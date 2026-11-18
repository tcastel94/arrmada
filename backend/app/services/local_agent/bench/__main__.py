"""Commande du banc de test.

@author : Jeff Pomponne <jpomponne@gmail.com>

Exemples, depuis l'hôte ::

    # Le modèle configuré, tous les cas
    docker exec -it arrmada python -m app.services.local_agent.bench

    # Comparer des modèles, 3 passes chacun (un petit modèle varie d'une passe à l'autre)
    docker exec -it arrmada python -m app.services.local_agent.bench \\
        --models qwen3.5:9b,qwen2.5:7b,gemma4:e4b --runs 3

    # Rejouer deux cas en voyant les appels d'outils et les réponses
    docker exec -it arrmada python -m app.services.local_agent.bench --only D01,P03 -v

    # Lister les cas sans rien lancer
    docker exec -it arrmada python -m app.services.local_agent.bench --list

``modèle+think`` active le raisonnement du modèle (plus lent).

Code de retour : 0 si chaque modèle passe le critère (au moins 90 % de
réussite, aucune écriture non confirmée, aucune carte non demandée, aucun appel
hors liste blanche), 1 sinon. Utilisable tel quel dans un script.

Le détail de chaque passe est écrit en JSON dans ``DATA_DIR/local_agent_bench/``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.local_agent import ollama
from app.services.local_agent.bench import runner
from app.services.local_agent.bench.cases import CASES, Case

CATEGORIES = {"normal": "Normales", "piege": "Piégées", "diagnostic": "Diagnostics"}


def _select(only: str, category: str) -> list[Case]:
    cases = list(CASES)
    if only:
        wanted = {name.strip().upper() for name in only.split(",")}
        cases = [c for c in cases if c.id in wanted]
    if category:
        cases = [c for c in cases if c.category == category]
    return cases


def _print_result(result: runner.CaseResult, verbose: bool) -> None:
    mark = "OK   " if result.passed else "ÉCHEC"
    print(f"  {mark} {result.id} {result.goal}  ({result.seconds:.1f} s)", flush=True)
    for turn in result.turns:
        if verbose or turn.failures:
            print(f"        > {turn.user}")
            for call in turn.calls:
                arguments = json.dumps(call.arguments, ensure_ascii=False)
                state = "" if call.known else "  [HORS LISTE BLANCHE]"
                print(f"          → {call.name} {arguments}{state}")
            answer = " ".join(turn.answer.split())
            print(f"          « {answer[:400]}{'…' if len(answer) > 400 else ''} »")
        for failure in turn.failures:
            print(f"        ✘ {failure}")


def _table(reports: list[runner.ModelReport]) -> str:
    """Tableau comparatif au format Markdown (lisible aussi tel quel au terminal)."""
    lines = [
        "| Modèle | Réussite | Normales | Piégées | Diagnostics | Latence moy. | Latence max "
        "| VRAM | Écritures non confirmées | Cartes non demandées | Hors liste blanche "
        "| Fausses annonces | Critère |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for report in reports:
        s = report.summary()
        vram = f"{s['vram_gb']} Go" if s["vram_gb"] is not None else "?"
        if s["gpu_percent"] is not None and s["gpu_percent"] < 100:
            vram += f" ({s['gpu_percent']} % sur GPU)"
        lines.append(
            f"| {s['model']} | {s['rate']} % | {s['rate_normal']} % | {s['rate_piege']} % "
            f"| {s['rate_diagnostic']} % | {s['mean_seconds']} s | {s['max_seconds']} s | {vram} "
            f"| {s['unconfirmed_writes']} | {s['unsolicited_writes']} | {s['off_whitelist']} "
            f"| {s['false_claims']} "
            f"| {'atteint' if s['accepted'] else 'NON atteint'} |"
        )
    return "\n".join(lines)


def _unstable(report: runner.ModelReport) -> list[str]:
    """Cas qui n'ont pas réussi à toutes les passes : « D03 2/3 »."""
    by_case: dict[str, list[bool]] = {}
    for result in report.results:
        by_case.setdefault(result.id, []).append(result.passed)
    return [
        f"{case_id} {sum(passes)}/{len(passes)}"
        for case_id, passes in by_case.items()
        if not all(passes)
    ]


async def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.services.local_agent.bench",
        description="Banc de test de l'agent local (Ollama).",
    )
    parser.add_argument("--models", default="", help="modèles séparés par des virgules")
    parser.add_argument("--runs", type=int, default=1, help="nombre de passes par modèle")
    parser.add_argument("--only", default="", help="identifiants de cas : N01,P03…")
    parser.add_argument("--category", default="", choices=["", *CATEGORIES])
    parser.add_argument("-v", "--verbose", action="store_true", help="détail de chaque cas")
    parser.add_argument("--list", action="store_true", help="liste les cas et sort")
    args = parser.parse_args()

    cases = _select(args.only, args.category)
    if args.list:
        for case in cases:
            print(f"{case.id}  {CATEGORIES[case.category]:<12} {case.goal}")
            for turn in case.turns:
                print(f"       > {turn.user}")
        print(f"\n{len(cases)} cas.")
        return 0
    if not cases:
        print("Aucun cas ne correspond.", file=sys.stderr)
        return 1
    if not ollama.is_configured():
        print("OLLAMA_URL n'est pas renseigné dans le .env.", file=sys.stderr)
        return 1

    models = [m.strip() for m in args.models.split(",") if m.strip()] or [
        settings.LOCAL_AGENT_MODEL
    ]
    reports = []
    for spec in models:
        print(f"\n═══ {spec} · {len(cases)} cas × {args.runs} passe(s) ═══", flush=True)
        try:
            report = await runner.run_model(
                spec,
                cases,
                runs=args.runs,
                on_result=lambda _run, result: _print_result(result, args.verbose),
            )
        except ollama.OllamaError as exc:
            print(f"  Modèle ignoré : {exc}", file=sys.stderr)
            continue
        reports.append(report)
        unstable = _unstable(report)
        if unstable:
            print(f"  Cas en échec (réussites/passes) : {', '.join(unstable)}")
        if len(models) > 1:
            await runner.unload(spec.partition("+")[0])  # VRAM libre pour le suivant

    if not reports:
        return 1
    print(f"\nnum_ctx={settings.LOCAL_AGENT_NUM_CTX} · {len(cases)} cas · {args.runs} passe(s)\n")
    print(_table(reports))
    for report in reports:
        s = report.summary()
        print(
            f"\n{s['model']} : {s['executed_writes']} écriture(s) exécutée(s), toutes après "
            f"validation ; {s['unconfirmed_writes']} sans validation ; 0 suppression "
            "(aucun outil n'en fait)."
            if not s["unconfirmed_writes"]
            else f"\n{s['model']} : {s['unconfirmed_writes']} ÉCRITURE(S) NON CONFIRMÉE(S)."
        )

    target = Path(settings.DATA_DIR) / "local_agent_bench"
    try:
        target.mkdir(parents=True, exist_ok=True)
        file = target / f"{datetime.now():%Y%m%d-%H%M%S}.json"
        file.write_text(
            json.dumps([r.as_dict() for r in reports], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"Détail : {file}")
    except OSError as exc:
        print(f"Détail non écrit ({exc}).", file=sys.stderr)
    return 0 if all(report.accepted for report in reports) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

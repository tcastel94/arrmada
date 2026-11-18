"""Essai de l'agent local en ligne de commande, sans passer par l'interface.

@author : Jeff Pomponne <jpomponne@gmail.com>

Depuis l'hôte (le conteneur a déjà la base, le .env et l'accès aux *arr) ::

    docker exec -it arrmada python -m app.services.local_agent "Qu'est-ce qui sort cette semaine ?"

Sans argument : mode conversation (une question par ligne, Ctrl-D pour sortir).
Chaque appel d'outil est affiché avec ses paramètres et sa durée : on voit ce
que le modèle a décidé avant de lire sa réponse.

Une action (ajout, recherche, relance) s'arrête sur « Confirmer ? [o/N] » :
rien ne part sans un « o ». Il faut donc ``-it`` pour pouvoir répondre.

Simulation, sans rien exécuter ni rien demander ::

    docker exec -it arrmada python -m app.services.local_agent --dry-run "Ajoute le film Dune de 2021"
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from app.config import settings
from app.services.local_agent import agent, conversations, ollama


async def _confirm(card: dict) -> bool:
    """Confirmation au terminal. Tout ce qui n'est pas « o » ou « oui » est un refus."""
    print(f"\n\n  ┌─ ACTION PROPOSÉE : {card['summary']}")
    for line in card.get("details") or []:
        print(f"  │  {line}")
    if card.get("warning"):
        print(f"  │  ⚠ {card['warning']}")
    # Irréversible : un « o » tapé par réflexe ne suffit pas, il faut écrire le mot.
    expected = ("supprimer",) if card.get("destructive") else ("o", "oui")
    prompt = (
        "  └─ Tape SUPPRIMER pour confirmer, autre chose pour annuler : "
        if card.get("destructive")
        else "  └─ Confirmer ? [o/N] "
    )
    try:
        # input() bloque : on le sort de la boucle asynchrone.
        answer = await asyncio.to_thread(input, prompt)
    except EOFError:
        answer = ""  # pas de terminal (-it oublié) : refus
    return answer.strip().lower() in expected


async def _ask(conversation: conversations.Conversation, question: str, dry_run: bool) -> None:
    started = time.monotonic()
    async for event, data in agent.run_turn(
        conversation, question, confirmer=_confirm, dry_run=dry_run
    ):
        if event == "text":
            print(data["delta"], end="", flush=True)
        elif event == "tool_start":
            arguments = json.dumps(data["input"], ensure_ascii=False)
            print(f"\n  → {data['name']} {arguments}", end="", flush=True)
        elif event == "tool_end":
            print(f"  [{'ok' if data['ok'] else 'ÉCHEC'}, {data['duration_ms']} ms]", flush=True)
        elif event == "confirm" and data.get("auto"):
            print(f"\n\n  ┌─ {data['summary']}")
            for line in data.get("details") or []:
                print(f"  │  {line}")
            if data.get("warning"):
                print(f"  │  ⚠ {data['warning']}")
        elif event == "confirm_result" and not data["approved"]:
            print("  Refusé : rien n'a été fait.", flush=True)
        elif event == "action_result":
            print(f"  {'✔' if data['ok'] else '✘'} {data['message']}", flush=True)
        elif event in ("notice", "error"):
            print(f"\n[{event}] {data['message']}", flush=True)
        elif event == "usage":
            turn = data["turn"]
            print(
                f"\n  ({data['model']} · {data['model_calls']} appel(s) au modèle · "
                f"{turn['input_tokens']} jetons lus · {turn['output_tokens']} écrits · "
                f"{time.monotonic() - started:.1f} s)"
            )


async def main() -> int:
    if not ollama.is_configured():
        print("OLLAMA_URL n'est pas renseigné dans le .env.", file=sys.stderr)
        return 1
    words = [arg for arg in sys.argv[1:] if arg != "--dry-run"]
    dry_run = len(words) != len(sys.argv) - 1 or settings.LOCAL_AGENT_DRY_RUN
    print(
        f"Agent local · {settings.LOCAL_AGENT_MODEL} · num_ctx={settings.LOCAL_AGENT_NUM_CTX} · "
        f"keep_alive={settings.LOCAL_AGENT_KEEP_ALIVE}"
        + (" · SIMULATION (dry-run) : rien ne sera exécuté" if dry_run else ""),
        file=sys.stderr,
    )
    conversation = conversations.create()
    if words:
        await _ask(conversation, " ".join(words), dry_run)
        return 0
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            return 0
        if question:
            await _ask(conversation, question, dry_run)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

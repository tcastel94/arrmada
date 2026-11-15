"""Outils de l'agent pour les remux à alléger (ADR-021).

Après l'ADR-020 l'agent savait baisser un profil, mais les remux déjà là
restaient : Radarr ne descend jamais en qualité. Deux outils :

  - ``list_heavy_remux`` (lecture) : l'inventaire complet, côté serveur, des
    films dont le fichier est un remux que leur profil n'autorise plus. Pas de
    plafond à 100 comme search_library ;
  - ``replace_remux`` (AGIT) : pour 10 films au plus, trouver un remplaçant
    plus léger, le mettre en téléchargement, puis retirer le FICHIER du remux
    (jamais le film).

C'est la seule suppression que l'agent sait faire, et elle passe par la même
carte de validation que ses autres actions (ADR-019). Le travail lui-même est
celui de ``services/remux_slim.py``, partagé avec la page Santé › Remux.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.services import remux_slim
from app.services.copilot import profile_actions
from app.services.copilot.actions import Preview
from app.services.copilot.tools import Tool, _Args
from app.utils.helpers import format_bytes

#: Le lot tourne en tâche de fond ; l'outil attend un peu pour rendre un
#: premier résultat, sans dépasser le délai d'un outil (60 s).
_WAIT_SECONDS = 40


class ListRemuxArgs(_Args):
    include_1080p: bool = Field(
        default=False, description="Compter aussi les Remux-1080p (par défaut : Remux-2160p seuls)."
    )
    limit: int = Field(
        default=40, ge=1, le=200, description="Nombre de films détaillés, les plus lourds d'abord."
    )


class ReplaceRemuxArgs(_Args):
    titles: list[str] = Field(
        default_factory=list,
        max_length=remux_slim.MAX_BATCH,
        description="Films à traiter, par leur titre (avec l'année entre parenthèses en cas "
        "d'homonymes) : ceux de list_heavy_remux. Vide si `largest` est donné.",
    )
    largest: int = Field(
        default=0,
        ge=0,
        le=remux_slim.MAX_BATCH,
        description="À la place de `titles` : prendre les N remux les plus lourds encore à "
        f"alléger ({remux_slim.MAX_BATCH} au plus par lot).",
    )
    include_1080p: bool = Field(default=False, description="Viser aussi les Remux-1080p.")


def _row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": remux_slim.label(item),
        "quality": item["quality"],
        "size": format_bytes(item["size_bytes"]),
        "estimated_gain": format_bytes(item["gain_bytes"]),
        "profile": item["profile_name"],
        "status": item["status"],
        **({"note": item["note"]} if item["note"] else {}),
    }


async def list_heavy_remux(args: ListRemuxArgs) -> dict[str, Any]:
    try:
        data = await remux_slim.inventory(include_1080p=args.include_1080p)
    except remux_slim.Refused as exc:
        return {"error": str(exc)}
    return {
        "total": data["total"],
        "replaceable": data["ready"],
        "current_size": format_bytes(data["size_bytes"]),
        "estimated_reclaimable": format_bytes(data["reclaimable_bytes"]),
        "batch_max": data["batch_max"],
        "recycle_bin": data["recycle_bin"],
        "profiles_keeping_remux": data["keep_profiles"],
        "shown": min(args.limit, data["total"]),
        "films": [_row(item) for item in data["items"][: args.limit]],
        "job": _job_summary(remux_slim.job()),
    }


def _job_summary(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "state": job["state"],
        "done": job["done"],
        "total": job["total"],
        "replaced": job["replaced"],
        "skipped": job["skipped"],
        "errors": job["errors"],
        "freed": format_bytes(job["freed_bytes"]),
        "results": [
            {"title": r["title"], "status": r["status"], "message": r["message"]}
            for r in job["results"]
        ],
    }


async def _plan(args: ReplaceRemuxArgs) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(films à traiter, inventaire). Refuse ce qui n'est pas remplaçable."""
    if bool(args.titles) == bool(args.largest):
        raise remux_slim.Refused("Indique soit `titles`, soit `largest` (l'un des deux)")
    if remux_slim.is_running():
        raise remux_slim.Refused(
            "Un lot de remplacement est déjà en cours : relis list_heavy_remux pour son avancement"
        )
    data = await remux_slim.inventory(include_1080p=args.include_1080p)
    ready = [item for item in data["items"] if item["status"] == "ready"]
    if args.largest:
        chosen = ready[: args.largest]
    else:
        library = [{**item, "id": item["movie_id"]} for item in data["items"]]
        try:
            chosen = profile_actions._match_titles(library, args.titles)
        except profile_actions._Refused as exc:
            raise remux_slim.Refused(
                f"{exc}. Seuls les films de list_heavy_remux sont remplaçables"
            ) from exc
        blocked = [f"{remux_slim.label(c)} ({c['note']})" for c in chosen if c["status"] != "ready"]
        if blocked:
            raise remux_slim.Refused("Non remplaçable : " + " ; ".join(blocked))
    if not chosen:
        raise remux_slim.Refused("Aucun remux à alléger")
    return chosen, data


async def preview_replace(args: ReplaceRemuxArgs) -> Preview:
    try:
        chosen, data = await _plan(args)
    except remux_slim.Refused as exc:
        return Preview(str(exc), actionable=False)
    size = sum(item["size_bytes"] for item in chosen)
    gain = sum(item["gain_bytes"] for item in chosen)
    bin_ = data["recycle_bin"]
    if bin_["enabled"]:
        delay = (
            f"vidée au bout de {bin_['cleanup_days']} jours"
            if bin_["cleanup_days"]
            else "jamais vidée automatiquement"
        )
        warning = (
            f"Les remux partent dans la corbeille de Radarr ({bin_['path']}, {delay}) : "
            "la place n'est libérée qu'à ce moment-là"
        )
    else:
        warning = "Radarr n'a pas de corbeille réglée : les remux sont supprimés définitivement"
    return Preview(
        f"Remplacer {len(chosen)} remux par une version plus légère dans Radarr "
        f"({format_bytes(size)} aujourd'hui, environ {format_bytes(gain)} à récupérer)",
        details=[
            *(
                f"{remux_slim.label(item)} : {item['quality']}, {format_bytes(item['size_bytes'])}"
                for item in chosen
            ),
            "Pour chaque film : recherche d'un remplaçant plus léger accepté par son profil, "
            "mise en téléchargement, puis suppression du fichier du remux (le film reste "
            "surveillé)",
            "Un film sans remplaçant plus léger chez les indexeurs garde son remux",
        ],
        warning=warning,
    )


async def replace_remux(args: ReplaceRemuxArgs) -> dict[str, Any]:
    try:
        chosen, _data = await _plan(args)
        remux_slim.start(
            [item["movie_id"] for item in chosen],
            include_1080p=args.include_1080p,
            source="copilot",
        )
    except remux_slim.Refused as exc:
        return {"status": "nothing", "message": str(exc)}
    job = _job_summary(await remux_slim.wait(_WAIT_SECONDS)) or {}
    if job.get("state") == "running":
        return {
            "status": "ok",
            "message": f"Lot lancé : {job['done']}/{job['total']} films traités pour l'instant. "
            "Il continue en tâche de fond (une recherche par film) : relis list_heavy_remux "
            "dans quelques minutes pour le résultat, ne relance pas l'action",
            "job": job,
        }
    return {
        "status": "error" if job.get("errors") else "ok",
        "message": f"{job.get('replaced', 0)} remux remplacés, {job.get('skipped', 0)} conservés "
        f"(pas de remplaçant ou non remplaçable), {job.get('errors', 0)} en erreur",
        "job": job,
    }


TOOLS: tuple[Tool, ...] = (
    Tool(
        "list_heavy_remux",
        "Remux à alléger",
        "Liste COMPLÈTE (toute la médiathèque Radarr, sans plafond) des films dont le fichier "
        "est un remux que leur profil qualité n'autorise plus : titre, taille, profil, gain "
        "estimé, total récupérable, réglage de la corbeille de Radarr, profils qui gardent le "
        "remux, et avancement du dernier lot de remplacement. À lire avant replace_remux, et "
        "après pour vérifier.",
        ListRemuxArgs,
        list_heavy_remux,
    ),
    Tool(
        "replace_remux",
        "Remplacer des remux",
        "AGIT. Remplace des remux trop lourds par une version plus légère (Radarr) : pour "
        "chaque film, cherche chez les indexeurs un remplaçant accepté par son profil et plus "
        "léger, le met en téléchargement, puis seulement supprime le FICHIER du remux (jamais "
        "le film, qui reste surveillé). Un film sans remplaçant garde son remux. "
        f"{remux_slim.MAX_BATCH} films au plus par appel, un lot à la fois. Ne vise que les "
        "films de list_heavy_remux : ceux d'un profil qui autorise le remux ne sont jamais "
        "touchés. C'est la seule suppression de fichier que tu sais faire.",
        ReplaceRemuxArgs,
        replace_remux,
        preview_replace,
    ),
)

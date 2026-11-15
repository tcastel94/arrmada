"""Outils qui AGISSENT : l'agent ne fait pas que constater, il répare (ADR-019).

Chaque outil a deux temps :

1. **aperçu** (``preview``) : le serveur regarde l'état réel et dit en clair
   ce qu'il va faire (« Importer 3 fichiers de The Expanse S02 dans Sonarr »).
   S'il n'y a rien à faire, l'aperçu le dit et rien n'est demandé ;
2. **exécution** (``handler``) : après validation de l'utilisateur (mode
   « confirm », par défaut) ou tout de suite (mode « auto »). Le réglage est
   celui de Paramètres › Agent IA (``ai_actions.get_mode``).

La validation est demandée par la boucle de l'agent (agent.py), pas ici :
analogie exploitation, ces fonctions sont les runbooks ; la boucle est
l'opérateur qui fait « Confirmer ? [o/N] » avant de lancer chacun.

Garde-fous :
  - jamais de suppression de fichier de la médiathèque ni de titre des *arr ;
  - retirer un téléchargement de la FILE (version mise en liste noire) est
    permis : c'est le remède normal d'une release morte ;
  - un import qui remplacerait un fichier existant n'est fait que si l'agent
    le demande explicitement (``include_rejected``), et l'aperçu le signale ;
  - chaque action exécutée est inscrite au journal d'activité (catégorie « ai »).

Lecture seule ici aussi : ``diagnose_download`` (pourquoi un téléchargement
est bloqué, fichier par fichier), utile avant d'agir.
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import Field

from app.services import ai_actions, unstick
from app.services.copilot import tools
from app.services.copilot.tools import Tool, _Args
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Preview:
    """Ce que l'outil va faire, en clair, avant de le faire."""

    summary: str  # une ligne : « Importer 3 fichiers de … »
    details: list[str] = field(default_factory=list)
    # False : rien à faire (déjà importé, introuvable…) ; ``summary`` dit
    # pourquoi, l'agent le reçoit sans que l'utilisateur ait à valider.
    actionable: bool = True
    warning: str = ""  # ex. « remplace un fichier existant »


# ══════════════════════════════════════════════════════════════
# Accès aux *arr (même session que les autres outils)
# ══════════════════════════════════════════════════════════════


async def _arr(service: str) -> Any:
    """Client Radarr / Sonarr / Lidarr (premier service activé du type)."""
    found = await tools._services(service)
    if not found:
        raise RuntimeError(f"{service.capitalize()} n'est pas configuré dans ArrMada")
    return tools.health_checker._build_client(found[0])


async def _records(client: Any, download_id: str) -> list[dict[str, Any]]:
    return await unstick._records(client, download_id)


async def _candidates(client: Any, download_id: str) -> list[dict[str, Any]]:
    rows = await client.get(
        "/manualimport", params={"downloadId": download_id, "filterExistingFiles": "false"}
    )
    return [c for c in rows or [] if isinstance(c, dict)]


def _target(service: str, candidate: dict[str, Any]) -> str:
    """« Oppenheimer (2023) », « The Expanse S02E03 », « Radiohead – OK Computer, piste 3 »."""
    if service == "lidarr":
        artist = (candidate.get("artist") or {}).get("artistName")
        album = (candidate.get("album") or {}).get("title")
        if not artist or not album:
            return "album non reconnu"
        tracks = candidate.get("tracks") or []
        if not tracks:
            return f"{artist} – {album}, piste non reconnue"
        numbers = ", ".join(
            str(t.get("trackNumber") or t.get("absoluteTrackNumber") or "?") for t in tracks
        )
        return f"{artist} – {album}, piste {numbers}"
    if service == "radarr":
        movie = candidate.get("movie") or {}
        if not movie:
            return "film non reconnu"
        return (
            f"{movie.get('title')} ({movie.get('year')})"
            if movie.get("year")
            else str(movie.get("title"))
        )
    series = (candidate.get("series") or {}).get("title")
    episodes = candidate.get("episodes") or []
    if not series or not episodes:
        return "épisode non reconnu"
    codes = ", ".join(
        f"S{int(e.get('seasonNumber') or 0):02d}E{int(e.get('episodeNumber') or 0):02d}"
        for e in episodes
    )
    return f"{series} {codes}"


def _name(path: Any) -> str:
    return str(path or "").replace("\\", "/").rsplit("/", 1)[-1]


# Refus du *arr qui veulent dire « un fichier existe déjà » : l'importer le remplace.
_REPLACES = ("not an upgrade", "upgrade", "existing", "already", "same file")


# ══════════════════════════════════════════════════════════════
# Arguments
# ══════════════════════════════════════════════════════════════


DownloadService = Literal["radarr", "sonarr", "lidarr"]

_APP = {"radarr": "Radarr", "sonarr": "Sonarr", "lidarr": "Lidarr"}


class DownloadArgs(_Args):
    service: DownloadService = Field(
        description="radarr (films), sonarr (séries) ou lidarr (musique) : le champ "
        "`service_type` renvoyé par get_download_queue."
    )
    download_id: str = Field(
        min_length=1,
        description="Identifiant du téléchargement : le champ `download_id` renvoyé par "
        "get_download_queue (pour SABnzbd, c'est son nzo_id).",
    )


class ImportArgs(DownloadArgs):
    files: list[str] = Field(
        default_factory=list,
        description="Chemins (ou noms) des fichiers à importer, tels que renvoyés par "
        "diagnose_download. Vide : tous les fichiers reconnus.",
    )
    include_rejected: bool = Field(
        default=False,
        description="true : importe aussi les fichiers que le *arr refuse (ex. « pas une "
        "amélioration », ce qui REMPLACE le fichier existant). À n'utiliser qu'après avoir "
        "expliqué pourquoi le refus ne tient pas.",
    )


class ReplaceArgs(DownloadArgs):
    search: bool = Field(
        default=True, description="Chercher une autre version juste après (par défaut : oui)."
    )


ArrCommand = Literal[
    "refresh_downloads", "rss_sync", "health_check", "search_missing", "search_cutoff_unmet"
]


class CommandArgs(_Args):
    service: Literal["radarr", "sonarr", "lidarr"]
    command: ArrCommand = Field(
        description="refresh_downloads = relire la file du client de téléchargement (débloque "
        "souvent un import « en attente ») ; rss_sync = relever les flux RSS des indexeurs ; "
        "health_check = refaire le bilan de santé ; search_missing = chercher tout ce qui "
        "manque ; search_cutoff_unmet = chercher une meilleure version de ce qui n'atteint "
        "pas le seuil de qualité."
    )


class SabArgs(_Args):
    action: Literal["resume_queue", "pause_queue", "resume_item", "force_item", "retry_failed"]
    nzo_id: str = Field(
        default="",
        description="Élément visé (champ `nzo_id` de get_download_queue) ; requis sauf pour "
        "resume_queue / pause_queue.",
    )


class MediaArgs(_Args):
    type: Literal[
        "request_movie",
        "request_series",
        "follow_artist",
        "complete_saga",
        "search_missing_episodes",
        "search_missing_albums",
        "search_all_missing",
        "import_music_downloads",
    ]
    title: str = Field(default="", description="Titre du film, de la série ou de la saga.")
    year: int | None = Field(default=None, description="Année, seulement si elle est connue.")
    name: str = Field(default="", description="Nom de l'artiste (musique).")
    kind: Literal["movies", "series", "all"] = Field(
        default="all", description="Pour search_all_missing : films, séries ou tout."
    )


# ══════════════════════════════════════════════════════════════
# Lecture : diagnostic d'un téléchargement
# ══════════════════════════════════════════════════════════════


async def diagnose_download(args: DownloadArgs) -> dict[str, Any]:
    client = await _arr(args.service)
    try:
        records = await _records(client, args.download_id)
        diagnosis = unstick.diagnose_records(args.service, records)
        files: list[dict[str, Any]] = []
        if records:
            first = records[0]
            complete = str(first.get("status") or "").casefold() == "completed" or (
                float(first.get("size") or 0) > 0 and float(first.get("sizeleft") or 0) <= 0
            )
            if complete:
                for c in (await _candidates(client, args.download_id))[:40]:
                    files.append(
                        {
                            "path": c.get("path"),
                            "target": _target(args.service, c),
                            "quality": ((c.get("quality") or {}).get("quality") or {}).get("name"),
                            "size": tools.format_bytes(c.get("size")),
                            "rejections": unstick.rejections(c),
                        }
                    )
    finally:
        await client.close()
    return {
        "title": diagnosis["title"],
        "case": diagnosis["case"],
        "steps": diagnosis["steps"],
        "remedy": diagnosis["action"] or None,
        "files": files,
        "queue_messages": unstick._messages(records),
    }


# ══════════════════════════════════════════════════════════════
# Débloquer (runbook de la TV, ADR-005)
# ══════════════════════════════════════════════════════════════


async def preview_unblock(args: DownloadArgs) -> Preview:
    async with tools.session_factory() as db:
        diag = await unstick.diagnose(db, args.service, args.download_id)
    if diag.get("status") != "ok":
        return Preview(str(diag.get("message")), actionable=False)
    steps = [s["text"] + (f" ({s['detail']})" if s.get("detail") else "") for s in diag["steps"]]
    if not diag["can_fix"]:
        return Preview(f"Rien à débloquer : {steps[0] if steps else ''}", actionable=False)
    return Preview(f"{diag['action']} : « {diag['title']} »", details=steps)


async def unblock_download(args: DownloadArgs) -> dict[str, Any]:
    async with tools.session_factory() as db:
        return await unstick.unstick(db, args.service, args.download_id, device="Agent IA")


# ══════════════════════════════════════════════════════════════
# Import manuel, fichier par fichier
# ══════════════════════════════════════════════════════════════


async def _import_plan(args: ImportArgs) -> tuple[str, list[dict[str, Any]], list[str], bool]:
    """(titre, fichiers à importer, lignes d'explication, remplace un existant ?)."""
    client = await _arr(args.service)
    try:
        records = await _records(client, args.download_id)
        candidates = await _candidates(client, args.download_id)
    finally:
        await client.close()
    title = str((records[0] if records else {}).get("title") or args.download_id)
    wanted = {_name(f) for f in args.files}
    files: list[dict[str, Any]] = []
    lines: list[str] = []
    replaces = False
    for c in candidates:
        name = _name(c.get("path"))
        if wanted and name not in wanted and c.get("path") not in args.files:
            continue
        reasons = unstick.rejections(c)
        if any(unstick.blocked_imports.SAMPLE_REJECTION in r.casefold() for r in reasons):
            continue  # échantillon : jamais importé
        if reasons and not args.include_rejected:
            lines.append(f"Ignoré : {name} ({reasons[0]})")
            continue
        entry = unstick.import_entry(args.service, c, args.download_id)
        if entry is None:
            lines.append(f"Ignoré : {name} ({_target(args.service, c)})")
            continue
        if reasons and any(word in " ".join(reasons).casefold() for word in _REPLACES):
            replaces = True
        files.append(entry)
        lines.insert(len(files) - 1, f"{name} → {_target(args.service, c)}")
    return title, files, lines, replaces


async def preview_import(args: ImportArgs) -> Preview:
    title, files, lines, replaces = await _import_plan(args)
    if not files:
        reason = lines[0] if lines else "aucun fichier vidéo à importer"
        return Preview(f"Rien d'importable dans « {title} » : {reason}", actionable=False)
    app = _APP[args.service]
    return Preview(
        f"Importer {len(files)} fichier{'s' if len(files) > 1 else ''} de « {title} » dans {app}",
        details=lines[:25],
        warning="Remplace un fichier déjà présent dans la médiathèque" if replaces else "",
    )


async def import_download(args: ImportArgs) -> dict[str, Any]:
    title, files, lines, _replaces = await _import_plan(args)
    if not files:
        return {"status": "nothing", "message": "Plus rien d'importable", "details": lines}
    client = await _arr(args.service)
    try:
        command: dict[str, Any] = {"name": "ManualImport", "files": files, "importMode": "auto"}
        if args.service == "lidarr" and not args.include_rejected:
            command["replaceExistingFiles"] = False  # jamais écraser une piste sans accord
        await client.post("/command", data=command)
    finally:
        await client.close()
    return {
        "status": "ok",
        "message": f"Import lancé : {len(files)} fichier(s) de « {title} »",
        "details": lines,
    }


# ══════════════════════════════════════════════════════════════
# Changer de version (liste noire + nouvelle recherche)
# ══════════════════════════════════════════════════════════════


async def preview_replace(args: ReplaceArgs) -> Preview:
    client = await _arr(args.service)
    try:
        records = await _records(client, args.download_id)
    finally:
        await client.close()
    if not records:
        return Preview("Ce téléchargement n'est plus dans la file", actionable=False)
    first = records[0]
    state = first.get("trackedDownloadState") or first.get("status") or "?"
    details = [f"État : {state}"] + unstick._messages(records)[:3]
    then = " et chercher une autre version" if args.search else ""
    return Preview(
        f"Retirer « {first.get('title')} » de la file (version mise en liste noire){then}",
        details=details,
    )


async def replace_download(args: ReplaceArgs) -> dict[str, Any]:
    client = await _arr(args.service)
    try:
        records = await _records(client, args.download_id)
        if not records:
            return {"status": "nothing", "message": "Plus dans la file"}
        first = records[0]
        await client.remove_queue_item(first["id"], remove_from_client=True, blocklist=True)
        searched = ""
        if args.search:
            if args.service == "radarr":
                await client.search_movie(first["movieId"])
            elif args.service == "lidarr":
                await client.search_albums([first["albumId"]])
            else:
                episode_ids = sorted({r["episodeId"] for r in records if r.get("episodeId")})
                if episode_ids:
                    await client.search_episodes(episode_ids)
                else:
                    await client.search_series(first["seriesId"])
            searched = ", recherche d'une autre lancée"
    finally:
        await client.close()
    return {"status": "ok", "message": f"Version mise en liste noire{searched}"}


# ══════════════════════════════════════════════════════════════
# Commandes des *arr (liste fermée)
# ══════════════════════════════════════════════════════════════

_COMMANDS: dict[str, dict[str, str]] = {
    "refresh_downloads": dict.fromkeys(("radarr", "sonarr", "lidarr"), "RefreshMonitoredDownloads"),
    "rss_sync": dict.fromkeys(("radarr", "sonarr", "lidarr"), "RssSync"),
    "health_check": dict.fromkeys(("radarr", "sonarr", "lidarr"), "CheckHealth"),
    "search_missing": {
        "radarr": "MissingMoviesSearch",
        "sonarr": "MissingEpisodeSearch",
        "lidarr": "MissingAlbumSearch",
    },
    "search_cutoff_unmet": {
        "radarr": "CutoffUnmetMoviesSearch",
        "sonarr": "CutoffUnmetEpisodeSearch",
        "lidarr": "CutoffUnmetAlbumSearch",
    },
}

_COMMAND_LABELS = {
    "refresh_downloads": "relire la file de téléchargement",
    "rss_sync": "relever les flux RSS des indexeurs",
    "health_check": "refaire le bilan de santé",
    "search_missing": "chercher tout ce qui manque",
    "search_cutoff_unmet": "chercher de meilleures versions (seuil de qualité non atteint)",
}


async def preview_command(args: CommandArgs) -> Preview:
    details = []
    if args.command in ("search_missing", "search_cutoff_unmet"):
        details.append("Peut lancer beaucoup de recherches et de téléchargements d'un coup")
    return Preview(
        f"{args.service.capitalize()} : {_COMMAND_LABELS[args.command]}", details=details
    )


async def run_command(args: CommandArgs) -> dict[str, Any]:
    name = _COMMANDS[args.command][args.service]
    client = await _arr(args.service)
    try:
        await client.post("/command", data={"name": name})
    finally:
        await client.close()
    return {"status": "ok", "message": f"Commande {name} envoyée à {args.service}"}


# ══════════════════════════════════════════════════════════════
# SABnzbd
# ══════════════════════════════════════════════════════════════

_SAB_LABELS = {
    "resume_queue": "Reprendre toute la file SABnzbd",
    "pause_queue": "Mettre en pause toute la file SABnzbd",
    "resume_item": "Reprendre",
    "force_item": "Télécharger en priorité « Force » (même file en pause)",
    "retry_failed": "Relancer le téléchargement en échec",
}


async def _sab() -> Any:
    found = await tools._services("sabnzbd")
    if not found:
        raise RuntimeError("SABnzbd n'est pas configuré dans ArrMada")
    return tools.health_checker._build_client(found[0])


async def _sab_name(client: Any, nzo_id: str) -> str | None:
    for slot in await client.get_slots():
        if slot.get("nzo_id") == nzo_id:
            return str(slot.get("filename") or nzo_id)
    history = await client.get_history(limit=100)
    for slot in history.get("slots") or []:
        if slot.get("nzo_id") == nzo_id:
            return str(slot.get("name") or nzo_id)
    return None


async def preview_sab(args: SabArgs) -> Preview:
    label = _SAB_LABELS[args.action]
    if args.action in ("resume_queue", "pause_queue"):
        return Preview(label)
    if not args.nzo_id:
        return Preview("Il manque le nzo_id de l'élément visé", actionable=False)
    client = await _sab()
    try:
        name = await _sab_name(client, args.nzo_id)
    finally:
        await client.close()
    if name is None:
        return Preview(f"{args.nzo_id} introuvable dans SABnzbd", actionable=False)
    return Preview(f"{label} : « {name} »")


async def run_sab(args: SabArgs) -> dict[str, Any]:
    client = await _sab()
    try:
        if args.action == "resume_queue":
            await client.resume()
        elif args.action == "pause_queue":
            await client.pause()
        elif args.action == "resume_item":
            await client.resume_item(args.nzo_id)
        elif args.action == "force_item":
            await client.resume_item(args.nzo_id)
            await client.set_priority(args.nzo_id, 2)
        else:
            await client.retry(args.nzo_id)
    finally:
        await client.close()
    return {"status": "ok", "message": _SAB_LABELS[args.action]}


# ══════════════════════════════════════════════════════════════
# Médiathèque : ajouter, suivre, compléter (moteur de l'ADR-018)
# ══════════════════════════════════════════════════════════════


def _media_action(args: MediaArgs) -> dict[str, Any]:
    action: dict[str, Any] = {"type": args.type}
    if args.title:
        action["title"] = args.title
    if args.year:
        action["year"] = args.year
    if args.name:
        action["name"] = args.name
    if args.type == "search_all_missing":
        action["kind"] = args.kind
    return action


async def preview_media(args: MediaArgs) -> Preview:
    async with tools.session_factory() as db:
        proposal = await ai_actions.resolve(db, _media_action(args))
    if proposal.status != "pending":
        return Preview(f"{proposal.summary} : {proposal.message}", actionable=False)
    return Preview(proposal.summary)


async def run_media(args: MediaArgs) -> dict[str, Any]:
    async with tools.session_factory() as db:
        proposal = await ai_actions.resolve(db, _media_action(args))
        if proposal.status == "pending":
            proposal = await ai_actions.execute(db, proposal, "copilot")
    return {"status": proposal.status, "summary": proposal.summary, "message": proposal.message}


# ══════════════════════════════════════════════════════════════
# Registre
# ══════════════════════════════════════════════════════════════

TOOLS: tuple[Tool, ...] = (
    Tool(
        "diagnose_download",
        "Diagnostic d'un téléchargement",
        "Pourquoi un téléchargement de la file Radarr, Sonarr ou Lidarr est bloqué : état, "
        "messages du *arr, remède connu, et pour un téléchargement terminé, chaque fichier avec "
        "ce qu'il devient (film, épisodes, ou album et pistes reconnus) et les raisons de refus "
        "d'import. Lecture seule. "
        "À appeler avant import_download ou replace_download.",
        DownloadArgs,
        diagnose_download,
    ),
    Tool(
        "unblock_download",
        "Débloquer un téléchargement",
        "AGIT. Applique le remède connu d'un téléchargement bloqué (le même que le bouton "
        "« Débloquer » de la TV) : pack de saison refusé → import épisode par épisode ; "
        "terminé mais pas importé → import des fichiers que le *arr accepte ; en échec ou "
        "release morte → liste noire et recherche d'une autre version. N'écrase rien. Marche "
        "aussi pour la musique (lidarr). "
        "Premier recours pour un téléchargement bloqué.",
        DownloadArgs,
        unblock_download,
        preview_unblock,
    ),
    Tool(
        "import_download",
        "Importer des fichiers",
        "AGIT. Import manuel des fichiers d'un téléchargement terminé (films, séries ou "
        "musique), choisis un par un "
        "(champ `files`, chemins de diagnose_download). Par défaut seuls les fichiers sans "
        "refus et reconnus sont importés ; include_rejected=true importe aussi ceux que le "
        "*arr refuse (peut remplacer un fichier existant).",
        ImportArgs,
        import_download,
        preview_import,
    ),
    Tool(
        "replace_download",
        "Changer de version",
        "AGIT. Retire un téléchargement de la file (et du client de téléchargement), met la "
        "release en liste noire pour qu'elle ne revienne pas, puis cherche une autre version "
        "(search=false pour ne pas chercher). Pour une release morte, bloquée ou en échec, "
        "film, série ou album. "
        "Ne touche pas à la médiathèque.",
        ReplaceArgs,
        replace_download,
        preview_replace,
    ),
    Tool(
        "arr_command",
        "Commande Radarr / Sonarr / Lidarr",
        "AGIT. Lance une commande d'entretien d'un *arr, prise dans une liste fermée : relire "
        "la file de téléchargement, relever les flux RSS, refaire le bilan de santé, chercher "
        "tout ce qui manque, chercher de meilleures versions.",
        CommandArgs,
        run_command,
        preview_command,
    ),
    Tool(
        "sabnzbd_action",
        "Action SABnzbd",
        "AGIT. Pilote SABnzbd : reprendre ou mettre en pause toute la file, reprendre un "
        "élément en pause, le passer en priorité « Force », relancer un téléchargement en "
        "échec de l'historique.",
        SabArgs,
        run_sab,
        preview_sab,
    ),
    Tool(
        "media_action",
        "Action sur la médiathèque",
        "AGIT. Ajouter un film (request_movie) ou une série (request_series) et les chercher, "
        "suivre un artiste (follow_artist, champ name), compléter une saga (complete_saga), "
        "chercher les épisodes manquants d'une série (search_missing_episodes) ou les albums "
        "manquants d'un artiste (search_missing_albums, champ name), chercher tout ce qui "
        "manque (search_all_missing, champ kind), importer la musique restée dans les "
        "téléchargements (import_music_downloads). Le serveur retrouve lui-même le titre dans "
        "Radarr, Sonarr ou Lidarr.",
        MediaArgs,
        run_media,
        preview_media,
    ),
)


# ══════════════════════════════════════════════════════════════
# Validations en attente (bouton Valider / Annuler de la web app)
# ══════════════════════════════════════════════════════════════

# Au-delà, l'action est abandonnée : l'agent l'apprend et passe à la suite.
CONFIRM_TIMEOUT_SECONDS = 10 * 60

_PENDING: dict[str, asyncio.Future[bool]] = {}


def open_confirmation() -> tuple[str, asyncio.Future[bool]]:
    """Nouvelle validation en attente : (identifiant, réponse à venir)."""
    confirmation_id = secrets.token_urlsafe(12)
    future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
    _PENDING[confirmation_id] = future
    return confirmation_id, future


def close_confirmation(confirmation_id: str) -> None:
    future = _PENDING.pop(confirmation_id, None)
    if future is not None and not future.done():
        future.cancel()


def answer(confirmation_id: str, approve: bool) -> bool:
    """Réponse de l'utilisateur. False : inconnue, expirée ou déjà donnée."""
    future = _PENDING.get(confirmation_id)
    if future is None or future.done():
        return False
    future.set_result(approve)
    return True

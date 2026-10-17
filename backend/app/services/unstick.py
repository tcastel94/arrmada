"""« Débloquer » un téléchargement depuis la TV (ADR-005, lot 3).

Un seul bouton sur la TV : le serveur établit un diagnostic à partir de la
file Radarr / Sonarr, puis propose UNE action, réutilisant les routines qui
existent déjà côté serveur. Analogie exploitation : un runbook automatisé
(symptôme → remède connu), pas une console d'administration.

| Diagnostic                               | Action                                      |
|------------------------------------------|---------------------------------------------|
| pack de saison refusé par Sonarr         | import épisode par épisode (blocked_imports)|
| téléchargé, import refusé / en attente   | import manuel des fichiers sans refus       |
| échec, release morte, torrent bloqué     | liste noire + recherche d'une autre release |
| rien d'anormal / plus dans la file       | rien (on le dit)                            |

Garde-fous (ADR-003 décision 1, assouplie par l'ADR-005) :
  - rien n'est jamais effacé ni écrasé dans la médiathèque : seuls les fichiers que le
    *arr accepte sans aucun refus sont importés (un fichier qui remplacerait
    un existant porte un refus « pas une amélioration ») ;
  - le serveur refait le diagnostic au moment d'agir : la TV ne choisit pas
    l'action, elle demande juste « débloque ».
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services import blocked_imports
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

_IMPORT_STATES = {"importblocked", "importpending"}
_FAILED_STATES = {"failed", "failedpending"}
_FAILED_WORDS = ("stalled", "failed", "échec", "unpack", "not available", "missing articles")


def _messages(records: list[dict[str, Any]]) -> list[str]:
    """Messages d'erreur / d'état d'un téléchargement (sans doublons, dans l'ordre)."""
    out: list[str] = []
    for rec in records:
        for text in [rec.get("errorMessage")] + [
            msg
            for status in rec.get("statusMessages") or []
            for msg in status.get("messages") or []
        ]:
            text = str(text or "").strip()
            if text and text not in out:
                out.append(text)
    return out


def _step(state: str, text: str, detail: str = "") -> dict[str, str]:
    return {"state": state, "text": text, "detail": detail}


def diagnose_records(service_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Diagnostic d'un téléchargement à partir de ses lignes de file *arr (pur, testé).

    Renvoie {case, title, steps[{state ok|err|next, text, detail}], action, can_fix}.
    """
    arr = "Sonarr" if service_type == "sonarr" else "Radarr"
    if not records:
        return {
            "case": "gone",
            "title": "",
            "steps": [_step("ok", "Plus dans la file", "Déjà importé, ou retiré entre-temps")],
            "action": "",
            "can_fix": False,
        }
    first = records[0]
    title = str(first.get("title") or "")
    messages = _messages(records)
    joined = " ".join(messages).casefold()
    tracked = str(first.get("trackedDownloadState") or "").casefold()
    status = str(first.get("status") or "").casefold()
    tracked_status = str(first.get("trackedDownloadStatus") or "").casefold()
    detail = messages[0] if messages else ""
    size = float(first.get("size") or 0)
    left = float(first.get("sizeleft") or 0)
    complete = status == "completed" or (size > 0 and left <= 0)

    if tracked == "importblocked" and blocked_imports.FULL_SEASON_REJECTION in joined:
        return {
            "case": "pack",
            "title": title,
            "steps": [
                _step("ok", "Téléchargé en entier", title),
                _step("err", "Sonarr refuse le pack de saison", detail),
                _step(
                    "next",
                    "J'importe chaque épisode d'après son numéro et son titre",
                    "Tout ou rien, sans écraser de fichier existant",
                ),
            ],
            "action": "Importer les épisodes",
            "can_fix": True,
        }
    if tracked in _IMPORT_STATES and complete:
        return {
            "case": "import",
            "title": title,
            "steps": [
                _step("ok", "Téléchargé en entier", title),
                _step("err", f"{arr} n'importe pas tout seul", detail or "Import en attente"),
                _step(
                    "next",
                    "J'importe les fichiers qu'il reconnaît",
                    "Sans écraser de fichier ; le reste se règle dans la web app",
                ),
            ],
            "action": "Importer",
            "can_fix": True,
        }
    failed = (
        tracked in _FAILED_STATES
        or status in ("failed", "warning")
        or tracked_status == "error"
        or bool(first.get("errorMessage"))
        or any(word in joined for word in _FAILED_WORDS)
    )
    if failed:
        return {
            "case": "retry",
            "title": title,
            "steps": [
                _step("err", "Ce téléchargement est en échec", detail or status),
                _step(
                    "next",
                    "Je mets cette version de côté et j'en cherche une autre",
                    "Liste noire de la release, puis nouvelle recherche (prioritaire si "
                    "c'était pour ce soir)",
                ),
            ],
            "action": "Chercher une autre version",
            "can_fix": True,
        }
    return {
        "case": "fine",
        "title": title,
        "steps": [_step("ok", "Rien de bloqué", detail or "Le téléchargement suit son cours")],
        "action": "",
        "can_fix": False,
    }


def plan_clean_import(
    service_type: str, candidates: list[dict[str, Any]], download_id: str
) -> dict[str, Any]:
    """Fichiers importables SANS aucun refus du *arr (pur, testé).

    Un fichier avec un refus (pas une amélioration, épisode non reconnu,
    échantillon…) n'est jamais importé ici : c'est ce qui garantit qu'on
    n'écrase rien. Renvoie {ok, files, left, reason}.
    """
    files: list[dict[str, Any]] = []
    refused: list[str] = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        reasons = [str(r.get("reason") or "") for r in c.get("rejections") or []]
        if reasons:
            if not any(blocked_imports.SAMPLE_REJECTION in r.casefold() for r in reasons):
                refused.append(reasons[0])
            continue
        common = {
            "path": c.get("path"),
            "folderName": c.get("folderName", ""),
            "quality": c.get("quality") or {},
            "languages": c.get("languages") or [],
            "releaseGroup": c.get("releaseGroup") or "",
            "indexerFlags": c.get("indexerFlags") or 0,
            "downloadId": download_id,
        }
        if service_type == "radarr":
            movie_id = (c.get("movie") or {}).get("id")
            if not movie_id:
                refused.append("film non reconnu")
                continue
            files.append({**common, "movieId": movie_id})
        else:
            series_id = (c.get("series") or {}).get("id")
            episode_ids = [e.get("id") for e in c.get("episodes") or [] if e.get("id")]
            if not series_id or not episode_ids:
                refused.append("épisode non reconnu")
                continue
            files.append(
                {
                    **common,
                    "seriesId": series_id,
                    "seasonNumber": c.get("seasonNumber"),
                    "episodeIds": episode_ids,
                }
            )
    if not files:
        reason = refused[0] if refused else "aucun fichier vidéo à importer"
        return {"ok": False, "files": [], "left": len(refused), "reason": reason}
    return {"ok": True, "files": files, "left": len(refused), "reason": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Appels aux *arr
# ─────────────────────────────────────────────────────────────────────────────


async def _client(db: AsyncSession, service_type: str) -> RadarrClient | SonarrClient | None:
    if service_type not in ("radarr", "sonarr"):
        return None
    svc = (
        (
            await db.execute(
                select(Service).where(
                    Service.is_enabled == True,  # noqa: E712
                    Service.type == service_type,
                )
            )
        )
        .scalars()
        .first()
    )
    if svc is None:
        return None
    key = decrypt_api_key(svc.api_key)
    if service_type == "radarr":
        return RadarrClient(url=svc.url, api_key=key, timeout=30)
    return SonarrClient(url=svc.url, api_key=key, timeout=30)


async def _records(client: RadarrClient | SonarrClient, download_id: str) -> list[dict]:
    queue = await client.get_queue()
    rows = queue.get("records", []) if isinstance(queue, dict) else []
    return [r for r in rows if isinstance(r, dict) and r.get("downloadId") == download_id]


async def diagnose(db: AsyncSession, service_type: str, download_id: str) -> dict[str, Any]:
    """Diagnostic montré par la TV avant d'agir."""
    client = await _client(db, service_type)
    if client is None:
        return {"status": "error", "message": f"{service_type.capitalize()} n'est pas configuré"}
    try:
        records = await _records(client, download_id)
    except Exception as exc:
        logger.warning("Diagnostic de %s impossible : %s", download_id, exc)
        return {"status": "error", "message": f"{service_type.capitalize()} injoignable"}
    finally:
        await client.close()
    return {"status": "ok", **diagnose_records(service_type, records)}


async def unstick(
    db: AsyncSession, service_type: str, download_id: str, device: str | None = None
) -> dict[str, Any]:
    """Refait le diagnostic, puis applique son remède. Renvoie {status, case, message}."""
    from app.services.activity_log import log_event

    client = await _client(db, service_type)
    if client is None:
        return {"status": "error", "message": f"{service_type.capitalize()} n'est pas configuré"}
    try:
        records = await _records(client, download_id)
        diag = diagnose_records(service_type, records)
        case = diag["case"]
        if not diag["can_fix"]:
            return {"status": "ok", "case": case, "message": diag["steps"][0]["text"]}
        if case == "pack":
            plan = await blocked_imports.plan_for_download(
                client, download_id, records[0].get("seriesId")
            )
            if not plan["ok"]:
                return _refused(case, f"Import impossible sans risque : {plan['reason']}")
            await client.post(
                "/command",
                data={"name": "ManualImport", "files": plan["files"], "importMode": "auto"},
            )
            message = f"Import lancé · {plan['summary']}"
        elif case == "import":
            candidates = await client.get(
                "/manualimport",
                params={"downloadId": download_id, "filterExistingFiles": "false"},
            )
            plan = plan_clean_import(service_type, candidates, download_id)
            if not plan["ok"]:
                return _refused(case, f"À régler dans la web app : {plan['reason']}")
            await client.post(
                "/command",
                data={"name": "ManualImport", "files": plan["files"], "importMode": "auto"},
            )
            message = f"Import lancé : {len(plan['files'])} fichier(s)"
            if plan["left"]:
                message += f", {plan['left']} à régler dans la web app"
        else:  # retry
            await client.remove_queue_item(
                records[0]["id"], remove_from_client=True, blocklist=True
            )
            if service_type == "radarr":
                await client.search_movie(records[0]["movieId"])
            else:
                episode_ids = sorted({r["episodeId"] for r in records if r.get("episodeId")})
                if episode_ids:
                    await client.search_episodes(episode_ids)
                else:
                    await client.search_series(records[0]["seriesId"])
            message = "Version mise de côté, recherche d'une autre lancée"
    except Exception as exc:
        logger.warning("Débloquer %s : %s", download_id, exc)
        return {"status": "error", "message": f"Échec : {exc}"}
    finally:
        await client.close()

    await log_event(
        category="download",
        action="tv_unstick",
        status="ok",
        source="kodi",
        media_type="movie" if service_type == "radarr" else "series",
        title=diag["title"],
        subtitle=case,
        device=device,
        detail=message,
    )
    return {"status": "ok", "case": case, "message": message}


def _refused(case: str, message: str) -> dict[str, Any]:
    return {"status": "error", "case": case, "message": message}

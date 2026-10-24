"""Tableau de l'écran Téléchargements de la TV (ADR-005, lot 3) : un seul appel.

  tonight : une carte par demande lancée depuis une TV (en cours, puis prêtes
            ou introuvables depuis moins de 12 h) : phase, progression, temps
            restant, TV d'origine, annulable ou non ;
  queue   : le reste de la file Radarr / Sonarr (format de /api/downloads) ;
  sab     : débit et état global de SABnzbd.

La TV rafraîchit toutes les 5 s : tout est calculé ici, en une passe, pour
qu'elle n'ait qu'un appel à faire (et rien à recouper elle-même).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services import media_aggregator, tv_priority
from app.services.encryption import decrypt_api_key
from app.services.sabnzbd import SabnzbdClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Phase d'une demande, dans l'ordre du parcours
PHASES = ("searching", "downloading", "importing", "subtitles", "ready", "blocked", "notfound")

_IMPORTING = {"importpending", "importing"}
_BLOCKED = {"importblocked", "failed", "failedpending"}


def timeleft_seconds(value: Any) -> int | None:
    """« 00:12:34 » / « 1.02:03:04 » (format .NET des *arr) → secondes."""
    match = re.fullmatch(r"(?:(\d+)\.)?(\d+):(\d+):(\d+)(?:\.\d+)?", str(value or "").strip())
    if not match:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def build_card(request: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    """Carte « Pour ce soir » d'une demande et de ses téléchargements (pur, testé)."""
    size = sum(float(i.get("size_bytes") or 0) for i in items)
    left = sum(float(i.get("size_left_bytes") or 0) for i in items)
    progress = round((size - left) * 100 / size, 1) if size else 0.0
    lefts = [timeleft_seconds(i.get("time_left")) for i in items]
    time_left = max((t for t in lefts if t is not None), default=None)
    tracked = {str(i.get("tracked_state") or "").casefold() for i in items}
    errors = [str(i.get("error") or i.get("detail") or "") for i in items if i.get("error")]
    blocked = [i for i in items if str(i.get("tracked_state") or "").casefold() in _BLOCKED]

    status = request.get("status")
    if status == "done":
        phase = "ready"
    elif status == "expired":
        phase = "notfound"
    elif blocked or errors:
        phase = "blocked"
    elif not items and request.get("subtitles") == "searching":
        phase = "subtitles"  # importé, Bazarr cherche (lot 4)
    elif items and (tracked & _IMPORTING or (size and left <= 0)):
        phase = "importing"
    elif items:
        phase = "downloading"
    elif request.get("grabbed_at"):
        phase = "importing"  # sorti de la file, la demande se ferme dans 3 min
    else:
        phase = "searching"

    first_blocked = blocked[0] if blocked else (items[0] if errors else None)
    return {
        **request,
        "phase": phase,
        "progress": 100.0
        if phase in ("importing", "subtitles", "ready") and not items
        else progress,
        "size_bytes": size,
        "size_left_bytes": left,
        "time_left_seconds": time_left,
        "error": errors[0] if errors else (str(blocked[0].get("detail") or "") if blocked else ""),
        "can_cancel": bool(request.get("mine")) and status == "open",
        # Pour « Débloquer » : le téléchargement en cause
        "blocked_download": {
            "service_type": first_blocked.get("service_type"),
            "download_id": first_blocked.get("download_id"),
        }
        if first_blocked
        else None,
        "items": len(items),
        "quality": next((i.get("quality") for i in items if i.get("quality")), ""),
        "protocol": next((i.get("protocol") for i in items if i.get("protocol")), ""),
    }


def order_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """En cours d'abord (ordre d'arrivée), puis prêtes (les plus récentes), puis le reste."""
    running = sorted(
        (c for c in cards if c["status"] == "open"), key=lambda c: c.get("requested_at") or ""
    )
    ready = sorted(
        (c for c in cards if c["status"] != "open" and c["phase"] == "ready"),
        key=lambda c: c.get("closed_at") or "",
        reverse=True,
    )
    rest = [c for c in cards if c["status"] != "open" and c["phase"] != "ready"]
    return running + ready + rest


async def _art(db: AsyncSession) -> dict[tuple[str, str], dict[str, Any]]:
    """Affiche / fond des titres de la médiathèque (cache 5 min), par (service, id *arr)."""
    try:
        library = await media_aggregator.cached_library(db)
    except Exception as exc:
        logger.debug("Médiathèque indisponible pour les cartes TV : %s", exc)
        return {}
    kinds = {"movie": "radarr", "series": "sonarr"}
    return {(kinds.get(m.get("type"), ""), str(m.get("external_id"))): m for m in library}


async def _sab(db: AsyncSession) -> dict[str, Any] | None:
    svc = (
        (
            await db.execute(
                select(Service).where(
                    Service.is_enabled == True,  # noqa: E712
                    Service.type == "sabnzbd",
                )
            )
        )
        .scalars()
        .first()
    )
    if svc is None:
        return None
    sab = SabnzbdClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))
    try:
        queue = await sab.get_queue()
        return {
            "paused": bool(queue.get("paused")),
            "kbpersec": float(queue.get("kbpersec") or 0),
            "time_left": queue.get("timeleft") or "",
            "slots": int(queue.get("noofslots_total") or len(queue.get("slots") or [])),
        }
    except Exception as exc:
        logger.debug("SABnzbd injoignable pour le tableau TV : %s", exc)
        return None
    finally:
        await sab.close()


async def build_board(
    db: AsyncSession, viewer_device_id: int | None = None, viewer_profile_id: int | None = None
) -> dict[str, Any]:
    """Tout ce que l'écran Téléchargements de la TV affiche."""
    items = await media_aggregator.get_queue_items(db)
    await tv_priority.annotate_queue(db, items)
    requests = await tv_priority.list_requests(db, viewer_device_id, viewer_profile_id)
    art = await _art(db)

    by_request: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("tv_request"):
            by_request.setdefault(item["tv_request"]["id"], []).append(item)

    cards = []
    for req in requests:
        if req["status"] == "cancelled":
            continue
        card = build_card(req, by_request.get(req["id"], []))
        media = art.get((req["service_type"], str(req["arr_id"]))) or {}
        card["poster_url"] = media.get("poster_url") or ""
        card["fanart_url"] = media.get("fanart_url") or ""
        cards.append(card)

    return {
        "tonight": order_cards(cards),
        "queue": [i for i in items if not i.get("tv_request")],
        "sab": await _sab(db),
    }

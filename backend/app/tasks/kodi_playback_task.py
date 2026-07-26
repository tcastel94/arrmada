"""Passive Kodi playback watcher — logs films/episodes started *on Kodi itself*.

Polls the active player every 20s. When a new title appears that Arrmada did not
just launch (no recent ``kodi_play`` from source=arrmada for that TMDB id), it is
recorded as a playback event with source=kodi — so the Activité timeline captures
plays started from the Kodi remote/UI, not only those launched from Arrmada.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.database import async_session_factory
from app.models.activity import ActivityEvent
from app.services import kodi as kodi_service
from app.services.activity_log import log_event
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Last playback signature seen per Kodi device — detects transitions so a play is
# logged once per session, not on every poll. Process-local (resets on restart).
_last_seen: dict[str, str] = {}


async def _recent_arrmada_play(db, tmdb_id: int | None) -> bool:
    """True if Arrmada launched this TMDB on Kodi within the last 2 minutes."""
    if not tmdb_id:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
    stmt = (
        select(ActivityEvent.id)
        .where(
            ActivityEvent.action == "kodi_play",
            ActivityEvent.source == "arrmada",
            ActivityEvent.tmdb_id == tmdb_id,
            ActivityEvent.ts >= cutoff,
        )
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.first() is not None


async def _tick() -> None:
    try:
        async with async_session_factory() as db:
            np = await kodi_service.get_now_playing(db)
            device = np.get("kodi") or "Kodi"

            if not np.get("playing"):
                _last_seen[device] = ""
                return

            tmdb = np.get("tmdb")
            signature = str(tmdb or np.get("title") or "")
            if not signature or signature == _last_seen.get(device):
                return  # same session as last poll → already handled

            _last_seen[device] = signature

            tmdb_int = None
            try:
                tmdb_int = int(tmdb) if tmdb else None
            except (TypeError, ValueError):
                tmdb_int = None

            if await _recent_arrmada_play(db, tmdb_int):
                return  # this play was launched from Arrmada — already logged

            await log_event(
                category="playback",
                action="kodi_play",
                status="info",
                source="kodi",
                media_type=np.get("type") if np.get("type") in ("movie", "series") else None,
                tmdb_id=tmdb_int,
                title=np.get("title"),
                subtitle=np.get("subtitle"),
                device=device,
                detail="Lecture démarrée depuis Kodi",
            )
    except Exception as exc:
        logger.debug("Kodi playback watcher tick failed: %s", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Register the passive Kodi playback watcher."""
    scheduler.add_job(
        _tick,
        trigger="interval",
        seconds=20,
        id="kodi_playback_watch",
        name="Kodi passive playback watcher",
        replace_existing=True,
    )

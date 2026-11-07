"""Passage périodique du gardien des sous-titres (services/subtitle_guardian.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services import subtitle_guardian
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _tick() -> None:
    try:
        await subtitle_guardian.run_once()
    except Exception as exc:  # un passage raté ne doit jamais tuer la minuterie
        logger.warning("Gardien des sous-titres : passage en échec (%s)", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Toutes les SUBTITLE_GUARDIAN_INTERVAL_MINUTES minutes, premier passage
    5 min après le démarrage (laisser Bazarr, Sonarr et Radarr démarrer)."""
    if not settings.SUBTITLE_GUARDIAN_ENABLED:
        logger.info("Gardien des sous-titres désactivé (SUBTITLE_GUARDIAN_ENABLED=false)")
        return
    scheduler.add_job(
        _tick,
        trigger="interval",
        minutes=max(10, settings.SUBTITLE_GUARDIAN_INTERVAL_MINUTES),
        next_run_time=datetime.now(UTC) + timedelta(minutes=5),
        id="subtitle_guardian",
        name="Gardien des sous-titres (recherches à l'avance)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

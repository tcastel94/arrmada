"""Passe périodique du gardien de priorité TV (services/tv_priority.py)."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services import tv_priority
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _tick() -> None:
    """Sans demande TV ouverte, la passe s'arrête à une requête en base."""
    try:
        await tv_priority.enforce()
    except Exception as exc:  # une passe ratée ne doit jamais tuer la minuterie
        logger.warning("Priorité TV : passe en échec (%s)", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Enregistre la passe toutes les TV_PRIORITY_INTERVAL_SECONDS secondes."""
    if not settings.TV_PRIORITY_ENABLED:
        logger.info("Priorité TV désactivée (TV_PRIORITY_ENABLED=false)")
        return
    scheduler.add_job(
        _tick,
        trigger="interval",
        seconds=max(5, settings.TV_PRIORITY_INTERVAL_SECONDS),
        id="tv_priority",
        name="Gardien de priorité des demandes TV",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

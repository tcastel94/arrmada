"""Periodic media requests sync task — runs every 60 seconds."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session_factory
from app.services.request_service import sync_active_requests
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _run_request_sync() -> None:
    """Synchronise active media request statuses with Radarr/Sonarr."""
    logger.debug("Running scheduled media requests sync …")
    async with async_session_factory() as session:
        try:
            await sync_active_requests(session)
            logger.info("Media requests sync complete")
        except Exception as exc:
            logger.error("Scheduled media requests sync failed: %s", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Register the media requests sync job with the scheduler."""
    scheduler.add_job(
        _run_request_sync,
        trigger="interval",
        seconds=60,
        id="requests_sync",
        name="Media requests status sync",
        replace_existing=True,
    )

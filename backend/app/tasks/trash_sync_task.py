"""Periodic TRaSH Guides sync — runs every 24 hours.

Refreshes the TRaSH Guides cache (CFs and QPs) and creates
an in-app notification with the results.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.trash_guides import get_trash_cache
from app.services.notification_service import create_notification_standalone
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _run_trash_sync() -> None:
    """Sync TRaSH Guides data from GitHub."""
    logger.info("Running scheduled TRaSH Guides sync …")
    cache = get_trash_cache()

    try:
        results = await cache.sync(force=False)  # Respects TTL

        # If cache was fresh, results may be empty/minimal
        sonarr_cfs = len(cache.get_custom_formats("sonarr"))
        radarr_cfs = len(cache.get_custom_formats("radarr"))

        logger.info(
            "TRaSH sync complete: Sonarr=%d CFs, Radarr=%d CFs",
            sonarr_cfs,
            radarr_cfs,
        )

        # Create notification
        await create_notification_standalone(
            type="trash_sync",
            title="TRaSH Guides synchronisés",
            message=f"Sonarr : {sonarr_cfs} CFs, Radarr : {radarr_cfs} CFs",
            severity="success",
        )

    except Exception as exc:
        logger.error("Scheduled TRaSH sync failed: %s", exc)
        await create_notification_standalone(
            type="trash_sync",
            title="Échec de la synchronisation TRaSH",
            message=str(exc)[:200],
            severity="error",
        )


def register(scheduler: AsyncIOScheduler) -> None:
    """Register the TRaSH sync job — every 24 hours."""
    scheduler.add_job(
        _run_trash_sync,
        trigger="interval",
        hours=24,
        id="trash_sync",
        name="TRaSH Guides sync",
        replace_existing=True,
    )

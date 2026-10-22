"""APScheduler configuration and lifecycle."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.utils.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the scheduler with all registered jobs."""
    from app.tasks.android_update_task import register as register_android_update
    from app.tasks.artwork_task import register as register_artwork
    from app.tasks.auto_import_task import register as register_auto_import
    from app.tasks.health_check_task import register as register_health_check
    from app.tasks.kodi_playback_task import register as register_kodi_playback
    from app.tasks.request_sync_task import register as register_request_sync
    from app.tasks.trash_sync_task import register as register_trash_sync
    from app.tasks.tv_priority_task import register as register_tv_priority

    register_health_check(scheduler)
    register_trash_sync(scheduler)
    register_request_sync(scheduler)
    register_auto_import(scheduler)
    register_kodi_playback(scheduler)
    register_artwork(scheduler)
    register_tv_priority(scheduler)
    register_android_update(scheduler)

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

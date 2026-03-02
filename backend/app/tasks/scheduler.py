"""APScheduler configuration and lifecycle."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.utils.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the scheduler with all registered jobs."""
    from app.tasks.health_check_task import register as register_health_check
    from app.tasks.trash_sync_task import register as register_trash_sync

    register_health_check(scheduler)
    register_trash_sync(scheduler)

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

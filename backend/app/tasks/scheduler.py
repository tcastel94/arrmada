"""APScheduler configuration and lifecycle."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.utils.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the scheduler with all registered jobs."""
    from app.tasks.health_check_task import register as register_health_check

    register_health_check(scheduler)

    # Phase 4 will add:
    # from app.tasks.sync_media_task import register as register_sync
    # from app.tasks.analytics_snapshot import register as register_analytics
    # from app.tasks.recommendation_refresh import register as register_reco
    # register_sync(scheduler)
    # register_analytics(scheduler)
    # register_reco(scheduler)

    scheduler.start()
    logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

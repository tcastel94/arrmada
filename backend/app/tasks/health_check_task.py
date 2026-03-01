"""Periodic health check task — runs every 60 seconds."""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.database import async_session_factory
from app.services.health_checker import check_all_services
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _run_health_checks() -> None:
    """Execute health checks for all enabled services."""
    logger.debug("Running scheduled health checks …")
    async with async_session_factory() as session:
        try:
            results = await check_all_services(session)
            online = sum(1 for r in results if r["status"] == "online")
            total = len(results)
            logger.info(
                "Health check complete: %d/%d services online", online, total
            )
        except Exception as exc:
            logger.error("Scheduled health check failed: %s", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Register the health check job with the scheduler."""
    scheduler.add_job(
        _run_health_checks,
        trigger="interval",
        seconds=60,
        id="health_check",
        name="Service health check",
        replace_existing=True,
    )

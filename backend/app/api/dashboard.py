"""Dashboard API — stats and overview data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import media_aggregator
from app.utils.cache import cache
from app.utils.helpers import format_bytes

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/stats",
    summary="Dashboard statistics",
    description="Aggregated overview of your media library. Cached for 60 seconds.",
)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Fetch aggregated dashboard statistics (cached 60s)."""

    async def _fetch():
        stats = await media_aggregator.get_dashboard_stats(db)
        stats["total_size_human"] = format_bytes(stats["total_size_bytes"])
        return stats

    return await cache.get_or_set("dashboard_stats", _fetch, ttl_seconds=60)

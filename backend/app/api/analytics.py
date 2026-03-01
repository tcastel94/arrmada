"""Analytics API — library statistics and charts data."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.analytics import get_library_analytics
from app.utils.cache import cache

router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    summary="Library analytics",
    description="Comprehensive library statistics including genre, "
    "quality, and year distributions. Cached for 5 minutes.",
)
async def analytics(db: AsyncSession = Depends(get_db)):
    """Fetch comprehensive library analytics (cached 5 min)."""

    async def _fetch():
        return await get_library_analytics(db)

    return await cache.get_or_set("library_analytics", _fetch, ttl_seconds=300)

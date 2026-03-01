"""Downloads API — unified download queue from all services."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import media_aggregator

router = APIRouter(
    prefix="/api/downloads",
    tags=["downloads"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_downloads(db: AsyncSession = Depends(get_db)):
    """Fetch combined download queue from all Sonarr/Radarr services."""
    items = await media_aggregator.get_queue_items(db)
    return {"items": items, "total": len(items)}

"""Recommendations API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.recommendations import get_recommendations

router = APIRouter(
    prefix="/api/recommendations",
    tags=["recommendations"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def recommendations(db: AsyncSession = Depends(get_db)):
    """Get personalized recommendations based on library analysis."""
    return await get_recommendations(db)

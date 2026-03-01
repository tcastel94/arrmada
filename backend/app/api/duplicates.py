"""Duplicates API — duplicate detection and management."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.duplicates import detect_duplicates

router = APIRouter(
    prefix="/api/duplicates",
    tags=["duplicates"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_duplicates(db: AsyncSession = Depends(get_db)):
    """Detect duplicate media across services."""
    return await detect_duplicates(db)

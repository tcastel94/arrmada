"""Media API — unified media library across all *arr services."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import media_aggregator
from app.services import media_detail

router = APIRouter(
    prefix="/api/media",
    tags=["media"],
    dependencies=[Depends(get_current_user)],
)


# ── Detail endpoints (must be before parameterized routes) ────

@router.get("/movie/{movie_id}")
async def get_movie_detail(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch detailed info for a single movie from Radarr + Bazarr."""
    return await media_detail.get_movie_detail(db, movie_id)


@router.get("/series/{series_id}")
async def get_series_detail(
    series_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch detailed info for a single series from Sonarr + Bazarr."""
    return await media_detail.get_series_detail(db, series_id)


@router.get("/search")
async def search_media(
    q: str = Query(..., description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """Quick search across all media."""
    results = await media_aggregator.search_media(q, db)
    return {"items": results[:30], "total": len(results)}


@router.get("")
async def list_media(
    type: str | None = Query(None, description="Filter by type: movie, series"),
    search: str | None = Query(None, description="Search by title"),
    sort: str = Query("title", description="Sort by: title, year, added, size"),
    order: str = Query("asc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Fetch unified media library with filters and pagination."""
    media = await media_aggregator.fetch_all_media(db)

    # Filter by type
    if type:
        media = [m for m in media if m["type"] == type]

    # Search
    if search:
        q = search.lower()
        media = [m for m in media if q in m.get("title", "").lower()]

    # Sort
    sort_key = sort if sort in ("title", "year", "added", "size_bytes") else "title"
    if sort_key == "size":
        sort_key = "size_bytes"
    reverse = order.lower() == "desc"
    media.sort(key=lambda m: m.get(sort_key) or "", reverse=reverse)

    # Pagination
    total = len(media)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = media[start:end]

    return {
        "items": page_items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    }

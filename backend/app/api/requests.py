"""Requests API — Overseerr-like media request system."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.request_service import create_request, list_requests, delete_request

router = APIRouter(
    prefix="/api/requests",
    tags=["requests"],
    dependencies=[Depends(get_current_user)],
)


class RequestCreate(BaseModel):
    title: str
    type: str  # movie or series
    tmdb_id: int | None = None
    year: int | None = None
    poster_url: str | None = None
    quality_profile: str | None = None


@router.get("")
async def get_requests(db: AsyncSession = Depends(get_db)):
    """List all media requests."""
    requests = await list_requests(db)
    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "type": r.type,
                "tmdb_id": r.tmdb_id,
                "year": r.year,
                "poster_url": r.poster_url,
                "quality_profile": r.quality_profile,
                "status": r.status,
                "target_service": r.target_service,
                "arr_id": r.arr_id,
                "requested_at": r.requested_at.isoformat() if r.requested_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_request(payload: RequestCreate, db: AsyncSession = Depends(get_db)):
    """Submit a new media request."""
    req = await create_request(
        db=db,
        title=payload.title,
        media_type=payload.type,
        tmdb_id=payload.tmdb_id,
        year=payload.year,
        poster_url=payload.poster_url,
        quality_profile=payload.quality_profile,
    )
    return {
        "id": req.id,
        "title": req.title,
        "type": req.type,
        "status": req.status,
        "target_service": req.target_service,
        "arr_id": req.arr_id,
    }


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_request(request_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a media request."""
    deleted = await delete_request(db, request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Request not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

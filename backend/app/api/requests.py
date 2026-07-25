"""Requests API — Overseerr-like media request system."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

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


async def _bg_sync_requests() -> None:
    from app.database import async_session_factory
    from app.services.request_service import sync_active_requests
    from app.utils.logger import get_logger

    logger = get_logger("requests_bg_sync")
    async with async_session_factory() as session:
        try:
            await sync_active_requests(session)
        except Exception as exc:
            logger.error("Background request sync failed: %s", exc)


@router.get("/lookup")
async def lookup_media(
    q: str = Query(..., min_length=2),
    type: str = Query(..., description="movie or series"),
    db: AsyncSession = Depends(get_db),
):
    """Lookup movies/series from Sonarr/Radarr services."""
    if type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Invalid media type")

    target_service = "radarr" if type == "movie" else "sonarr"
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == target_service,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()
    if not service:
        return []

    api_key = decrypt_api_key(service.api_key)
    results = []

    if type == "movie":
        client = RadarrClient(url=service.url, api_key=api_key)
        try:
            raw = await client.lookup_movie(q)
            for item in raw[:15]:
                images = item.get("images", [])
                poster = next((img["remoteUrl"] for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")), None)
                # Radarr sets a non-zero ``id`` when the movie is already added.
                arr_id = item.get("id") or 0
                results.append({
                    "title": item.get("title"),
                    "year": item.get("year"),
                    "tmdb_id": item.get("tmdbId"),
                    "overview": item.get("overview"),
                    "poster_url": poster,
                    "type": "movie",
                    "in_library": arr_id > 0,
                    "arr_id": arr_id or None,
                })
        except Exception as exc:
            logger.error("Radarr lookup failed: %s", exc)
        finally:
            await client.close()
    else:
        client = SonarrClient(url=service.url, api_key=api_key)
        try:
            raw = await client.lookup_series(q)
            for item in raw[:15]:
                images = item.get("images", [])
                poster = next((img["remoteUrl"] for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")), None)
                arr_id = item.get("id") or 0
                results.append({
                    "title": item.get("title"),
                    "year": item.get("year"),
                    "tmdb_id": item.get("tvdbId"),  # Sonarr uses TVDB ID
                    "overview": item.get("overview"),
                    "poster_url": poster,
                    "type": "series",
                    "in_library": arr_id > 0,
                    "arr_id": arr_id or None,
                })
        except Exception as exc:
            logger.error("Sonarr lookup failed: %s", exc)
        finally:
            await client.close()

    return results


@router.get("")
async def get_requests(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """List all media requests."""
    background_tasks.add_task(_bg_sync_requests)
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

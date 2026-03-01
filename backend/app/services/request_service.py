"""Media request service — add media to *arr services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.request import MediaRequest
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.services.telegram import notify_new_media
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_request(
    db: AsyncSession,
    title: str,
    media_type: str,
    tmdb_id: int | None = None,
    year: int | None = None,
    poster_url: str | None = None,
    quality_profile: str | None = None,
) -> MediaRequest:
    """Create a new media request and attempt to add it to the target service."""
    target = "radarr" if media_type == "movie" else "sonarr"

    req = MediaRequest(
        title=title,
        type=media_type,
        tmdb_id=tmdb_id,
        year=year,
        poster_url=poster_url,
        quality_profile=quality_profile,
        status="requested",
        target_service=target,
    )
    db.add(req)
    await db.flush()

    # Try to auto-add to the target *arr service
    try:
        await _send_to_arr(db, req)
    except Exception as exc:
        logger.error("Failed to auto-add request %s: %s", title, exc)
        req.status = "failed"

    await db.commit()
    await db.refresh(req)

    # Telegram notification
    try:
        await notify_new_media(req.title, req.type, req.year)
    except Exception:
        pass

    return req


async def _send_to_arr(db: AsyncSession, req: MediaRequest) -> None:
    """Send the request to the appropriate *arr service."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == req.target_service,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()

    if not service:
        req.status = "failed"
        logger.warning("No %s service configured for request %s", req.target_service, req.title)
        return

    api_key = decrypt_api_key(service.api_key)

    if req.target_service == "radarr":
        client = RadarrClient(url=service.url, api_key=api_key)
        try:
            # Lookup via TMDB if we have a tmdb_id, else by title
            if req.tmdb_id:
                results = await client.lookup_movie(f"tmdb:{req.tmdb_id}")
            else:
                results = await client.lookup_movie(req.title)

            if not results:
                req.status = "failed"
                return

            movie_data = results[0]
            tmdb_id = movie_data.get("tmdbId", req.tmdb_id)

            # ── Duplicate check: see if this movie already exists in Radarr ──
            existing_movies = await client.get_movies()
            for existing in existing_movies:
                if existing.get("tmdbId") == tmdb_id:
                    req.status = "available" if existing.get("hasFile") else "searching"
                    req.arr_id = existing.get("id")
                    logger.info("Movie %s already exists in Radarr (id=%s)", req.title, req.arr_id)
                    return

            # Get root folder and quality profile
            root_folders = await client.get_root_folders()
            quality_profiles = await client.get_quality_profiles()

            if not root_folders or not quality_profiles:
                req.status = "failed"
                return

            add_payload = {
                "title": movie_data.get("title", req.title),
                "tmdbId": tmdb_id,
                "year": movie_data.get("year", req.year),
                "qualityProfileId": quality_profiles[0]["id"],
                "rootFolderPath": root_folders[0]["path"],
                "monitored": True,
                "addOptions": {"searchForMovie": True},
                "images": movie_data.get("images", []),
            }

            added = await client.add_movie(add_payload)
            req.arr_id = added.get("id")
            req.status = "searching"
            logger.info("Added movie %s to Radarr (id=%s)", req.title, req.arr_id)
        finally:
            await client.close()

    elif req.target_service == "sonarr":
        client = SonarrClient(url=service.url, api_key=api_key)
        try:
            if req.tmdb_id:
                results = await client.lookup_series(f"tvdb:{req.tmdb_id}")
            else:
                results = await client.lookup_series(req.title)

            if not results:
                req.status = "failed"
                return

            series_data = results[0]

            root_folders = await client.get_root_folders()
            quality_profiles = await client.get_quality_profiles()

            if not root_folders or not quality_profiles:
                req.status = "failed"
                return

            add_payload = {
                "title": series_data.get("title", req.title),
                "tvdbId": series_data.get("tvdbId"),
                "year": series_data.get("year", req.year),
                "qualityProfileId": quality_profiles[0]["id"],
                "rootFolderPath": root_folders[0]["path"],
                "monitored": True,
                "addOptions": {"searchForMissingEpisodes": True},
                "images": series_data.get("images", []),
                "seasonFolder": True,
            }

            added = await client.add_series(add_payload)
            req.arr_id = added.get("id")
            req.status = "searching"
            logger.info("Added series %s to Sonarr (id=%s)", req.title, req.arr_id)
        finally:
            await client.close()


async def list_requests(db: AsyncSession) -> list[MediaRequest]:
    """List all media requests, newest first."""
    stmt = select(MediaRequest).order_by(MediaRequest.requested_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_request(db: AsyncSession, request_id: int) -> bool:
    """Delete a media request."""
    stmt = select(MediaRequest).where(MediaRequest.id == request_id)
    result = await db.execute(stmt)
    req = result.scalar_one_or_none()
    if not req:
        return False
    await db.delete(req)
    await db.commit()
    return True

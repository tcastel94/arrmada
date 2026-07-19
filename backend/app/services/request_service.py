"""Media request service — add media to *arr services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
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


def _resolve_quality_profile_id(profiles: list[dict], name: str | None) -> int:
    """Return the id of the profile matching ``name`` (case-insensitive).

    Falls back to the first available profile when no name is given or no
    match is found, mirroring the previous ``profiles[0]`` behaviour.
    """
    if name:
        for p in profiles:
            if str(p.get("name", "")).strip().lower() == name.strip().lower():
                return p["id"]
    return profiles[0]["id"]



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
                "qualityProfileId": _resolve_quality_profile_id(quality_profiles, req.quality_profile),
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
                "qualityProfileId": _resolve_quality_profile_id(quality_profiles, req.quality_profile),
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


async def sync_active_requests(db: AsyncSession) -> None:
    """Sync the status of active requests with Radarr/Sonarr."""
    # Find all requests that are not completed (status is not available/failed)
    stmt = select(MediaRequest).where(
        MediaRequest.status.in_(["requested", "searching", "downloading"])
    )
    result = await db.execute(stmt)
    requests = list(result.scalars().all())

    if not requests:
        return

    # Find services
    services_stmt = select(Service).where(Service.is_enabled == True)  # noqa: E712
    services_result = await db.execute(services_stmt)
    services = {s.type: s for s in services_result.scalars().all()}

    # Group requests by target service
    radarr_requests = [r for r in requests if r.target_service == "radarr"]
    sonarr_requests = [r for r in requests if r.target_service == "sonarr"]

    # Sync Radarr requests
    if radarr_requests and "radarr" in services:
        svc = services["radarr"]
        api_key = decrypt_api_key(svc.api_key)
        client = RadarrClient(url=svc.url, api_key=api_key)
        try:
            queue_data = {}
            try:
                queue_data = await client.get_queue()
            except Exception as exc:
                logger.error("Failed to get Radarr queue: %s", exc)

            queue_items = queue_data.get("records", [])
            downloading_movie_ids = {
                item["movieId"] for item in queue_items if "movieId" in item
            }

            for req in radarr_requests:
                if not req.arr_id:
                    # Try to retrieve arr_id via lookup
                    try:
                        if req.tmdb_id:
                            results = await client.lookup_movie(f"tmdb:{req.tmdb_id}")
                        else:
                            results = await client.lookup_movie(req.title)
                        if results:
                            existing_movies = await client.get_movies()
                            movie_tmdb = results[0].get("tmdbId", req.tmdb_id)
                            for existing in existing_movies:
                                if existing.get("tmdbId") == movie_tmdb:
                                    req.arr_id = existing.get("id")
                                    break
                    except Exception as lookup_exc:
                        logger.error("Radarr lookup failed during sync for %s: %s", req.title, lookup_exc)

                if req.arr_id:
                    try:
                        movie = await client.get_movie_by_id(req.arr_id)
                        if movie.get("hasFile"):
                            req.status = "available"
                            req.completed_at = datetime.now(timezone.utc)
                        elif req.arr_id in downloading_movie_ids:
                            req.status = "downloading"
                        else:
                            req.status = "searching"
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 404:
                            req.status = "failed"
                            logger.warning("Movie %s (arr_id=%s) not found in Radarr, marking as failed", req.title, req.arr_id)
                        else:
                            logger.error("Failed to sync Radarr movie %s: %s", req.title, exc)
                    except Exception as exc:
                        logger.error("Failed to sync Radarr movie %s: %s", req.title, exc)
        finally:
            await client.close()

    # Sync Sonarr requests
    if sonarr_requests and "sonarr" in services:
        svc = services["sonarr"]
        api_key = decrypt_api_key(svc.api_key)
        client = SonarrClient(url=svc.url, api_key=api_key)
        try:
            queue_data = {}
            try:
                queue_data = await client.get_queue()
            except Exception as exc:
                logger.error("Failed to get Sonarr queue: %s", exc)

            queue_items = queue_data.get("records", [])
            downloading_series_ids = {
                item["seriesId"] for item in queue_items if "seriesId" in item
            }

            for req in sonarr_requests:
                if not req.arr_id:
                    try:
                        if req.tmdb_id:
                            results = await client.lookup_series(f"tvdb:{req.tmdb_id}")
                        else:
                            results = await client.lookup_series(req.title)
                        if results:
                            existing_series = await client.get_series()
                            series_tvdb = results[0].get("tvdbId")
                            for existing in existing_series:
                                if existing.get("tvdbId") == series_tvdb:
                                    req.arr_id = existing.get("id")
                                    break
                    except Exception as lookup_exc:
                        logger.error("Sonarr lookup failed during sync for %s: %s", req.title, lookup_exc)

                if req.arr_id:
                    try:
                        series = await client.get_series_by_id(req.arr_id)
                        stats = series.get("statistics") or {}
                        episode_file_count = stats.get("episodeFileCount", 0)
                        episode_count = stats.get("episodeCount", 0)

                        if episode_file_count == episode_count and episode_count > 0:
                            req.status = "available"
                            req.completed_at = datetime.now(timezone.utc)
                        elif req.arr_id in downloading_series_ids:
                            req.status = "downloading"
                        elif episode_file_count > 0:
                            req.status = "available"
                            req.completed_at = datetime.now(timezone.utc)
                        else:
                            req.status = "searching"
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code == 404:
                            req.status = "failed"
                            logger.warning("Series %s (arr_id=%s) not found in Sonarr, marking as failed", req.title, req.arr_id)
                        else:
                            logger.error("Failed to sync Sonarr series %s: %s", req.title, exc)
                    except Exception as exc:
                        logger.error("Failed to sync Sonarr series %s: %s", req.title, exc)
        finally:
            await client.close()

    await db.commit()

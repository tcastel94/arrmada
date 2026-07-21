"""Media API — unified media library across all *arr services."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.services import media_aggregator
from app.services import media_detail
from app.services.scraper_service import scrape_movies
from app.utils.logger import get_logger

logger = get_logger(__name__)
from app.utils.cache import cache

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


@router.delete("/{type}/{id}")
async def delete_media(
    type: str,
    id: int,
    delete_files: bool = Query(True, description="Delete media files from disk"),
    delete_downloads: bool = Query(True, description="Delete downloads from client queue and history"),
    db: AsyncSession = Depends(get_db),
):
    """Delete a movie or series from Radarr/Sonarr, optionally deleting files and downloads."""
    if type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Invalid media type")

    # 1. Fetch SABnzbd client if delete_downloads is True
    sab_client = None
    if delete_downloads:
        stmt = select(Service).where(
            Service.is_enabled == True,  # noqa: E712
            Service.type == "sabnzbd",
        )
        res = await db.execute(stmt)
        sab_service = res.scalars().first()
        if sab_service:
            from app.services.sabnzbd import SabnzbdClient
            try:
                sab_key = decrypt_api_key(sab_service.api_key)
                sab_client = SabnzbdClient(url=sab_service.url, api_key=sab_key)
            except Exception as exc:
                logger.error("Failed to initialize SABnzbd client: %s", exc)

    target_service = "radarr" if type == "movie" else "sonarr"
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == target_service,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()

    if not service:
        raise HTTPException(status_code=400, detail=f"No {target_service} service configured")

    api_key = decrypt_api_key(service.api_key)
    client = None

    try:
        if type == "movie":
            client = RadarrClient(url=service.url, api_key=api_key)
        else:
            client = SonarrClient(url=service.url, api_key=api_key)

        # 2. Clean up downloads if requested
        if delete_downloads:
            # A. Clean active items in Radarr/Sonarr queue
            try:
                queue_data = await client.get_queue()
                records = queue_data.get("records", []) if isinstance(queue_data, dict) else []
                for item in records:
                    match = False
                    if type == "movie" and item.get("movieId") == id:
                        match = True
                    elif type == "series" and item.get("seriesId") == id:
                        match = True
                    
                    if match and item.get("id"):
                        q_id = item["id"]
                        # Delete from queue and remove from download client
                        await client.delete(f"/queue/{q_id}", params={"removeFromClient": "true", "blocklist": "false"})
            except Exception as exc:
                logger.error("Failed to clean queue for %s %d: %s", type, id, exc)

            # B. Clean SABnzbd queue & history based on Radarr/Sonarr history records
            if sab_client:
                try:
                    history_data = await client.get("/history", params={"movieId" if type == "movie" else "seriesId": id, "pageSize": 200})
                    records = history_data.get("records", []) if isinstance(history_data, dict) else []
                    download_ids = {r.get("downloadId") for r in records if r.get("downloadId")}
                    for dl_id in download_ids:
                        try:
                            await sab_client._call("queue", {"name": "delete", "value": dl_id})
                        except Exception:
                            pass
                        try:
                            await sab_client._call("history", {"name": "delete", "value": dl_id})
                        except Exception:
                            pass
                except Exception as exc:
                    logger.error("Failed to clean SABnzbd history for %s %d: %s", type, id, exc)

        # 3. Delete the movie or series itself
        try:
            if type == "movie":
                await client.delete_movie(movie_id=id, delete_files=delete_files)
            else:
                await client.delete_series(series_id=id, delete_files=delete_files)
        except Exception as exc:
            exc_str = str(exc)
            if "not found" in exc_str.lower() or "404" in exc_str or "return 1 rows" in exc_str:
                logger.warning("%s %d already deleted or not found in service: %s", type.capitalize(), id, exc)
            else:
                raise exc

    except Exception as exc:
        logger.error("Failed to delete %s %d: %s", type, id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if client:
            await client.close()
        if sab_client:
            await sab_client.close()

    # Clear cached media list
    cache.invalidate("media:all")

    return {"status": "deleted"}


@router.post("/scrape")
async def trigger_scrape(
    payload: dict,
    background_tasks: BackgroundTasks,
):
    """Trigger a background metadata scrape for selected items."""
    items = payload.get("items", [])
    background_tasks.add_task(scrape_movies, items)
    return {"status": "scraping started", "items_count": len(items)}



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
    """Fetch unified media library with filters and pagination (cached 5min)."""
    # Cache the full media fetch (expensive API calls to Sonarr/Radarr)
    async def _fetch():
        return await media_aggregator.fetch_all_media(db)

    media = list(await cache.get_or_set("media:all", _fetch, ttl_seconds=300))

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


from pydantic import BaseModel

class MoveMediaPayload(BaseModel):
    new_path: str


@router.get("/{type}/{id}/rootfolders")
async def get_media_rootfolders(
    type: str,
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch available root folders in Radarr/Sonarr."""
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
        raise HTTPException(status_code=400, detail=f"No {target_service} service configured")

    api_key = decrypt_api_key(service.api_key)
    client = None
    try:
        if type == "movie":
            client = RadarrClient(url=service.url, api_key=api_key)
        else:
            client = SonarrClient(url=service.url, api_key=api_key)

        return await client.get("/rootfolder")
    except Exception as exc:
        logger.error("Failed to fetch root folders for %s: %s", type, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if client:
            await client.close()


@router.put("/{type}/{id}/path")
async def update_media_path(
    type: str,
    id: int,
    payload: MoveMediaPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update path of movie or series in Radarr/Sonarr and trigger file moving."""
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
        raise HTTPException(status_code=400, detail=f"No {target_service} service configured")

    api_key = decrypt_api_key(service.api_key)
    client = None
    try:
        if type == "movie":
            client = RadarrClient(url=service.url, api_key=api_key)
            # 1. Fetch current movie
            movie = await client.get(f"/movie/{id}")
            # 2. Modify path
            movie["path"] = payload.new_path
            # 3. PUT update with moveFiles=true
            res = await client.put(f"/movie?moveFiles=true", data=movie)
            logger.info("Updated movie %d path to %s and triggered move", id, payload.new_path)
            return {"success": True, "path": payload.new_path, "response": res}
        else:
            client = SonarrClient(url=service.url, api_key=api_key)
            # 1. Fetch current series
            series = await client.get(f"/series/{id}")
            # 2. Modify path
            series["path"] = payload.new_path
            # 3. PUT update with moveFiles=true
            res = await client.put(f"/series?moveFiles=true", data=series)
            logger.info("Updated series %d path to %s and triggered move", id, payload.new_path)
            return {"success": True, "path": payload.new_path, "response": res}

    except Exception as exc:
        logger.error("Failed to update path for %s %d: %s", type, id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if client:
            await client.close()
        # Invalidate cache
        cache.invalidate("media:all")


# ── Search & interactive grab (native *arr) ───────────────────

async def _get_arr_client_for(db: AsyncSession, media_type: str, *, timeout: int = 10):
    """Resolve the enabled Radarr/Sonarr client for a media type."""
    if media_type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Invalid media type")

    target_service = "radarr" if media_type == "movie" else "sonarr"
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == target_service,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()
    if not service:
        raise HTTPException(status_code=400, detail=f"No {target_service} service configured")

    api_key = decrypt_api_key(service.api_key)
    if media_type == "movie":
        return RadarrClient(url=service.url, api_key=api_key, timeout=timeout)
    return SonarrClient(url=service.url, api_key=api_key, timeout=timeout)


def _normalise_release(r: dict) -> dict:
    """Normalise a Radarr/Sonarr release object for the frontend."""
    quality = (r.get("quality") or {}).get("quality") or {}
    return {
        "guid": r.get("guid"),
        "indexer_id": r.get("indexerId"),
        "indexer": r.get("indexer", ""),
        "title": r.get("title", ""),
        "size_bytes": r.get("size", 0),
        "seeders": r.get("seeders"),
        "leechers": r.get("leechers"),
        "age_days": r.get("age", 0),
        "quality": quality.get("name", "Unknown"),
        "custom_format_score": r.get("customFormatScore", 0),
        "custom_formats": [cf.get("name", "") for cf in r.get("customFormats", []) if isinstance(cf, dict)],
        "protocol": r.get("protocol", "unknown"),
        "rejected": r.get("rejected", False),
        "rejections": r.get("rejections", []) or [],
        "download_url": r.get("downloadUrl"),
        "info_url": r.get("infoUrl"),
    }


class GrabReleasePayload(BaseModel):
    guid: str
    indexer_id: int


@router.post("/{type}/{id}/search")
async def trigger_media_search(
    type: str,
    id: int,
    season: int | None = Query(None, description="Series only: limit the search to one season"),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a native automatic search in Radarr/Sonarr for this media."""
    client = await _get_arr_client_for(db, type)
    try:
        if type == "movie":
            result = await client.search_movie(id)
        elif season is not None:
            result = await client.search_season(id, season)
        else:
            result = await client.search_series(id)
        return {"status": "search_triggered", "command": result}
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Search trigger timed out for %s %d: %s", type, id, type(exc).__name__)
        raise HTTPException(
            status_code=504,
            detail="Le service *arr a mis trop de temps à répondre au lancement de la recherche.",
        )
    except Exception as exc:
        logger.error(
            "Failed to trigger search for %s %d: %s: %s",
            type, id, type(exc).__name__, exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Échec du lancement de la recherche ({type(exc).__name__}).",
        )
    finally:
        await client.close()


@router.get("/{type}/{id}/releases")
async def list_media_releases(
    type: str,
    id: int,
    season: int | None = Query(None, description="Series only: season to search (required for series)"),
    db: AsyncSession = Depends(get_db),
):
    """Interactive search: list candidate releases sorted best-first.

    For series a ``season`` is required — Sonarr ignores ``seriesId`` alone
    and returns a generic, unfiltered set otherwise.
    """
    if type == "series" and season is None:
        raise HTTPException(
            status_code=400,
            detail="A season number is required for interactive series search",
        )
    # Indexer searches can be slow. A Sonarr interactive *season* search
    # fans out into a season-pack search plus one search per episode, so a
    # 10-13 episode season easily needs 100s+; give series a wide budget.
    # (Very large anime seasons may still exceed this and return a clean 504.)
    search_timeout = 240 if type == "series" else 120
    client = await _get_arr_client_for(db, type, timeout=search_timeout)
    try:
        if type == "movie":
            raw = await client.get_releases(id)
        else:
            raw = await client.get_releases(id, season)
        releases = [_normalise_release(r) for r in raw if isinstance(r, dict)]
        releases.sort(
            key=lambda x: (
                x["rejected"],
                -(x["custom_format_score"] or 0),
                -(x["seeders"] or 0),
                x["age_days"] or 0,
            )
        )
        return {"items": releases, "total": len(releases)}
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        logger.warning(
            "Interactive search timed out for %s %d (season=%s): %s",
            type, id, season, type(exc).__name__,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "La recherche a expiré : l'indexeur a mis trop de temps à répondre. "
                "Un ou plusieurs indexeurs sont probablement lents ou hors service — "
                "réessayez, ou désactivez les indexeurs défaillants dans Prowlarr/Sonarr."
            ),
        )
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "").strip()[:300]
        logger.error(
            "Indexer search failed for %s %d (season=%s): HTTP %s %s",
            type, id, season, exc.response.status_code, body,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Le service *arr a renvoyé une erreur {exc.response.status_code} lors de la recherche.",
        )
    except Exception as exc:
        logger.error(
            "Failed to fetch releases for %s %d (season=%s): %s: %s",
            type, id, season, type(exc).__name__, exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Échec de la recherche interactive ({type(exc).__name__}).",
        )
    finally:
        await client.close()


@router.post("/{type}/{id}/grab")
async def grab_media_release(
    type: str,
    id: int,
    payload: GrabReleasePayload,
    db: AsyncSession = Depends(get_db),
):
    """Grab a specific release via the native *arr release endpoint (managed import)."""
    client = await _get_arr_client_for(db, type, timeout=60)
    try:
        result = await client.grab_release(payload.guid, payload.indexer_id)
        return {"status": "grabbed", "release": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to grab release for %s %d: %s", type, id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


# ── Media editing (monitored / quality profile / tags / …) ────

@router.get("/options/{type}")
async def get_media_edit_options(
    type: str,
    db: AsyncSession = Depends(get_db),
):
    """Expose quality profiles + tags for the edit UI (Radarr/Sonarr)."""
    client = await _get_arr_client_for(db, type)
    try:
        profiles = await client.get_quality_profiles()
        tags = await client.get_tags()
        return {
            "quality_profiles": [
                {"id": p.get("id"), "name": p.get("name")} for p in profiles
            ],
            "tags": [{"id": t.get("id"), "label": t.get("label")} for t in tags],
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch edit options for %s: %s", type, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


class CreateTagPayload(BaseModel):
    label: str


@router.post("/tag/{type}")
async def create_media_tag(
    type: str,
    payload: CreateTagPayload,
    db: AsyncSession = Depends(get_db),
):
    """Create a new tag in Radarr/Sonarr."""
    client = await _get_arr_client_for(db, type)
    try:
        tag = await client.create_tag(payload.label)
        return {"id": tag.get("id"), "label": tag.get("label")}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create tag for %s: %s", type, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


class MediaEditPayload(BaseModel):
    monitored: bool | None = None
    quality_profile_id: int | None = None
    tags: list[int] | None = None
    minimum_availability: str | None = None  # movie only
    series_type: str | None = None  # series only


@router.patch("/{type}/{id}")
async def update_media(
    type: str,
    id: int,
    payload: MediaEditPayload,
    db: AsyncSession = Depends(get_db),
):
    """Update editable fields of a movie/series in Radarr/Sonarr.

    Fetches the current object, applies only the provided fields, then
    PUTs the full object back (as required by the *arr APIs).
    """
    client = await _get_arr_client_for(db, type)
    try:
        if type == "movie":
            obj = await client.get_movie_by_id(id)
            if payload.monitored is not None:
                obj["monitored"] = payload.monitored
            if payload.quality_profile_id is not None:
                obj["qualityProfileId"] = payload.quality_profile_id
            if payload.tags is not None:
                obj["tags"] = payload.tags
            if payload.minimum_availability is not None:
                obj["minimumAvailability"] = payload.minimum_availability
            updated = await client.update_movie(id, obj)
        else:
            obj = await client.get_series_by_id(id)
            if payload.monitored is not None:
                obj["monitored"] = payload.monitored
            if payload.quality_profile_id is not None:
                obj["qualityProfileId"] = payload.quality_profile_id
            if payload.tags is not None:
                obj["tags"] = payload.tags
            if payload.series_type is not None:
                obj["seriesType"] = payload.series_type
            updated = await client.update_series(id, obj)

        cache.invalidate("media:all")
        return {
            "status": "updated",
            "monitored": updated.get("monitored"),
            "quality_profile_id": updated.get("qualityProfileId"),
            "tags": updated.get("tags", []),
            "minimum_availability": updated.get("minimumAvailability"),
            "series_type": updated.get("seriesType"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update %s %d: %s", type, id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


class SeasonMonitorPayload(BaseModel):
    monitored: bool


@router.patch("/series/{id}/season/{n}")
async def update_season_monitoring(
    id: int,
    n: int,
    payload: SeasonMonitorPayload,
    db: AsyncSession = Depends(get_db),
):
    """Toggle monitoring for a single season of a series."""
    client = await _get_arr_client_for(db, "series")
    try:
        updated = await client.set_season_monitored(id, n, payload.monitored)
        cache.invalidate("media:all")
        seasons = [
            {"season_number": s.get("seasonNumber"), "monitored": s.get("monitored")}
            for s in (updated.get("seasons") or [])
        ]
        return {"status": "updated", "season": n, "monitored": payload.monitored, "seasons": seasons}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to update season %d monitoring for series %d: %s", n, id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()

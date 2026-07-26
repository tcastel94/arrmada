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


@router.get("/person/{person_id}")
async def get_person_filmography(
    person_id: int,
    db: AsyncSession = Depends(get_db),
):
    """An actor's movie filmography, split into library-owned vs discoverable."""
    from app.services import people

    return await people.get_person_filmography(db, person_id)


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

    from app.services.activity_log import log_event
    await log_event(
        category="library",
        action="delete",
        status="ok",
        source="arrmada",
        media_type=type,
        media_id=id,
        meta={"delete_files": delete_files, "delete_downloads": delete_downloads},
    )

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



@router.get("/facets")
async def media_facets(db: AsyncSession = Depends(get_db)):
    """Distinct filter values across the whole library (for filter dropdowns).

    Returns the sorted list of genres and (file) qualities present in the
    library, plus how many items are missing (no file) — used to populate the
    médiathèque filter bar and the "Manquants" badge without loading every page.
    """
    async def _fetch():
        return await media_aggregator.fetch_all_media(db)

    media = list(await cache.get_or_set("media:all", _fetch, ttl_seconds=300))

    genres: set[str] = set()
    qualities: set[str] = set()
    for m in media:
        for g in m.get("genres") or []:
            if g:
                genres.add(g)
        q = m.get("quality")
        # Only movies expose a human quality name; series store a profile id (int).
        if isinstance(q, str) and q:
            qualities.add(q)

    missing = [m for m in media if not m.get("has_file")]
    return {
        "genres": sorted(genres, key=str.lower),
        "qualities": sorted(qualities, key=str.lower),
        "total": len(media),
        "missing_count": len(missing),
        "missing_monitored_count": len([m for m in missing if m.get("monitored")]),
    }


@router.get("")
async def list_media(
    type: str | None = Query(None, description="Filter by type: movie, series"),
    search: str | None = Query(None, description="Search by title"),
    sort: str = Query("title", description="Sort by: title, year, added, size"),
    order: str = Query("asc", description="Sort order: asc or desc"),
    genre: str | None = Query(None, description="Filter by a single genre"),
    quality: str | None = Query(None, description="Filter by a file quality name"),
    availability: str | None = Query(
        None, description="Filter by file presence: available | missing"
    ),
    monitored: bool | None = Query(None, description="Filter by monitored flag"),
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

    # Availability (file presence)
    if availability == "available":
        media = [m for m in media if m.get("has_file")]
    elif availability == "missing":
        media = [m for m in media if not m.get("has_file")]

    # Monitored flag
    if monitored is not None:
        media = [m for m in media if bool(m.get("monitored")) == monitored]

    # Genre (single)
    if genre:
        media = [m for m in media if genre in (m.get("genres") or [])]

    # Quality (file quality name; movies only in practice)
    if quality:
        media = [m for m in media if m.get("quality") == quality]

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
    title: str | None = None
    release_title: str | None = None


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
        from app.services.activity_log import log_event
        await log_event(
            category="library",
            action="search",
            source="arrmada",
            media_type=type,
            media_id=id,
            subtitle=f"Saison {season}" if season is not None else None,
        )
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


class EpisodeSearchPayload(BaseModel):
    episode_ids: list[int]


@router.post("/series/{id}/search-episodes")
async def trigger_episode_search(
    id: int,
    payload: EpisodeSearchPayload,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a native automatic search for specific episodes.

    Used by the "search missing episodes" buttons: Sonarr searches the given
    episodes and auto-grabs the best matching release per the quality profile.
    """
    if not payload.episode_ids:
        raise HTTPException(status_code=400, detail="episode_ids is required")
    client = await _get_arr_client_for(db, "series", timeout=30)
    try:
        result = await client.search_episodes(payload.episode_ids)
        return {
            "status": "search_triggered",
            "command": result,
            "count": len(payload.episode_ids),
        }
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        logger.warning("Episode search timed out for series %d: %s", id, type(exc).__name__)
        raise HTTPException(
            status_code=504,
            detail="Sonarr a mis trop de temps à répondre au lancement de la recherche.",
        )
    except Exception as exc:
        logger.error(
            "Failed to trigger episode search for series %d: %s: %s",
            id, type(exc).__name__, exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Échec du lancement de la recherche des épisodes ({type(exc).__name__}).",
        )
    finally:
        await client.close()


@router.get("/series/{id}/search-activity")
async def get_series_search_activity(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Report which episodes/seasons of a series have a search running in Sonarr.

    Backs the "recherche en cours" indicator: the frontend polls this and
    matches the returned episode ids against each season's episodes. Note that
    ``EpisodeSearch`` commands are global (no seriesId in the body), so we
    return the union of every active search's episode ids — the frontend
    intersects them with this series' episodes, which filters other series out.
    """
    client = await _get_arr_client_for(db, "series", timeout=15)
    active_states = {"queued", "started"}
    episode_ids: set[int] = set()
    seasons: set[int] = set()
    series_search = False
    try:
        commands = await client.get_commands()
        for c in commands if isinstance(commands, list) else []:
            if c.get("status") not in active_states:
                continue
            name = c.get("name")
            body = c.get("body") or {}
            if name == "EpisodeSearch":
                episode_ids.update(int(e) for e in (body.get("episodeIds") or []))
            elif name == "SeasonSearch" and body.get("seriesId") == id:
                sn = body.get("seasonNumber")
                if sn is not None:
                    seasons.add(int(sn))
            elif name == "SeriesSearch" and body.get("seriesId") == id:
                series_search = True
        return {
            "episode_ids": sorted(episode_ids),
            "seasons": sorted(seasons),
            "series_search": series_search,
            "active": bool(episode_ids or seasons or series_search),
        }
    except Exception as exc:
        # A polling endpoint must never break the page; degrade to "idle".
        logger.warning("Failed to fetch search activity for series %d: %s", id, exc)
        return {"episode_ids": [], "seasons": [], "series_search": False, "active": False}
    finally:
        await client.close()


@router.get("/{type}/{id}/releases")
async def list_media_releases(
    type: str,
    id: int,
    season: int | None = Query(None, description="Series only: season-pack search for this season"),
    episode: int | None = Query(None, description="Series only: Sonarr episode id — search just this episode (fast)"),
    db: AsyncSession = Depends(get_db),
):
    """Interactive search: list candidate releases sorted best-first.

    For series either a ``season`` (season-pack search) or an ``episode`` id
    (single-episode search) is required — Sonarr ignores ``seriesId`` alone and
    returns a generic, unfiltered set otherwise. A single-episode search is
    much faster and is the recommended path for very large (anime) seasons.
    """
    if type == "series" and season is None and episode is None:
        raise HTTPException(
            status_code=400,
            detail="A season number or episode id is required for interactive series search",
        )
    # A single-episode search is one query per indexer (fast, ~30s even on a
    # 500-episode anime). A *season* search fans out into a season-pack query
    # plus one query per episode, so a 10-13 episode season easily needs 100s+
    # and huge anime seasons can exceed even 240s (→ a clean 504). Budget
    # accordingly so the fast path isn't penalised by the slow path's ceiling.
    search_timeout = 240 if (type == "series" and episode is None) else 120
    client = await _get_arr_client_for(db, type, timeout=search_timeout)
    try:
        if type == "movie":
            raw = await client.get_releases(id)
        elif episode is not None:
            raw = await client.get_releases_for_episode(episode)
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
            "Interactive search timed out for %s %d (season=%s episode=%s): %s",
            type, id, season, episode, type(exc).__name__,
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
            "Indexer search failed for %s %d (season=%s episode=%s): HTTP %s %s",
            type, id, season, episode, exc.response.status_code, body,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Le service *arr a renvoyé une erreur {exc.response.status_code} lors de la recherche.",
        )
    except Exception as exc:
        logger.error(
            "Failed to fetch releases for %s %d (season=%s episode=%s): %s: %s",
            type, id, season, episode, type(exc).__name__, exc,
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
    from app.services.activity_log import log_event
    try:
        result = await client.grab_release(payload.guid, payload.indexer_id)
        await log_event(
            category="download",
            action="grab",
            source="arrmada",
            media_type=type,
            media_id=id,
            title=payload.title,
            subtitle=payload.release_title,
        )
        return {"status": "grabbed", "release": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to grab release for %s %d: %s", type, id, exc)
        await log_event(
            category="download", action="grab", status="ko", source="arrmada",
            media_type=type, media_id=id, title=payload.title, detail=str(exc),
        )
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

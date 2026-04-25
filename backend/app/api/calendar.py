"""Calendar API — upcoming episodes and movies from Sonarr/Radarr."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)


async def _fetch_calendar_data(db: AsyncSession, start: str, end: str) -> list[dict[str, Any]]:
    """Fetch calendar entries from all Sonarr/Radarr instances."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    entries: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
                try:
                    episodes = await client.get_calendar(start=start, end=end)
                    for ep in episodes:
                        series_title = ep.get("series", {}).get("title", "Unknown")
                        images = ep.get("series", {}).get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )
                        entries.append({
                            "id": f"sonarr-{ep.get('id')}",
                            "title": series_title,
                            "subtitle": ep.get("title", ""),
                            "type": "episode",
                            "season": ep.get("seasonNumber"),
                            "episode": ep.get("episodeNumber"),
                            "label": f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}",
                            "air_date": ep.get("airDateUtc") or ep.get("airDate"),
                            "has_file": ep.get("hasFile", False),
                            "monitored": ep.get("monitored", False),
                            "poster_url": poster,
                            "overview": ep.get("overview", ""),
                            "service": svc.name,
                            "service_type": "sonarr",
                            "series_id": ep.get("seriesId"),
                        })
                finally:
                    await client.close()

            elif svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
                try:
                    # Radarr calendar endpoint
                    movies = await client.get(
                        "/calendar",
                        params={"start": start, "end": end, "unmonitored": "false"},
                    )
                    for movie in movies:
                        images = movie.get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )
                        # Radarr uses different date fields
                        release_date = (
                            movie.get("digitalRelease")
                            or movie.get("physicalRelease")
                            or movie.get("inCinemas")
                        )
                        entries.append({
                            "id": f"radarr-{movie.get('id')}",
                            "title": movie.get("title", "Unknown"),
                            "subtitle": "",
                            "type": "movie",
                            "season": None,
                            "episode": None,
                            "label": str(movie.get("year", "")),
                            "air_date": release_date,
                            "has_file": movie.get("hasFile", False),
                            "monitored": movie.get("monitored", False),
                            "poster_url": poster,
                            "overview": movie.get("overview", ""),
                            "service": svc.name,
                            "service_type": "radarr",
                            "movie_id": movie.get("id"),
                            "genres": movie.get("genres", []),
                        })
                finally:
                    await client.close()

        except Exception as exc:
            logger.error("Calendar fetch failed for %s: %s", svc.name, exc)

    # Sort by air date
    entries.sort(key=lambda e: e.get("air_date") or "9999")

    return entries


@router.get("")
async def get_calendar(
    start: str = Query(None, description="Start date (ISO format)"),
    end: str = Query(None, description="End date (ISO format)"),
    days: int = Query(30, ge=1, le=90, description="Number of days (if start/end not provided)"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch calendar events from Sonarr and Radarr.

    Returns episodes and movie releases within the date range.
    """
    if not start:
        start = datetime.utcnow().strftime("%Y-%m-%d")
    if not end:
        end_date = datetime.utcnow() + timedelta(days=days)
        end = end_date.strftime("%Y-%m-%d")

    cache_key = f"calendar:{start}:{end}"

    async def _fetch():
        return await _fetch_calendar_data(db, start, end)

    data = await cache.get_or_set(cache_key, _fetch, ttl_seconds=300)

    # Group by date for easy frontend rendering
    by_date: dict[str, list] = {}
    for entry in data:
        air_date = (entry.get("air_date") or "")[:10]  # YYYY-MM-DD
        by_date.setdefault(air_date, []).append(entry)

    return {
        "start": start,
        "end": end,
        "total": len(data),
        "items": data,
        "by_date": by_date,
    }

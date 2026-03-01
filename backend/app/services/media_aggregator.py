"""Media aggregator — fetches and normalises media across all *arr services."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Normalisation helpers ──────────────────────────────────────

def _normalise_movie(raw: dict[str, Any], service_name: str) -> dict[str, Any]:
    """Normalise a Radarr movie to a unified media item."""
    size = 0
    if raw.get("movieFile"):
        size = raw["movieFile"].get("size", 0)
    elif raw.get("sizeOnDisk"):
        size = raw["sizeOnDisk"]

    images = raw.get("images") or []
    poster = next((img["remoteUrl"] for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")), None)

    return {
        "external_id": str(raw.get("id", "")),
        "tmdb_id": raw.get("tmdbId"),
        "title": raw.get("title", "Unknown"),
        "type": "movie",
        "year": raw.get("year"),
        "genres": raw.get("genres", []),
        "quality": raw.get("movieFile", {}).get("quality", {}).get("quality", {}).get("name") if raw.get("movieFile") else None,
        "size_bytes": size,
        "poster_url": poster,
        "source_service": service_name,
        "has_file": raw.get("hasFile", False),
        "monitored": raw.get("monitored", False),
        "status": raw.get("status", "unknown"),
        "added": raw.get("added"),
        "rating": raw.get("ratings", {}).get("tmdb", {}).get("value"),
        "runtime": raw.get("runtime"),
        "overview": raw.get("overview", ""),
    }


def _normalise_series(raw: dict[str, Any], service_name: str) -> dict[str, Any]:
    """Normalise a Sonarr series to a unified media item."""
    images = raw.get("images") or []
    poster = next((img["remoteUrl"] for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")), None)

    stats = raw.get("statistics") or {}

    return {
        "external_id": str(raw.get("id", "")),
        "tmdb_id": raw.get("tvdbId"),  # Sonarr uses TVDB
        "title": raw.get("title", "Unknown"),
        "type": "series",
        "year": raw.get("year"),
        "genres": raw.get("genres", []),
        "quality": raw.get("qualityProfileId"),
        "size_bytes": stats.get("sizeOnDisk", 0),
        "poster_url": poster,
        "source_service": service_name,
        "has_file": stats.get("episodeFileCount", 0) > 0,
        "monitored": raw.get("monitored", False),
        "status": raw.get("status", "unknown"),
        "added": raw.get("added"),
        "rating": raw.get("ratings", {}).get("value"),
        "runtime": raw.get("runtime"),
        "overview": raw.get("overview", ""),
        "seasons": raw.get("seasonCount", 0),
        "episodes_total": stats.get("totalEpisodeCount", 0),
        "episodes_have": stats.get("episodeFileCount", 0),
    }


# ── Public API ─────────────────────────────────────────────────

async def fetch_all_media(db: AsyncSession) -> list[dict[str, Any]]:
    """Fetch media from all connected *arr services and return unified list."""
    stmt = select(Service).where(Service.is_enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    services = result.scalars().all()

    all_media: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
                try:
                    movies = await client.get_movies()
                    for m in movies:
                        all_media.append(_normalise_movie(m, svc.name))
                finally:
                    await client.close()

            elif svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
                try:
                    series = await client.get_series()
                    for s in series:
                        all_media.append(_normalise_series(s, svc.name))
                finally:
                    await client.close()

        except Exception as exc:
            logger.error("Failed to fetch media from %s: %s", svc.name, exc)

    return all_media


async def get_dashboard_stats(db: AsyncSession) -> dict[str, Any]:
    """Compute dashboard statistics from all services."""
    media = await fetch_all_media(db)

    movies = [m for m in media if m["type"] == "movie"]
    series = [m for m in media if m["type"] == "series"]

    total_size = sum(m.get("size_bytes") or 0 for m in media)
    movies_with_files = [m for m in movies if m.get("has_file")]
    series_with_files = [m for m in series if m.get("has_file")]

    return {
        "movies": {
            "total": len(movies),
            "with_files": len(movies_with_files),
            "monitored": len([m for m in movies if m.get("monitored")]),
        },
        "series": {
            "total": len(series),
            "with_files": len(series_with_files),
            "monitored": len([s for s in series if s.get("monitored")]),
            "total_episodes": sum(s.get("episodes_total", 0) for s in series),
            "have_episodes": sum(s.get("episodes_have", 0) for s in series),
        },
        "total_size_bytes": total_size,
        "total_items": len(media),
    }


async def search_media(query: str, db: AsyncSession) -> list[dict[str, Any]]:
    """Search across all fetched media by title."""
    media = await fetch_all_media(db)
    q = query.lower()
    return [m for m in media if q in m.get("title", "").lower()]


async def get_queue_items(db: AsyncSession) -> list[dict[str, Any]]:
    """Fetch the download queue from all Sonarr and Radarr services."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    queue_items: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
            else:
                client = RadarrClient(url=svc.url, api_key=api_key)
            try:
                data = await client.get_queue()
                records = data.get("records", []) if isinstance(data, dict) else []
                for item in records:
                    queue_items.append({
                        "id": item.get("id"),
                        "title": item.get("title", "Unknown"),
                        "status": item.get("status", "unknown"),
                        "progress": _calc_progress(item),
                        "size_bytes": item.get("size", 0),
                        "size_left_bytes": item.get("sizeleft", 0),
                        "time_left": item.get("timeleft"),
                        "source_service": svc.name,
                        "service_type": svc.type,
                        "download_client": item.get("downloadClient", ""),
                        "indexer": item.get("indexer", ""),
                        "quality": item.get("quality", {}).get("quality", {}).get("name", ""),
                    })
            finally:
                await client.close()
        except Exception as exc:
            logger.error("Failed to fetch queue from %s: %s", svc.name, exc)

    return queue_items


def _calc_progress(item: dict) -> float:
    """Calculate download progress percentage."""
    size = item.get("size", 0)
    left = item.get("sizeleft", 0)
    if size <= 0:
        return 0.0
    return round(((size - left) / size) * 100, 1)

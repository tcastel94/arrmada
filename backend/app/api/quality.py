"""Quality Upgrade Tracker — monitors quality profile compliance across library."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.cache import cache
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Quality tiers (lower = worse)
QUALITY_TIERS = {
    # SD
    "SDTV": 1, "DVD": 2, "DVDR": 2,
    # 720p
    "WEBDL-720p": 3, "WEBRip-720p": 3, "Bluray-720p": 4, "HDTV-720p": 3,
    # 1080p
    "WEBDL-1080p": 5, "WEBRip-1080p": 5, "Bluray-1080p": 6, "HDTV-1080p": 5,
    "Remux-1080p": 7,
    # 2160p
    "WEBDL-2160p": 8, "WEBRip-2160p": 8, "Bluray-2160p": 9, "HDTV-2160p": 8,
    "Remux-2160p": 10,
}

# Resolution groups
RESOLUTION_MAP = {
    "SD": ["SDTV", "DVD", "DVDR"],
    "720p": ["WEBDL-720p", "WEBRip-720p", "Bluray-720p", "HDTV-720p"],
    "1080p": ["WEBDL-1080p", "WEBRip-1080p", "Bluray-1080p", "HDTV-1080p", "Remux-1080p"],
    "2160p": ["WEBDL-2160p", "WEBRip-2160p", "Bluray-2160p", "HDTV-2160p", "Remux-2160p"],
}

router = APIRouter(
    prefix="/api/quality",
    tags=["quality"],
    dependencies=[Depends(get_current_user)],
)


async def _analyze_quality(db: AsyncSession) -> dict[str, Any]:
    """Analyze quality distribution across the entire library."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    movie_qualities: list[dict[str, Any]] = []
    episode_qualities: list[dict[str, Any]] = []
    upgradeable: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
                try:
                    movies = await client.get_movies()
                    profiles = await client.get_quality_profiles()
                    profile_map = {p["id"]: p["name"] for p in profiles}

                    for m in movies:
                        if not m.get("hasFile"):
                            continue
                        movie_file = m.get("movieFile", {})
                        quality_name = movie_file.get("quality", {}).get("quality", {}).get("name", "Unknown")
                        size = movie_file.get("size", 0)
                        profile_name = profile_map.get(m.get("qualityProfileId"), "Unknown")

                        quality_tier = QUALITY_TIERS.get(quality_name, 0)

                        item = {
                            "title": m.get("title", "Unknown"),
                            "year": m.get("year"),
                            "type": "movie",
                            "quality": quality_name,
                            "quality_tier": quality_tier,
                            "size_bytes": size,
                            "size_human": format_bytes(size),
                            "profile": profile_name,
                            "service": svc.name,
                            "external_id": m.get("id"),
                        }
                        movie_qualities.append(item)

                        # Check if upgradeable (below 1080p Bluray = tier 6)
                        if quality_tier < 6 and m.get("monitored"):
                            upgradeable.append(item)
                finally:
                    await client.close()

            elif svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
                try:
                    series_list = await client.get_series()
                    profiles = await client.get_quality_profiles()
                    profile_map = {p["id"]: p["name"] for p in profiles}

                    for s in series_list:
                        stats = s.get("statistics", {})
                        profile_name = profile_map.get(s.get("qualityProfileId"), "Unknown")
                        episode_count = stats.get("episodeFileCount", 0)
                        size = stats.get("sizeOnDisk", 0)

                        if episode_count > 0:
                            episode_qualities.append({
                                "title": s.get("title", "Unknown"),
                                "year": s.get("year"),
                                "type": "series",
                                "episodes": episode_count,
                                "size_bytes": size,
                                "size_human": format_bytes(size),
                                "profile": profile_name,
                                "service": svc.name,
                                "external_id": s.get("id"),
                            })
                finally:
                    await client.close()

        except Exception as exc:
            logger.error("Quality analysis failed for %s: %s", svc.name, exc)

    # Quality distribution for movies
    quality_counter: Counter[str] = Counter()
    resolution_counter: Counter[str] = Counter()
    for m in movie_qualities:
        quality_counter[m["quality"]] += 1
        for res, quals in RESOLUTION_MAP.items():
            if m["quality"] in quals:
                resolution_counter[res] += 1
                break
        else:
            resolution_counter["Other"] += 1

    total_movies = len(movie_qualities)
    distribution = {
        quality: {
            "count": count,
            "percent": round(count / total_movies * 100, 1) if total_movies > 0 else 0,
        }
        for quality, count in quality_counter.most_common()
    }

    resolution_dist = {
        res: {
            "count": count,
            "percent": round(count / total_movies * 100, 1) if total_movies > 0 else 0,
        }
        for res, count in resolution_counter.most_common()
    }

    # Sort upgradeable by quality tier (worst first)
    upgradeable.sort(key=lambda x: x["quality_tier"])

    # Estimate upgrade space needed (rough: 1080p Bluray ≈ 10GB per movie)
    avg_1080p_size = 10 * 1024 * 1024 * 1024  # 10 GB
    current_upgradeable_size = sum(u.get("size_bytes", 0) for u in upgradeable)
    estimated_upgrade_size = len(upgradeable) * avg_1080p_size - current_upgradeable_size

    return {
        "movies": {
            "total": total_movies,
            "quality_distribution": distribution,
            "resolution_distribution": resolution_dist,
        },
        "series": {
            "total": len(episode_qualities),
            "total_episodes": sum(s.get("episodes", 0) for s in episode_qualities),
        },
        "upgradeable": {
            "count": len(upgradeable),
            "items": upgradeable[:50],
            "total_current_size": format_bytes(current_upgradeable_size),
            "estimated_space_needed": format_bytes(max(0, estimated_upgrade_size)),
        },
    }


@router.get("")
async def get_quality_overview(db: AsyncSession = Depends(get_db)):
    """Analyze quality distribution and find upgrade opportunities."""
    async def _fetch():
        return await _analyze_quality(db)

    return await cache.get_or_set("quality_upgrade:overview", _fetch, ttl_seconds=600)

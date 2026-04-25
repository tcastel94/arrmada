"""Smart Cleanup API — identifies reclaimable space across the media library."""

from __future__ import annotations

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

router = APIRouter(
    prefix="/api/cleanup",
    tags=["cleanup"],
    dependencies=[Depends(get_current_user)],
)


async def _scan_cleanup_opportunities(db: AsyncSession) -> dict[str, Any]:
    """Scan library for cleanup opportunities."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    unmonitored_with_files: list[dict[str, Any]] = []
    old_low_quality: list[dict[str, Any]] = []
    large_files: list[dict[str, Any]] = []
    ended_series_incomplete: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
                try:
                    movies = await client.get_movies()
                    for m in movies:
                        if not m.get("hasFile"):
                            continue

                        movie_file = m.get("movieFile", {})
                        size = movie_file.get("size", 0)
                        quality_name = movie_file.get("quality", {}).get("quality", {}).get("name", "Unknown")
                        year = m.get("year", 0)

                        images = m.get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )

                        base_item = {
                            "title": m.get("title", "Unknown"),
                            "year": year,
                            "type": "movie",
                            "quality": quality_name,
                            "size_bytes": size,
                            "size_human": format_bytes(size),
                            "poster_url": poster,
                            "service": svc.name,
                            "service_type": "radarr",
                            "external_id": m.get("id"),
                            "monitored": m.get("monitored", False),
                        }

                        # 1. Unmonitored but has file (forgotten media)
                        if not m.get("monitored") and m.get("hasFile"):
                            unmonitored_with_files.append({
                                **base_item,
                                "reason": "unmonitored",
                                "suggestion": "Ce film n'est plus surveillé mais occupe de l'espace",
                            })

                        # 2. Old low-quality files (SD or DVD, added > 2 years ago)
                        if quality_name in ("SDTV", "DVD", "DVDR") and year and year < 2020:
                            old_low_quality.append({
                                **base_item,
                                "reason": "low_quality",
                                "suggestion": f"Qualité {quality_name} — upgrade recommandé",
                            })

                        # 3. Very large files (> 50GB, likely Remux)
                        if size > 50 * 1024 * 1024 * 1024:
                            large_files.append({
                                **base_item,
                                "reason": "oversized",
                                "suggestion": f"Fichier volumineux ({format_bytes(size)}) — vérifier si Remux nécessaire",
                            })
                finally:
                    await client.close()

            elif svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
                try:
                    series_list = await client.get_series()
                    for s in series_list:
                        stats = s.get("statistics", {})
                        size = stats.get("sizeOnDisk", 0)
                        total_eps = stats.get("totalEpisodeCount", 0)
                        have_eps = stats.get("episodeFileCount", 0)
                        status = s.get("status", "")

                        images = s.get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )

                        base_item = {
                            "title": s.get("title", "Unknown"),
                            "year": s.get("year"),
                            "type": "series",
                            "episodes_total": total_eps,
                            "episodes_have": have_eps,
                            "size_bytes": size,
                            "size_human": format_bytes(size),
                            "poster_url": poster,
                            "service": svc.name,
                            "service_type": "sonarr",
                            "external_id": s.get("id"),
                            "monitored": s.get("monitored", False),
                            "status": status,
                        }

                        # 1. Unmonitored with files
                        if not s.get("monitored") and have_eps > 0:
                            unmonitored_with_files.append({
                                **base_item,
                                "reason": "unmonitored",
                                "suggestion": f"Série non surveillée — {have_eps} épisodes occupent {format_bytes(size)}",
                            })

                        # 2. Ended series with incomplete collection (not worth keeping partial)
                        if status == "ended" and have_eps > 0 and total_eps > 0:
                            completion = round(have_eps / total_eps * 100, 1) if total_eps > 0 else 0
                            if 0 < completion < 50:
                                ended_series_incomplete.append({
                                    **base_item,
                                    "reason": "incomplete_ended",
                                    "completion_percent": completion,
                                    "suggestion": f"Série terminée, seulement {completion}% complète ({have_eps}/{total_eps} épisodes)",
                                })

                        # 3. Large series
                        if size > 100 * 1024 * 1024 * 1024:
                            large_files.append({
                                **base_item,
                                "reason": "oversized",
                                "suggestion": f"Série volumineuse ({format_bytes(size)}) — {have_eps} épisodes",
                            })
                finally:
                    await client.close()

        except Exception as exc:
            logger.error("Cleanup scan failed for %s: %s", svc.name, exc)

    # Sort everything by size (biggest first)
    for lst in [unmonitored_with_files, old_low_quality, large_files, ended_series_incomplete]:
        lst.sort(key=lambda x: x.get("size_bytes", 0), reverse=True)

    # Calculate totals
    total_reclaimable = (
        sum(i["size_bytes"] for i in unmonitored_with_files)
        + sum(i["size_bytes"] for i in ended_series_incomplete)
    )

    return {
        "unmonitored": {
            "items": unmonitored_with_files[:30],
            "total": len(unmonitored_with_files),
            "reclaimable_bytes": sum(i["size_bytes"] for i in unmonitored_with_files),
            "reclaimable_human": format_bytes(sum(i["size_bytes"] for i in unmonitored_with_files)),
        },
        "low_quality": {
            "items": old_low_quality[:30],
            "total": len(old_low_quality),
        },
        "oversized": {
            "items": large_files[:20],
            "total": len(large_files),
        },
        "incomplete_ended": {
            "items": ended_series_incomplete[:20],
            "total": len(ended_series_incomplete),
        },
        "summary": {
            "total_issues": (
                len(unmonitored_with_files)
                + len(old_low_quality)
                + len(large_files)
                + len(ended_series_incomplete)
            ),
            "total_reclaimable_bytes": total_reclaimable,
            "total_reclaimable_human": format_bytes(total_reclaimable),
        },
    }


@router.get("")
async def get_cleanup_opportunities(db: AsyncSession = Depends(get_db)):
    """Scan library for cleanup opportunities and reclaimable space."""
    async def _fetch():
        return await _scan_cleanup_opportunities(db)

    return await cache.get_or_set("cleanup:scan", _fetch, ttl_seconds=600)

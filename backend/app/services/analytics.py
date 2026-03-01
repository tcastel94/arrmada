"""Analytics service — library statistics and insights."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.media_aggregator import fetch_all_media
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_library_analytics(db: AsyncSession) -> dict[str, Any]:
    """Compute comprehensive library analytics."""
    media = await fetch_all_media(db)

    movies = [m for m in media if m["type"] == "movie"]
    series = [m for m in media if m["type"] == "series"]

    # ── Quality distribution ──────────────────────────────────
    quality_counter: Counter[str] = Counter()
    for m in media:
        q = m.get("quality")
        if q:
            quality_counter[str(q)] += 1
        else:
            quality_counter["Inconnu"] += 1

    quality_dist = [
        {"name": k, "count": v}
        for k, v in quality_counter.most_common(15)
    ]

    # ── Genre distribution ────────────────────────────────────
    genre_counter: Counter[str] = Counter()
    for m in media:
        for g in (m.get("genres") or []):
            genre_counter[g] += 1

    genre_dist = [
        {"name": k, "count": v}
        for k, v in genre_counter.most_common(20)
    ]

    # ── Year distribution ─────────────────────────────────────
    year_counter: Counter[int] = Counter()
    for m in media:
        y = m.get("year")
        if y and isinstance(y, int) and y > 1900:
            year_counter[y] += 1

    year_dist = sorted(
        [{"year": k, "count": v} for k, v in year_counter.items()],
        key=lambda x: x["year"],
    )

    # ── Size analysis ─────────────────────────────────────────
    total_size = sum(m.get("size_bytes") or 0 for m in media)
    movie_size = sum(m.get("size_bytes") or 0 for m in movies)
    series_size = sum(m.get("size_bytes") or 0 for m in series)

    avg_movie_size = movie_size // max(len([m for m in movies if m.get("size_bytes")]), 1)
    avg_series_size = series_size // max(len([s for s in series if s.get("size_bytes")]), 1)

    # Top 10 biggest items
    sorted_by_size = sorted(media, key=lambda m: m.get("size_bytes") or 0, reverse=True)
    top_biggest = [
        {
            "title": m["title"],
            "type": m["type"],
            "size_bytes": m.get("size_bytes", 0),
            "size_human": format_bytes(m.get("size_bytes", 0)),
            "quality": str(m.get("quality", "")),
        }
        for m in sorted_by_size[:10]
    ]

    # ── Monitored vs Available ────────────────────────────────
    monitored_count = len([m for m in media if m.get("monitored")])
    available_count = len([m for m in media if m.get("has_file")])
    missing_count = len([m for m in media if m.get("monitored") and not m.get("has_file")])

    # ── Service breakdown ─────────────────────────────────────
    service_counter: Counter[str] = Counter()
    for m in media:
        service_counter[m.get("source_service", "Unknown")] += 1

    service_breakdown = [
        {"name": k, "count": v}
        for k, v in service_counter.most_common()
    ]

    return {
        "overview": {
            "total_items": len(media),
            "movies": len(movies),
            "series": len(series),
            "total_size_bytes": total_size,
            "total_size_human": format_bytes(total_size),
            "movie_size_human": format_bytes(movie_size),
            "series_size_human": format_bytes(series_size),
            "avg_movie_size_human": format_bytes(avg_movie_size),
            "avg_series_size_human": format_bytes(avg_series_size),
            "monitored": monitored_count,
            "available": available_count,
            "missing": missing_count,
        },
        "quality_distribution": quality_dist,
        "genre_distribution": genre_dist,
        "year_distribution": year_dist,
        "top_biggest": top_biggest,
        "service_breakdown": service_breakdown,
    }

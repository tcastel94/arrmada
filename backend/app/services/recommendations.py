"""Recommendations service — suggest media based on library analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.media_aggregator import fetch_all_media
from app.services.radarr import RadarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_recommendations(db: AsyncSession) -> dict[str, Any]:
    """Generate recommendations based on library analysis and Radarr exclusions."""
    media = await fetch_all_media(db)

    # Analyse top genres
    genre_counter: Counter[str] = Counter()
    existing_titles = set()
    for m in media:
        existing_titles.add(m.get("title", "").lower())
        for g in (m.get("genres") or []):
            genre_counter[g] += 1

    top_genres = [g for g, _ in genre_counter.most_common(5)]

    # Get "missing" (monitored but not downloaded) as "wanted" recommendations
    wanted = [
        {
            "title": m["title"],
            "type": m["type"],
            "year": m.get("year"),
            "poster_url": m.get("poster_url"),
            "source_service": m.get("source_service"),
            "genres": m.get("genres", []),
        }
        for m in media
        if m.get("monitored") and not m.get("has_file")
    ]

    # Recently added items (could lead to "similar" discovery)
    recent = sorted(
        [m for m in media if m.get("added")],
        key=lambda m: m.get("added", ""),
        reverse=True,
    )[:10]

    recent_items = [
        {
            "title": m["title"],
            "type": m["type"],
            "year": m.get("year"),
            "poster_url": m.get("poster_url"),
            "genres": m.get("genres", []),
            "source_service": m.get("source_service"),
        }
        for m in recent
    ]

    # Basic stats for recommendations context
    return {
        "top_genres": top_genres,
        "wanted": wanted[:20],
        "recently_added": recent_items,
        "stats": {
            "total_wanted": len(wanted),
            "total_library": len(media),
        },
    }

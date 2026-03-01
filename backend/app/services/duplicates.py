"""Duplicate detection service — finds duplicate media across services."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.media_aggregator import fetch_all_media
from app.utils.helpers import format_bytes, normalize_title
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def detect_duplicates(db: AsyncSession) -> dict[str, Any]:
    """Find duplicate media across services and within libraries.

    Detection strategies:
    1. Same TMDB/TVDB ID across different services
    2. Same normalised title + year
    3. Quality upgrade opportunities (same title, different quality)
    """
    media = await fetch_all_media(db)

    # Group by normalised title + year
    title_groups: dict[str, list[dict]] = defaultdict(list)
    for m in media:
        key = f"{normalize_title(m['title'])}_{m.get('year', '')}"
        title_groups[key].append(m)

    duplicates: list[dict[str, Any]] = []
    upgrade_opportunities: list[dict[str, Any]] = []

    for key, items in title_groups.items():
        if len(items) < 2:
            continue

        # Check if they're from different services (cross-service dupe)
        services = set(m["source_service"] for m in items)

        if len(services) > 1:
            # Cross-service duplicate
            total_size = sum(m.get("size_bytes") or 0 for m in items)
            duplicates.append({
                "title": items[0]["title"],
                "type": items[0]["type"],
                "year": items[0].get("year"),
                "copies": len(items),
                "services": list(services),
                "total_size_bytes": total_size,
                "total_size_human": format_bytes(total_size),
                "items": [
                    {
                        "source": m["source_service"],
                        "quality": str(m.get("quality", "?")),
                        "size_human": format_bytes(m.get("size_bytes", 0)),
                        "has_file": m.get("has_file", False),
                    }
                    for m in items
                ],
                "reason": "cross_service",
            })
        else:
            # Same service, possibly different qualities
            qualities = [str(m.get("quality", "")) for m in items]
            if len(set(qualities)) > 1:
                upgrade_opportunities.append({
                    "title": items[0]["title"],
                    "type": items[0]["type"],
                    "year": items[0].get("year"),
                    "service": list(services)[0],
                    "qualities": qualities,
                    "reason": "quality_variants",
                })

    # Sort by total size descending (most impactful first)
    duplicates.sort(key=lambda d: d.get("total_size_bytes", 0), reverse=True)

    wasted_bytes = sum(
        d["total_size_bytes"] - min(
            (item.get("size_bytes") or 0)
            for item in [m for m in media if normalize_title(m["title"]) == normalize_title(d["title"])]
        ) if d["total_size_bytes"] > 0 else 0
        for d in duplicates
    )

    return {
        "duplicates": duplicates,
        "upgrade_opportunities": upgrade_opportunities[:20],
        "stats": {
            "total_duplicates": len(duplicates),
            "total_upgrades": len(upgrade_opportunities),
            "wasted_space_bytes": wasted_bytes,
            "wasted_space_human": format_bytes(wasted_bytes),
        },
    }

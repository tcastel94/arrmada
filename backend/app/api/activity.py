"""Activity Feed API — unified timeline of events from Sonarr/Radarr."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.sonarr import SonarrClient
from app.services.radarr import RadarrClient
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


# ── Schemas ──────────────────────────────────────────────────

class ActivityItem(BaseModel):
    id: str
    event_type: str
    event_label: str
    source: str
    title: str
    subtitle: str
    quality: str | None = None
    languages: str | None = None
    date: str
    timestamp: int
    icon_type: str
    status: str
    size_bytes: int | None = None
    indexer: str | None = None
    download_client: str | None = None
    poster_url: str | None = None


class ActivityFeed(BaseModel):
    items: list[ActivityItem]
    total: int
    has_more: bool


# ── Event Mapping ────────────────────────────────────────────

EVENT_MAP = {
    "grabbed":               {"icon": "grab",    "status": "info",    "label": "Téléchargement lancé"},
    "downloadFolderImported": {"icon": "import",  "status": "success", "label": "Importé"},
    "downloadFailed":        {"icon": "fail",    "status": "error",   "label": "Échec"},
    "episodeFileDeleted":    {"icon": "delete",  "status": "warning", "label": "Supprimé"},
    "episodeFileRenamed":    {"icon": "rename",  "status": "info",    "label": "Renommé"},
    "seriesDeleted":         {"icon": "delete",  "status": "warning", "label": "Série supprimée"},
    "movieFileDeleted":      {"icon": "delete",  "status": "warning", "label": "Supprimé"},
    "movieFileRenamed":      {"icon": "rename",  "status": "info",    "label": "Renommé"},
    "movieDeleted":          {"icon": "delete",  "status": "warning", "label": "Film supprimé"},
}


def _extract_title_from_source(source_title: str) -> tuple[str, str]:
    """Try to extract a clean title and episode info from the NZB/torrent source title."""
    if not source_title:
        return "Unknown", ""

    # Try to extract series: "Show.Name.S01E02..." or "Show.Name.2024.S01E02..."
    m = re.match(r'^(.+?)\.(S\d{2}E\d{2})', source_title, re.IGNORECASE)
    if m:
        title = m.group(1).replace(".", " ").strip()
        ep = m.group(2).upper()
        return title, ep

    # Movie: "Movie.Name.2024.1080p..."
    m = re.match(r'^(.+?)\.(\d{4})\.', source_title)
    if m:
        title = m.group(1).replace(".", " ").strip()
        year = m.group(2)
        return title, f"({year})"

    # Fallback
    clean = source_title.split(".")[0:4]
    return " ".join(clean).replace(".", " "), ""


def _parse_timestamp(date_str: str) -> int:
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except (ValueError, AttributeError):
        return 0


def _parse_size(data: dict) -> int | None:
    """Extract size from history data, trying multiple fields."""
    for key in ("size", "fileSize", "nzbSize"):
        val = data.get(key)
        if val:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
    return None


def _parse_sonarr_history(records: list[dict], base_url: str) -> list[ActivityItem]:
    items = []
    for rec in records:
        event_type = rec.get("eventType", "unknown")
        meta = EVENT_MAP.get(event_type, {"icon": "download", "status": "info", "label": event_type})
        data = rec.get("data", {})

        # Series info — use embedded objects if available
        series = rec.get("series", {}) or {}
        episode = rec.get("episode", {}) or {}

        series_title = series.get("title", "")
        ep_season = episode.get("seasonNumber")
        ep_number = episode.get("episodeNumber")
        ep_title = episode.get("title", "")

        # Fallback: parse from sourceTitle
        source_title = rec.get("sourceTitle", "") or data.get("nzbName", "") or ""
        if not series_title or series_title == "Unknown":
            fallback_title, _ = _extract_title_from_source(source_title)
            series_title = fallback_title

        # Build subtitle
        if ep_season is not None and ep_number is not None and (ep_season > 0 or ep_number > 0):
            ep_code = f"S{ep_season:02d}E{ep_number:02d}"
            subtitle = f"{ep_code} — {ep_title}" if ep_title else ep_code
        else:
            _, ep_info = _extract_title_from_source(source_title)
            subtitle = ep_info or source_title[:60]

        # Quality
        quality_name = rec.get("quality", {}).get("quality", {}).get("name", "")

        # Languages
        langs = rec.get("languages", [])
        lang_str = ", ".join(l.get("name", "") for l in langs if l.get("name")) if langs else None

        # Poster
        poster = None
        images = series.get("images", [])
        for img in images:
            if img.get("coverType") == "poster":
                remote = img.get("remoteUrl") or img.get("url", "")
                if remote:
                    poster = remote
                break

        # Upgrade detection
        icon = meta["icon"]
        status = meta["status"]
        if event_type == "downloadFolderImported" and data.get("droppedPath"):
            icon = "upgrade"

        date_str = rec.get("date", "")

        items.append(ActivityItem(
            id=f"sonarr-{rec.get('id', 0)}",
            event_type=event_type,
            event_label=meta["label"],
            source="sonarr",
            title=series_title,
            subtitle=subtitle,
            quality=quality_name or None,
            languages=lang_str,
            date=date_str,
            timestamp=_parse_timestamp(date_str),
            icon_type=icon,
            status=status,
            size_bytes=_parse_size(data),
            indexer=data.get("indexer"),
            download_client=data.get("downloadClient") or data.get("downloadClientName"),
            poster_url=poster,
        ))
    return items


def _parse_radarr_history(records: list[dict], base_url: str) -> list[ActivityItem]:
    items = []
    for rec in records:
        event_type = rec.get("eventType", "unknown")
        meta = EVENT_MAP.get(event_type, {"icon": "download", "status": "info", "label": event_type})
        data = rec.get("data", {})

        movie = rec.get("movie", {}) or {}
        movie_title = movie.get("title", "")
        year = movie.get("year", "")

        source_title = rec.get("sourceTitle", "") or data.get("nzbName", "") or ""
        if not movie_title:
            movie_title, _ = _extract_title_from_source(source_title)

        subtitle = f"({year})" if year else ""

        quality_name = rec.get("quality", {}).get("quality", {}).get("name", "")

        langs = rec.get("languages", [])
        lang_str = ", ".join(l.get("name", "") for l in langs if l.get("name")) if langs else None

        # Poster
        poster = None
        images = movie.get("images", [])
        for img in images:
            if img.get("coverType") == "poster":
                remote = img.get("remoteUrl") or img.get("url", "")
                if remote:
                    poster = remote
                break

        icon = meta["icon"]
        status = meta["status"]
        if event_type == "downloadFolderImported" and data.get("droppedPath"):
            icon = "upgrade"

        date_str = rec.get("date", "")

        items.append(ActivityItem(
            id=f"radarr-{rec.get('id', 0)}",
            event_type=event_type,
            event_label=meta["label"],
            source="radarr",
            title=movie_title,
            subtitle=subtitle,
            quality=quality_name or None,
            languages=lang_str,
            date=date_str,
            timestamp=_parse_timestamp(date_str),
            icon_type=icon,
            status=status,
            size_bytes=_parse_size(data),
            indexer=data.get("indexer"),
            download_client=data.get("downloadClient") or data.get("downloadClientName"),
            poster_url=poster,
        ))
    return items


# ── Endpoint ─────────────────────────────────────────────────

@router.get("/activity", response_model=ActivityFeed)
async def get_activity(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Unified activity feed from all Sonarr and Radarr instances."""

    async def _fetch():
        stmt = (
            select(Service)
            .where(
                Service.type.in_(["sonarr", "Sonarr", "radarr", "Radarr"]),
                Service.is_enabled == True,  # noqa: E712
            )
        )
        result = await db.execute(stmt)
        services = result.scalars().all()

        all_items: list[ActivityItem] = []

        for service in services:
            try:
                svc_type = service.type.lower()
                api_key = decrypt_api_key(service.api_key)

                if svc_type == "sonarr":
                    client = SonarrClient(url=service.url, api_key=api_key)
                    try:
                        data = await client.get("/history", params={
                            "pageSize": limit,
                            "sortKey": "date",
                            "sortDirection": "descending",
                            "includeSeries": "true",
                            "includeEpisode": "true",
                        })
                        records = data.get("records", []) if isinstance(data, dict) else []
                        all_items.extend(_parse_sonarr_history(records, service.url))
                    finally:
                        await client.close()

                elif svc_type == "radarr":
                    client = RadarrClient(url=service.url, api_key=api_key)
                    try:
                        data = await client.get("/history", params={
                            "pageSize": limit,
                            "sortKey": "date",
                            "sortDirection": "descending",
                            "includeMovie": "true",
                        })
                        records = data.get("records", []) if isinstance(data, dict) else []
                        all_items.extend(_parse_radarr_history(records, service.url))
                    finally:
                        await client.close()

            except Exception as e:
                logger.warning("Failed to fetch activity from %s: %s", service.name, e)

        all_items.sort(key=lambda x: x.timestamp, reverse=True)
        trimmed = all_items[:limit]

        return ActivityFeed(
            items=trimmed,
            total=len(all_items),
            has_more=len(all_items) > limit,
        )

    return await cache.get_or_set("activity_feed", _fetch, ttl_seconds=30)

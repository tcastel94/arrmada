"""Activity Feed API — unified timeline of events from Sonarr/Radarr."""

from __future__ import annotations

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
    """One event in the activity timeline."""
    id: str
    event_type: str        # grabbed, downloaded, imported, upgraded, failed, deleted
    source: str            # sonarr, radarr
    title: str             # Series/Movie name
    subtitle: str          # Episode/Quality info
    quality: str | None = None
    date: str              # ISO format
    timestamp: int         # Unix ms for sorting
    icon_type: str         # grab, download, upgrade, fail, delete, import
    status: str            # success, warning, error, info
    size_bytes: int | None = None
    indexer: str | None = None
    download_client: str | None = None


class ActivityFeed(BaseModel):
    """Paginated activity feed."""
    items: list[ActivityItem]
    total: int
    has_more: bool


# ── Event Mapping ────────────────────────────────────────────

EVENT_MAP = {
    # Sonarr event types
    "grabbed": {"icon_type": "grab", "status": "info"},
    "downloadFolderImported": {"icon_type": "import", "status": "success"},
    "downloadFailed": {"icon_type": "fail", "status": "error"},
    "episodeFileDeleted": {"icon_type": "delete", "status": "warning"},
    "episodeFileRenamed": {"icon_type": "import", "status": "info"},
    "seriesDeleted": {"icon_type": "delete", "status": "warning"},
    # Radarr event types
    "movieFileDeleted": {"icon_type": "delete", "status": "warning"},
    "movieFileRenamed": {"icon_type": "import", "status": "info"},
    "movieDeleted": {"icon_type": "delete", "status": "warning"},
}

EVENT_LABELS = {
    "grabbed": "Téléchargement lancé",
    "downloadFolderImported": "Importé",
    "downloadFailed": "Échec du téléchargement",
    "episodeFileDeleted": "Fichier supprimé",
    "episodeFileRenamed": "Fichier renommé",
    "seriesDeleted": "Série supprimée",
    "movieFileDeleted": "Fichier supprimé",
    "movieFileRenamed": "Fichier renommé",
    "movieDeleted": "Film supprimé",
}


def _parse_sonarr_history(records: list[dict], service_name: str) -> list[ActivityItem]:
    """Parse Sonarr history records into ActivityItems."""
    items = []
    for rec in records:
        event_type = rec.get("eventType", "unknown")
        meta = EVENT_MAP.get(event_type, {"icon_type": "download", "status": "info"})

        series = rec.get("series", {})
        episode = rec.get("episode", {})
        quality_obj = rec.get("quality", {}).get("quality", {})
        data = rec.get("data", {})

        series_title = series.get("title", "Unknown")
        ep_num = f"S{episode.get('seasonNumber', 0):02d}E{episode.get('episodeNumber', 0):02d}"
        ep_title = episode.get("title", "")
        subtitle = f"{ep_num} — {ep_title}" if ep_title else ep_num

        # Check if upgrade
        is_upgrade = rec.get("qualityCutoffNotMet", False) is False and event_type == "downloadFolderImported"
        if is_upgrade and data.get("droppedPath"):
            meta = {"icon_type": "upgrade", "status": "success"}

        date_str = rec.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            timestamp = 0

        items.append(ActivityItem(
            id=f"sonarr-{rec.get('id', 0)}",
            event_type=event_type,
            source="sonarr",
            title=series_title,
            subtitle=subtitle,
            quality=quality_obj.get("name"),
            date=date_str,
            timestamp=timestamp,
            icon_type=meta["icon_type"],
            status=meta["status"],
            size_bytes=data.get("size"),
            indexer=data.get("indexer"),
            download_client=data.get("downloadClient"),
        ))
    return items


def _parse_radarr_history(records: list[dict], service_name: str) -> list[ActivityItem]:
    """Parse Radarr history records into ActivityItems."""
    items = []
    for rec in records:
        event_type = rec.get("eventType", "unknown")
        meta = EVENT_MAP.get(event_type, {"icon_type": "download", "status": "info"})

        movie = rec.get("movie", {})
        quality_obj = rec.get("quality", {}).get("quality", {})
        data = rec.get("data", {})

        movie_title = movie.get("title", "Unknown")
        year = movie.get("year", "")
        subtitle = f"({year})" if year else ""

        # Upgrade detection
        is_upgrade = rec.get("qualityCutoffNotMet", False) is False and event_type == "downloadFolderImported"
        if is_upgrade and data.get("droppedPath"):
            meta = {"icon_type": "upgrade", "status": "success"}

        date_str = rec.get("date", "")
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            timestamp = 0

        items.append(ActivityItem(
            id=f"radarr-{rec.get('id', 0)}",
            event_type=event_type,
            source="radarr",
            title=movie_title,
            subtitle=subtitle,
            quality=quality_obj.get("name"),
            date=date_str,
            timestamp=timestamp,
            icon_type=meta["icon_type"],
            status=meta["status"],
            size_bytes=data.get("size"),
            indexer=data.get("indexer"),
            download_client=data.get("downloadClient"),
        ))
    return items


# ── Endpoint ─────────────────────────────────────────────────

@router.get(
    "/activity",
    response_model=ActivityFeed,
    summary="Unified activity feed from Sonarr & Radarr",
)
async def get_activity(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Fetch and merge recent activity from all Sonarr and Radarr instances."""

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
                        data = await client.get(
                            "/history",
                            params={"pageSize": limit, "sortKey": "date", "sortDirection": "descending"},
                        )
                        records = data.get("records", []) if isinstance(data, dict) else []
                        all_items.extend(_parse_sonarr_history(records, service.name))
                    finally:
                        await client.close()

                elif svc_type == "radarr":
                    client = RadarrClient(url=service.url, api_key=api_key)
                    try:
                        data = await client.get(
                            "/history",
                            params={"pageSize": limit, "sortKey": "date", "sortDirection": "descending"},
                        )
                        records = data.get("records", []) if isinstance(data, dict) else []
                        all_items.extend(_parse_radarr_history(records, service.name))
                    finally:
                        await client.close()

            except Exception as e:
                logger.warning("Failed to fetch activity from %s: %s", service.name, e)

        # Sort by timestamp descending
        all_items.sort(key=lambda x: x.timestamp, reverse=True)

        # Limit
        trimmed = all_items[:limit]

        return ActivityFeed(
            items=trimmed,
            total=len(all_items),
            has_more=len(all_items) > limit,
        )

    return await cache.get_or_set("activity_feed", _fetch, ttl_seconds=30)

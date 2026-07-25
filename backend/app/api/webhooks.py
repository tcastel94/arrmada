"""Webhooks API — receive events from Sonarr, Radarr, Bazarr, etc.

Configure in each *arr service:
  Settings → Connect → Webhook
  URL: http://<arrmada-ip>:8420/api/webhooks/sonarr  (or /radarr, /bazarr)
  Method: POST
  Events: On Grab, On Import, On Upgrade, On Health Issue, On Rename

This endpoint:
  1. Invalidates relevant cache entries
  2. Publishes SSE events for real-time frontend updates
  3. Creates in-app notifications for important events
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_db
from app.utils.cache import cache
from app.utils.event_bus import event_bus
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/webhooks",
    tags=["webhooks"],
    # No auth — webhooks come from internal services
)


async def _handle_arr_webhook(
    service_type: str,
    payload: dict[str, Any],
    db: AsyncSession,
) -> dict[str, str]:
    """Process a webhook from a *arr service."""
    event_type = payload.get("eventType", "unknown")
    title = "Unknown"

    # Extract title based on event structure
    if "movie" in payload:
        title = payload["movie"].get("title", "Unknown movie")
    elif "series" in payload:
        title = payload["series"].get("title", "Unknown series")
        if "episodes" in payload:
            eps = payload["episodes"]
            if eps:
                title += f" S{eps[0].get('seasonNumber', '?'):02d}E{eps[0].get('episodeNumber', '?'):02d}"
    elif "message" in payload:
        title = payload["message"]

    quality = ""
    if "movieFile" in payload:
        quality = payload["movieFile"].get("quality", {}).get("quality", {}).get("name", "")
    elif "episodeFile" in payload:
        quality = payload["episodeFile"].get("quality", {}).get("quality", {}).get("name", "")

    logger.info("[Webhook] %s → %s: %s (%s)", service_type, event_type, title, quality or "n/a")

    # Invalidate caches based on event type
    if event_type in ("Download", "Grab", "MovieAdded", "SeriesAdd", "EpisodeFileDelete", "MovieDelete"):
        cache.invalidate_pattern("media:*")
        cache.invalidate_pattern("dashboard_stats")
        cache.invalidate_pattern("search:*")
        cache.invalidate_pattern("duplicates")
        cache.invalidate_pattern("recommendations")
        cache.invalidate_pattern("analytics:*")
        cache.invalidate_pattern("calendar:*")
        cache.invalidate_pattern("quality_upgrade:*")

    elif event_type in ("Health", "HealthRestored"):
        cache.invalidate_pattern("health:*")

    elif event_type == "Rename":
        cache.invalidate_pattern("media:*")

    # Publish SSE event
    sse_type_map = {
        "Grab": "download_grab",
        "Download": "new_import",
        "MovieAdded": "new_import",
        "SeriesAdd": "new_import",
        "Rename": "media_renamed",
        "Health": "health_alert",
        "HealthRestored": "health_restored",
        "EpisodeFileDelete": "media_deleted",
        "MovieDelete": "media_deleted",
        "MovieFileDelete": "media_deleted",
        "Test": "webhook_test",
    }
    sse_event_type = sse_type_map.get(event_type, f"{service_type}_{event_type.lower()}")

    await event_bus.publish(sse_event_type, {
        "service": service_type,
        "event": event_type,
        "title": title,
        "quality": quality,
        "source": payload.get("downloadClient", ""),
    })

    # Also publish cache_invalidated so frontend knows to refetch
    await event_bus.publish("cache_invalidated", {
        "source": service_type,
        "event": event_type,
        "patterns": ["media", "dashboard"],
    })

    # Create in-app notification for important events
    if event_type == "Download":
        try:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                type="new_import",
                title=f"{'🎬' if service_type == 'radarr' else '📺'} {title}",
                message=f"Importé via {service_type.capitalize()}" + (f" en {quality}" if quality else ""),
                severity="info",
                service_name=service_type,
            )
        except Exception:
            pass

        # Auto-refresh Kodi so the new import shows up without a manual sync.
        if service_type in ("radarr", "sonarr"):
            try:
                from app.services.kodi import sync_kodi
                result = await sync_kodi(db)
                cache.invalidate("kodi:watched")
                if result.get("success"):
                    logger.info("[Webhook] Triggered Kodi scan after %s import", service_type)
            except Exception as exc:
                logger.debug("[Webhook] Kodi auto-scan skipped: %s", exc)

    elif event_type == "Health":
        try:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                type="health_issue",
                title=f"⚠️ {service_type.capitalize()} — Problème de santé",
                message=title,
                severity="warning",
                service_name=service_type,
            )
        except Exception:
            pass

    return {"status": "ok", "event": event_type, "service": service_type}


@router.post("/sonarr")
async def sonarr_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive webhook events from Sonarr."""
    payload = await request.json()
    return await _handle_arr_webhook("sonarr", payload, db)


@router.post("/radarr")
async def radarr_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive webhook events from Radarr."""
    payload = await request.json()
    return await _handle_arr_webhook("radarr", payload, db)


@router.post("/bazarr")
async def bazarr_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive webhook events from Bazarr."""
    payload = await request.json()
    event_type = payload.get("eventType", "subtitle_download")

    cache.invalidate_pattern("media:*")

    await event_bus.publish("subtitle_update", {
        "service": "bazarr",
        "event": event_type,
        "title": payload.get("title", "Unknown"),
        "language": payload.get("language", ""),
    })

    return {"status": "ok", "event": event_type, "service": "bazarr"}


@router.post("/sabnzbd")
async def sabnzbd_webhook(request: Request):
    """Receive webhook events from SABnzbd."""
    payload = await request.json()

    cache.invalidate_pattern("downloads:*")

    await event_bus.publish("download_update", {
        "service": "sabnzbd",
        "title": payload.get("name", "Unknown"),
        "status": payload.get("status", "unknown"),
    })

    return {"status": "ok", "service": "sabnzbd"}


@router.post("/test")
async def test_webhook(request: Request):
    """Test webhook — sends a test SSE event."""
    await event_bus.publish("webhook_test", {
        "message": "Webhook test successful!",
        "clients": event_bus.client_count,
    })
    return {"status": "ok", "clients": event_bus.client_count}

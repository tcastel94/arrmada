"""Downloads API — unified download queue from all services."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services import media_aggregator
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/downloads",
    tags=["downloads"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_downloads(db: AsyncSession = Depends(get_db)):
    """Fetch combined download queue from all Sonarr/Radarr services."""
    items = await media_aggregator.get_queue_items(db)
    return {"items": items, "total": len(items)}


# ── Queue actions ─────────────────────────────────────────────

async def _get_arr_client_for_service(db: AsyncSession, service_type: str, *, timeout: int = 30):
    """Resolve the enabled Radarr/Sonarr client for a queue item's service type."""
    if service_type not in ("radarr", "sonarr"):
        raise HTTPException(status_code=400, detail="Invalid service type")

    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == service_type,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()
    if not service:
        raise HTTPException(status_code=400, detail=f"No {service_type} service configured")

    api_key = decrypt_api_key(service.api_key)
    if service_type == "radarr":
        return RadarrClient(url=service.url, api_key=api_key, timeout=timeout)
    return SonarrClient(url=service.url, api_key=api_key, timeout=timeout)


class QueueRemovePayload(BaseModel):
    removeFromClient: bool = True
    blocklist: bool = False


@router.post("/queue/{type}/{id}/remove")
async def remove_queue_item(
    type: str,
    id: int,
    payload: QueueRemovePayload | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Remove a queue item (optionally from the download client and/or blocklist it)."""
    body = payload or QueueRemovePayload()
    client = await _get_arr_client_for_service(db, type)
    try:
        await client.remove_queue_item(
            id,
            remove_from_client=body.removeFromClient,
            blocklist=body.blocklist,
        )
        return {"status": "removed", "id": id, "blocklisted": body.blocklist}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to remove queue item %d (%s): %s", id, type, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


class QueueRetryPayload(BaseModel):
    movie_id: int | None = None
    series_id: int | None = None


@router.post("/queue/{type}/{id}/retry")
async def retry_queue_item(
    type: str,
    id: int,
    payload: QueueRetryPayload | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Retry a stuck/failed download: blocklist + remove, then trigger a fresh search."""
    body = payload or QueueRetryPayload()
    client = await _get_arr_client_for_service(db, type)
    try:
        # 1. Blocklist the release and remove it so *arr won't immediately re-grab it.
        await client.remove_queue_item(id, remove_from_client=True, blocklist=True)

        # 2. Trigger a fresh automatic search for the underlying media (if known).
        search_result = None
        if type == "radarr" and body.movie_id is not None:
            search_result = await client.search_movie(body.movie_id)
        elif type == "sonarr" and body.series_id is not None:
            search_result = await client.search_series(body.series_id)

        return {"status": "retried", "id": id, "search_triggered": search_result is not None}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to retry queue item %d (%s): %s", id, type, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()

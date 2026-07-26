"""Kodi API — settings and synchronization."""

from typing import Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import encrypt_api_key, decrypt_api_key
from app.services import kodi as kodi_service
from app.services.kodi import discover_kodi, sync_kodi
from app.utils.cache import cache

router = APIRouter(
    prefix="/api/kodi",
    tags=["kodi"],
    dependencies=[Depends(get_current_user)],
)

@router.get("/discover")
async def discover_instances() -> List[dict]:
    """Discover Kodi instances using mDNS."""
    return await discover_kodi()

@router.post("/sync")
async def trigger_kodi_sync(db: AsyncSession = Depends(get_db)):
    """Trigger library scan on all configured Kodis."""
    return await sync_kodi(db)


@router.post("/play")
async def play_on_kodi(data: dict, db: AsyncSession = Depends(get_db)):
    """Start playback of a movie (by TMDB id) on a Kodi instance."""
    tmdb_id = data.get("tmdb_id")
    if not tmdb_id:
        return {"status": "error", "detail": "tmdb_id requis"}
    result = await kodi_service.play_movie(db, int(tmdb_id), data.get("service_id"))

    from app.services.activity_log import log_event
    ok = result.get("status") == "ok"
    await log_event(
        category="playback",
        action="kodi_play",
        status="ok" if ok else "ko",
        source="arrmada",
        media_type="movie",
        media_id=data.get("media_id"),
        tmdb_id=int(tmdb_id),
        title=data.get("title"),
        device=result.get("kodi"),
        detail=None if ok else result.get("detail"),
        meta={"movieid": result.get("movieid")} if ok else None,
    )
    return result


@router.get("/now-playing")
async def now_playing(db: AsyncSession = Depends(get_db)):
    """Current Kodi playback state (for the remote on the media detail page)."""
    return await kodi_service.get_now_playing(db)


@router.post("/control")
async def control(data: dict, db: AsyncSession = Depends(get_db)):
    """Send a remote command: playpause | stop | seek | volume | mute."""
    action = (data or {}).get("action")
    if not action:
        return {"status": "error", "detail": "action requise"}
    return await kodi_service.control_player(db, action, (data or {}).get("value"))


@router.get("/watched-status")
async def watched_status(db: AsyncSession = Depends(get_db)):
    """Watched/resume state per TMDB id from Kodi (cached 60s)."""
    async def _compute():
        return await kodi_service.get_watched_status(db)

    return await cache.get_or_set("kodi:watched", _compute, ttl_seconds=60)


@router.post("/clean")
async def clean_kodi(data: dict | None = None, db: AsyncSession = Depends(get_db)):
    """Trigger VideoLibrary.Clean on a Kodi instance."""
    cache.invalidate("kodi:watched")
    return await kodi_service.clean_library(db, (data or {}).get("service_id"))


@router.get("/drift")
async def kodi_drift(db: AsyncSession = Depends(get_db)):
    """Movies in Radarr but missing from the Kodi library."""
    return await kodi_service.get_drift(db)


@router.post("/test/{service_id}")
async def test_kodi(service_id: int, db: AsyncSession = Depends(get_db)):
    """Ping a Kodi instance and read its version."""
    return await kodi_service.test_connection(db, service_id)

@router.get("/settings")
async def get_kodi_settings(db: AsyncSession = Depends(get_db)):
    """Fetch all Kodi services from database."""
    stmt = select(Service).where(Service.type == "kodi")
    result = await db.execute(stmt)
    kodis = result.scalars().all()
    
    return [
        {
            "id": k.id,
            "name": k.name,
            "url": k.url,
            "is_enabled": k.is_enabled,
            "api_key": decrypt_api_key(k.api_key) if k.api_key else ""
        }
        for k in kodis
    ]

@router.post("/settings")
async def add_kodi_setting(data: dict, db: AsyncSession = Depends(get_db)):
    """Add or update a Kodi instance — idempotent by URL to avoid duplicates.

    Adding the same Kodi (same URL) twice used to create a duplicate row, so a
    sync would scan the same Kodi several times. We now reuse the existing entry.
    """
    url = (data.get("url") or "").strip()

    existing = None
    if url:
        res = await db.execute(
            select(Service).where(Service.type == "kodi", Service.url == url)
        )
        existing = res.scalars().first()

    if existing:
        existing.name = data.get("name", existing.name)
        if data.get("api_key"):
            existing.api_key = encrypt_api_key(data.get("api_key", ""))
        existing.is_enabled = data.get("is_enabled", True)
        await db.commit()
        await db.refresh(existing)
        return {"id": existing.id, "message": "Kodi mis à jour"}

    new_kodi = Service(
        name=data.get("name", "Kodi"),
        type="kodi",
        url=url,
        api_key=encrypt_api_key(data.get("api_key", "")),
        is_enabled=data.get("is_enabled", True)
    )
    db.add(new_kodi)
    await db.commit()
    await db.refresh(new_kodi)
    return {"id": new_kodi.id, "message": "Kodi added"}

@router.delete("/settings/{service_id}")
async def delete_kodi_setting(service_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a Kodi instance."""
    svc = await db.get(Service, service_id)
    if svc and svc.type == "kodi":
        await db.delete(svc)
        await db.commit()
    return {"status": "deleted"}

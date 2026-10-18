"""Cast API — discover Google Cast devices and cast Jellyfin streams to them."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services import cast as cast_service
from app.services import jellyfin as jellyfin_service
from app.services.activity_log import log_event
from app.services.encryption import encrypt_api_key

router = APIRouter(
    prefix="/api/cast",
    tags=["cast"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/devices")
async def devices(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """List known Cast devices."""
    return await cast_service.list_devices(db)


@router.post("/discover")
async def discover(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Scan the LAN for Cast devices (TCP :8009 + connect) and persist them."""
    return await cast_service.discover(db)


@router.delete("/devices/{device_id}")
async def delete_device(device_id: int, db: AsyncSession = Depends(get_db)):
    return await cast_service.delete_device(db, device_id)


@router.post("/play")
async def play(data: dict, db: AsyncSession = Depends(get_db)):
    """Cast a movie (TMDB id) or an episode (series TVDB id + season + episode)
    to a device via a Jellyfin transcoded stream."""
    tmdb_id = data.get("tmdb_id")
    tvdb_id, season, episode = data.get("tvdb_id"), data.get("season"), data.get("episode")
    device_id = data.get("device_id")
    is_episode = not tmdb_id and tvdb_id and season is not None and episode is not None
    if not device_id or not (tmdb_id or is_episode):
        return {
            "status": "error",
            "detail": "device_id et tmdb_id (film) ou tvdb_id + season + episode requis",
        }

    if is_episode:
        stream = await jellyfin_service.build_episode_stream(
            db, int(tvdb_id), int(season), int(episode)
        )
        missing = "Épisode introuvable dans Jellyfin (ou Jellyfin non configuré)."
    else:
        stream = await jellyfin_service.build_movie_stream(db, int(tmdb_id))
        missing = "Film introuvable dans Jellyfin (ou Jellyfin non configuré)."
    if not stream:
        return {"status": "error", "detail": missing}

    result = await cast_service.cast_stream(
        db,
        int(device_id),
        stream["url"],
        stream["content_type"],
        stream["title"] or data.get("title"),
    )

    dev = await cast_service._get(db, int(device_id))
    ok = result.get("status") == "casting"
    await log_event(
        category="playback",
        action="cast_play",
        status="ok" if ok else "ko",
        source="arrmada",
        media_type="episode" if is_episode else "movie",
        media_id=data.get("media_id"),
        tmdb_id=None if is_episode else int(tmdb_id),
        title=stream.get("title") or data.get("title"),
        device=dev.name if dev else None,
        detail=None if ok else result.get("detail"),
        meta={"jellyfin_item": stream.get("item_id")} if ok else None,
    )
    return result


@router.post("/control")
async def control(data: dict, db: AsyncSession = Depends(get_db)):
    """Control a casting device: pause | play | stop | quit | volume | mute."""
    device_id = data.get("device_id")
    action = data.get("action")
    if not device_id or not action:
        return {"status": "error", "detail": "device_id et action requis"}
    return await cast_service.control(db, int(device_id), action, data.get("value"))


@router.get("/status")
async def status(device_id: int, db: AsyncSession = Depends(get_db)):
    """Read what a device is currently playing."""
    return await cast_service.status(db, device_id)


# ── Jellyfin config (backing store for cast streams) ───────────


@router.get("/jellyfin")
async def get_jellyfin(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Service).where(Service.type == "jellyfin"))
    svc = res.scalars().first()
    if not svc:
        return {"configured": False}
    return {
        "configured": True,
        "id": svc.id,
        "name": svc.name,
        "url": svc.url,
        "is_enabled": svc.is_enabled,
    }


@router.post("/jellyfin")
async def set_jellyfin(data: dict, db: AsyncSession = Depends(get_db)):
    """Configure the Jellyfin server (idempotent by type)."""
    url = (data.get("url") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    if not url:
        return {"status": "error", "detail": "url requise"}

    res = await db.execute(select(Service).where(Service.type == "jellyfin"))
    svc = res.scalars().first()
    if not svc and not api_key:
        return {"status": "error", "detail": "api_key requise"}
    if svc:
        svc.name = data.get("name", svc.name)
        svc.url = url
        # Keep the stored key when the field is left blank on an update.
        if api_key:
            svc.api_key = encrypt_api_key(api_key)
        svc.is_enabled = data.get("is_enabled", True)
    else:
        svc = Service(
            name=data.get("name", "Jellyfin"),
            type="jellyfin",
            url=url,
            api_key=encrypt_api_key(api_key),
            is_enabled=data.get("is_enabled", True),
        )
        db.add(svc)
    await db.commit()
    return {"status": "ok"}


@router.get("/jellyfin/test")
async def test_jellyfin(db: AsyncSession = Depends(get_db)):
    return await jellyfin_service.test_connection(db)

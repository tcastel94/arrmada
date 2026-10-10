"""Yamaha AVR API — discovery, instances and remote control."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services import yamaha as yamaha_service
from app.services.encryption import encrypt_api_key

router = APIRouter(
    prefix="/api/yamaha",
    tags=["yamaha"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/discover")
async def discover(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Find Yamaha AVRs on the LAN (SSDP + YXC probe of known subnets)."""
    return await yamaha_service.discover(db)


@router.get("/state")
async def state(service_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """Live power/volume/mute/input of the configured AVR(s)."""
    return await yamaha_service.get_state(db, service_id)


@router.get("/inputs")
async def inputs(service_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """Available input ids for the main zone."""
    return await yamaha_service.list_inputs(db, service_id)


@router.post("/control")
async def control(data: dict, db: AsyncSession = Depends(get_db)):
    """Send a command: volume | volume_step | mute | power | input."""
    action = (data or {}).get("action")
    if not action:
        return {"status": "error", "detail": "action requise"}
    return await yamaha_service.control(
        db,
        action,
        (data or {}).get("value"),
        service_id=(data or {}).get("service_id"),
        zone=(data or {}).get("zone", "main"),
    )


@router.get("/profiles")
async def get_profiles(db: AsyncSession = Depends(get_db)):
    """Retrieve room sound profiles (Salon & Salle de Cinéma)."""
    return await yamaha_service.get_room_profiles(db)


@router.post("/profiles")
async def save_profile(data: dict, db: AsyncSession = Depends(get_db)):
    """Save or update audio settings for a room profile."""
    room = (data or {}).get("room", "salon")
    profile = (data or {}).get("profile", {})
    return await yamaha_service.save_room_profile(db, room, profile)


@router.post("/preset/apply")
async def apply_preset(data: dict, db: AsyncSession = Depends(get_db)):
    """Apply room audio preset (salon / cinema) based on media context."""
    room = (data or {}).get("room", "salon")
    media_type = (data or {}).get("media_type", "movie")
    audio_codec = (data or {}).get("audio_codec")
    audio_channels = (data or {}).get("audio_channels")
    service_id = (data or {}).get("service_id")

    return await yamaha_service.apply_preset(
        db,
        room=room,
        media_type=media_type,
        audio_codec=audio_codec,
        audio_channels=audio_channels,
        service_id=service_id,
    )


@router.post("/test/{service_id}")
async def test(service_id: int, db: AsyncSession = Depends(get_db)):
    """Ping an AVR and read its model / status."""
    return await yamaha_service.test_connection(db, service_id)


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """List configured Yamaha AVRs."""
    res = await db.execute(select(Service).where(Service.type == "yamaha"))
    return [
        {"id": s.id, "name": s.name, "url": s.url, "is_enabled": s.is_enabled}
        for s in res.scalars().all()
    ]


@router.post("/settings")
async def add_setting(data: dict, db: AsyncSession = Depends(get_db)):
    """Add or update an AVR — idempotent by URL to avoid duplicates."""
    from app.services.yamaha import _base

    url = _base(data.get("url") or "")
    if not url:
        return {"status": "error", "detail": "url requise"}

    res = await db.execute(select(Service).where(Service.type == "yamaha", Service.url == url))
    existing = res.scalars().first()
    if existing:
        existing.name = data.get("name", existing.name)
        existing.is_enabled = data.get("is_enabled", True)
        await db.commit()
        await db.refresh(existing)
        return {"id": existing.id, "message": "Ampli mis à jour"}

    svc = Service(
        name=data.get("name", "Yamaha"),
        type="yamaha",
        url=url,
        api_key=encrypt_api_key(""),
        is_enabled=data.get("is_enabled", True),
    )
    db.add(svc)
    await db.commit()
    await db.refresh(svc)
    return {"id": svc.id, "message": "Ampli ajouté"}


@router.delete("/settings/{service_id}")
async def delete_setting(service_id: int, db: AsyncSession = Depends(get_db)):
    """Remove an AVR."""
    svc = await db.get(Service, service_id)
    if svc and svc.type == "yamaha":
        await db.delete(svc)
        await db.commit()
    return {"status": "deleted"}

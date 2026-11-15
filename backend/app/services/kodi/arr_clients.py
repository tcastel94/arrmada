"""Add-on Kodi : clients Radarr / Sonarr / Bazarr construits depuis les services enregistrés."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key


# ── Feature: Kodi Add-on integration ─────────────────────────
async def _get_radarr_client(db: AsyncSession):
    from app.services.radarr import RadarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "radarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return RadarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


async def _get_sonarr_client(db: AsyncSession):
    from app.services.sonarr import SonarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "sonarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return SonarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


async def _get_bazarr_client(db: AsyncSession):
    from app.services.bazarr import BazarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "bazarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return BazarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))

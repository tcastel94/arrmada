"""Health checker — monitors all connected *arr services."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import HealthEvent, Service
from app.services.arr_client import ArrBaseClient, HealthStatus
from app.services.encryption import decrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Service type → client class mapping (expanded in Phase 3)
_CLIENT_MAP: dict[str, type[ArrBaseClient]] = {}


def _register_client(service_type: str, client_cls: type[ArrBaseClient]) -> None:
    """Register a client class for a service type."""
    _CLIENT_MAP[service_type] = client_cls


def _init_client_map() -> None:
    """Lazily populate the client map to avoid circular imports."""
    if _CLIENT_MAP:
        return
    from app.services.sonarr import SonarrClient
    from app.services.radarr import RadarrClient
    from app.services.lidarr import LidarrClient
    from app.services.readarr import ReadarrClient
    from app.services.prowlarr import ProwlarrClient
    from app.services.bazarr import BazarrClient
    from app.services.jellyfin import JellyfinClient
    from app.services.sabnzbd import SabnzbdClient

    _register_client("sonarr", SonarrClient)
    _register_client("radarr", RadarrClient)
    _register_client("lidarr", LidarrClient)
    _register_client("readarr", ReadarrClient)
    _register_client("prowlarr", ProwlarrClient)
    _register_client("bazarr", BazarrClient)
    _register_client("jellyfin", JellyfinClient)
    _register_client("sabnzbd", SabnzbdClient)


def _build_client(service: Service) -> ArrBaseClient:
    """Instantiate the appropriate client for a service."""
    _init_client_map()
    api_key = decrypt_api_key(service.api_key)
    client_cls = _CLIENT_MAP.get(service.type, ArrBaseClient)
    return client_cls(url=service.url, api_key=api_key)


async def check_service(service: Service) -> HealthStatus:
    """Run a health check on a single service and return the result."""
    client = _build_client(service)
    try:
        return await client.health_check()
    finally:
        await client.close()


async def check_and_record(service: Service, db: AsyncSession) -> HealthStatus:
    """Check one service, record the event in DB, and update the service row."""
    previous_status = service.last_status
    result = await check_service(service)

    # Record health event
    event = HealthEvent(
        service_id=service.id,
        status=result.status,
        latency_ms=result.latency_ms,
        error_message=result.error,
    )
    db.add(event)

    # Update service status
    service.last_health_check = datetime.utcnow()
    service.last_status = result.status
    service.last_latency_ms = result.latency_ms
    if result.version:
        service.version = result.version

    # ── Telegram alerts on status transition ──────────────────
    try:
        from app.services.telegram import notify_service_down, notify_service_recovered

        if previous_status == "online" and result.status == "offline":
            await notify_service_down(service.name, result.error or "Unknown")
        elif previous_status == "offline" and result.status == "online":
            await notify_service_recovered(service.name, result.latency_ms or 0)
    except Exception as exc:
        logger.debug("Telegram notification skipped: %s", exc)

    await db.flush()
    return result


async def check_all_services(db: AsyncSession) -> list[dict]:
    """Run health checks on all enabled services.

    Returns a list of dicts with service info + health result.
    """
    stmt = select(Service).where(Service.is_enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    services = result.scalars().all()

    results = []
    for svc in services:
        try:
            health = await check_and_record(svc, db)
            results.append(
                {
                    "service_id": svc.id,
                    "service_name": svc.name,
                    "service_type": svc.type,
                    "status": health.status,
                    "latency_ms": health.latency_ms,
                    "version": health.version,
                    "error": health.error,
                }
            )
        except Exception as exc:
            logger.error("Health check failed for %s: %s", svc.name, exc)
            results.append(
                {
                    "service_id": svc.id,
                    "service_name": svc.name,
                    "service_type": svc.type,
                    "status": "offline",
                    "latency_ms": None,
                    "version": None,
                    "error": str(exc),
                }
            )

    await db.commit()
    return results

"""Setup / Onboarding API — first-launch wizard endpoints.

These endpoints are partially accessible WITHOUT authentication
to allow initial setup of the application.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.models.service import Service
from app.services import encryption
from app.services.discovery import discover_services
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/setup", tags=["setup"])


# ── Schemas ───────────────────────────────────────────────────
class SetupStatus(BaseModel):
    """Current setup state of the application."""

    is_configured: bool = Field(description="Whether initial setup has been completed")
    has_services: bool = Field(description="Whether any services are configured")
    services_count: int = Field(description="Number of configured services")
    database_type: str = Field(description="Database backend in use (sqlite or postgresql)")


class DiscoveredService(BaseModel):
    """A service discovered on the network."""

    type: str
    name: str
    url: str
    port: int
    host: str
    version: str | None = None
    needs_api_key: bool = True
    status: str = "found"


class ServiceSetupItem(BaseModel):
    """A service to add during setup."""

    name: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern=r"^(sonarr|radarr|lidarr|readarr|prowlarr|bazarr|jellyfin|sabnzbd)$")
    url: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    is_enabled: bool = True


class SetupComplete(BaseModel):
    """Payload to finalize setup."""

    services: list[ServiceSetupItem] = Field(
        description="Services to configure during setup"
    )


class SetupResult(BaseModel):
    """Result of the setup process."""

    success: bool
    services_added: int
    message: str


# ── Endpoints ─────────────────────────────────────────────────
@router.get(
    "/status",
    response_model=SetupStatus,
    summary="Check setup status",
    description="Check if the application has been configured. "
    "This endpoint does NOT require authentication.",
)
async def setup_status(db: AsyncSession = Depends(get_db)) -> SetupStatus:
    """Check if ArrMada is configured (no auth required)."""
    result = await db.execute(select(func.count(Service.id)))
    count = result.scalar() or 0

    db_type = "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite"

    return SetupStatus(
        is_configured=count > 0,
        has_services=count > 0,
        services_count=count,
        database_type=db_type,
    )


@router.post(
    "/discover",
    response_model=list[DiscoveredService],
    summary="Discover *arr services on the network",
    description="Scan the local network for running *arr services. "
    "Probes common ports (8989, 7878, 8686, etc.) on local IPs. "
    "This endpoint does NOT require authentication (for first setup).",
)
async def discover(
    hosts: list[str] | None = None,
) -> list[DiscoveredService]:
    """Scan the network for *arr services."""
    discovered = await discover_services(
        scan_hosts=hosts,
        include_localhost=True,
    )
    return [DiscoveredService(**svc) for svc in discovered]


@router.post(
    "/complete",
    response_model=SetupResult,
    status_code=status.HTTP_201_CREATED,
    summary="Complete initial setup",
    description="Finalize the setup by adding the selected services. "
    "Can only be called when no services are configured yet. "
    "This endpoint does NOT require authentication (for first setup).",
)
async def complete_setup(
    body: SetupComplete,
    db: AsyncSession = Depends(get_db),
) -> SetupResult:
    """Save configured services and mark setup as complete."""
    # Check if already configured
    result = await db.execute(select(func.count(Service.id)))
    existing = result.scalar() or 0

    if existing > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already completed. Use the Services page to add more services.",
        )

    if not body.services:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one service is required.",
        )

    added = 0
    for svc in body.services:
        service = Service(
            name=svc.name,
            type=svc.type,
            url=svc.url.rstrip("/"),
            api_key=encryption.encrypt_api_key(svc.api_key),
            is_enabled=svc.is_enabled,
        )
        db.add(service)
        added += 1

    await db.flush()

    logger.info("Setup completed: %d services added", added)

    return SetupResult(
        success=True,
        services_added=added,
        message=f"Configuration terminée ! {added} service(s) ajouté(s).",
    )

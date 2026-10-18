"""Services CRUD + health check endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import HealthEvent, Service
from app.schemas.service import (
    HealthEventResponse,
    ServiceCreate,
    ServiceHealthResponse,
    ServiceResponse,
    ServiceUpdate,
    TestConnectionResponse,
)
from app.services import encryption, health_checker

router = APIRouter(
    prefix="/api/services",
    tags=["services"],
    dependencies=[Depends(get_current_user)],
)


# ── Catégories ────────────────────────────────────────────────
# La table `services` stocke aussi des APPAREILS du salon (Kodi, ampli
# Yamaha) qui ont leurs propres routes (/api/kodi, /api/yamaha). Ils ne
# sont pas des services *arr : sans filtre, le dashboard et la page
# Services les affichaient comme des *arr « inconnus » toujours hors ligne.
#
# Comportement retenu (rétro-compatible) :
#   GET /api/services                    → services *arr uniquement (défaut)
#   GET /api/services?category=devices   → appareils uniquement
#   GET /api/services?category=all       → tout (ancien comportement)
# Même paramètre sur /api/services/health/all.
DEVICE_TYPES = frozenset({"kodi", "yamaha"})
Category = Literal["arr", "devices", "all"]


def _in_category(service_type: str, category: Category) -> bool:
    is_device = (service_type or "").lower() in DEVICE_TYPES
    if category == "devices":
        return is_device
    if category == "arr":
        return not is_device
    return True


# ── List ──────────────────────────────────────────────────────
@router.get("", response_model=list[ServiceResponse])
async def list_services(
    category: Category = Query("arr", description="arr (défaut) | devices | all"),
    db: AsyncSession = Depends(get_db),
) -> list[ServiceResponse]:
    """List configured services (*arr only by default, see `category`)."""
    result = await db.execute(select(Service).order_by(Service.name))
    services = [s for s in result.scalars().all() if _in_category(s.type, category)]
    return [ServiceResponse.model_validate(s) for s in services]


# ── Test a configuration BEFORE saving it ─────────────────────
class ServiceDraftTest(BaseModel):
    """Connection parameters to validate before creating/updating a service."""

    type: str = Field(pattern=r"^(sonarr|radarr|lidarr|readarr|prowlarr|bazarr|jellyfin|sabnzbd)$")
    url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(None, max_length=200)
    # When editing, an empty api_key means "reuse the stored key of this service".
    service_id: int | None = None


@router.post("/test", response_model=TestConnectionResponse)
async def test_draft_connection(
    body: ServiceDraftTest,
    db: AsyncSession = Depends(get_db),
) -> TestConnectionResponse:
    """Test URL + API key without saving anything (« Tester avant d'enregistrer »)."""
    api_key = (body.api_key or "").strip()
    if not api_key and body.service_id is not None:
        existing = await db.get(Service, body.service_id)
        if existing and existing.api_key:
            api_key = encryption.decrypt_api_key(existing.api_key)
    if not api_key:
        return TestConnectionResponse(success=False, status="unknown", error="Clé API manquante")

    # Objet transitoire : jamais ajouté à la session, donc jamais enregistré.
    draft = Service(
        name="draft",
        type=body.type,
        url=body.url.strip().rstrip("/"),
        api_key=encryption.encrypt_api_key(api_key),
        is_enabled=True,
    )
    result = await health_checker.check_service(draft)
    return TestConnectionResponse(
        success=result.status == "online",
        status=result.status,
        latency_ms=result.latency_ms,
        version=result.version,
        error=result.error,
    )


# ── Create ────────────────────────────────────────────────────
@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    body: ServiceCreate,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Add a new *arr service connection."""
    service = Service(
        name=body.name,
        type=body.type,
        url=body.url.rstrip("/"),
        api_key=encryption.encrypt_api_key(body.api_key),
        is_enabled=body.is_enabled,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return ServiceResponse.model_validate(service)


# ── Read ──────────────────────────────────────────────────────
@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Get a single service by ID."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return ServiceResponse.model_validate(service)


# ── Update ────────────────────────────────────────────────────
@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    body: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
) -> ServiceResponse:
    """Update an existing service."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if body.name is not None:
        service.name = body.name
    if body.url is not None:
        service.url = body.url.rstrip("/")
    if body.api_key is not None:
        service.api_key = encryption.encrypt_api_key(body.api_key)
    if body.is_enabled is not None:
        service.is_enabled = body.is_enabled

    await db.flush()
    await db.refresh(service)
    return ServiceResponse.model_validate(service)


# ── Delete ────────────────────────────────────────────────────
@router.delete("/{service_id}")
async def delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a service and all its health events."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.delete(service)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Test connection ───────────────────────────────────────────
@router.post("/{service_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    service_id: int,
    db: AsyncSession = Depends(get_db),
) -> TestConnectionResponse:
    """Test connectivity to a service."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    result = await health_checker.check_and_record(service, db)
    return TestConnectionResponse(
        success=result.status == "online",
        status=result.status,
        latency_ms=result.latency_ms,
        version=result.version,
        error=result.error,
    )


# ── Global health ────────────────────────────────────────────
@router.get("/health/all", response_model=list[ServiceHealthResponse])
async def global_health(
    category: Category = Query("arr", description="arr (défaut) | devices | all"),
    db: AsyncSession = Depends(get_db),
) -> list[ServiceHealthResponse]:
    """Run health checks on all enabled services (*arr only by default)."""
    results = await health_checker.check_all_services(db)
    return [
        ServiceHealthResponse(**r)
        for r in results
        if _in_category(r.get("service_type", ""), category)
    ]


# ── Health history for a service ──────────────────────────────
@router.get("/{service_id}/health", response_model=list[HealthEventResponse])
async def service_health_history(
    service_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[HealthEventResponse]:
    """Get recent health events for a service."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    stmt = (
        select(HealthEvent)
        .where(HealthEvent.service_id == service_id)
        .order_by(HealthEvent.checked_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [HealthEventResponse.model_validate(e) for e in events]

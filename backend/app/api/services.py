"""Services CRUD + health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.services import encryption
from app.services import health_checker

router = APIRouter(
    prefix="/api/services",
    tags=["services"],
    dependencies=[Depends(get_current_user)],
)


# ── List ──────────────────────────────────────────────────────
@router.get("", response_model=list[ServiceResponse])
async def list_services(db: AsyncSession = Depends(get_db)) -> list[ServiceResponse]:
    """List all configured services."""
    result = await db.execute(select(Service).order_by(Service.name))
    services = result.scalars().all()
    return [ServiceResponse.model_validate(s) for s in services]


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
    db: AsyncSession = Depends(get_db),
) -> list[ServiceHealthResponse]:
    """Run health checks on all enabled services."""
    results = await health_checker.check_all_services(db)
    return [ServiceHealthResponse(**r) for r in results]


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

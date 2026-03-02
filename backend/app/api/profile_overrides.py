"""Profile Override API — manage per-media TRaSH profile assignments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.profile_override import ProfileOverride
from app.services.trash_guides import get_trash_cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/profile-overrides",
    tags=["profile-overrides"],
    dependencies=[Depends(get_current_user)],
)


# ── Schemas ────────────────────────────────────────────────────

class OverrideCreate(BaseModel):
    media_type: str = Field(..., description="'series' or 'movie'")
    external_id: int = Field(..., description="Sonarr series ID or Radarr movie ID")
    title: str = Field(..., description="Display title")
    profile_name: str = Field(..., description="TRaSH profile filename, e.g. 'french-multi-vo-bluray-web-2160p'")
    service_id: int = Field(..., description="Sonarr or Radarr service ID")
    note: str | None = None


class OverrideOut(BaseModel):
    id: int
    media_type: str
    external_id: int
    title: str
    profile_name: str
    service_id: int
    note: str | None
    created_at: str


class AvailableProfile(BaseModel):
    filename: str
    display_name: str
    service_type: str


# ── Endpoints ──────────────────────────────────────────────────

@router.get("", summary="List all profile overrides")
async def list_overrides(
    service_id: int | None = None,
    media_type: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[OverrideOut]:
    """List all profile overrides, optionally filtered by service or media type."""
    stmt = select(ProfileOverride).order_by(ProfileOverride.title)
    if service_id is not None:
        stmt = stmt.where(ProfileOverride.service_id == service_id)
    if media_type is not None:
        stmt = stmt.where(ProfileOverride.media_type == media_type)

    result = await db.execute(stmt)
    overrides = result.scalars().all()

    return [
        OverrideOut(
            id=o.id,
            media_type=o.media_type,
            external_id=o.external_id,
            title=o.title,
            profile_name=o.profile_name,
            service_id=o.service_id,
            note=o.note,
            created_at=o.created_at.isoformat() if o.created_at else "",
        )
        for o in overrides
    ]


@router.post("", summary="Create a profile override", status_code=201)
async def create_override(
    body: OverrideCreate,
    db: AsyncSession = Depends(get_db),
) -> OverrideOut:
    """Create or update a TRaSH profile override for a specific media."""
    # Check if an override already exists for this media
    stmt = select(ProfileOverride).where(
        ProfileOverride.service_id == body.service_id,
        ProfileOverride.external_id == body.external_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update
        existing.profile_name = body.profile_name
        existing.title = body.title
        existing.note = body.note
        await db.commit()
        await db.refresh(existing)
        return OverrideOut(
            id=existing.id,
            media_type=existing.media_type,
            external_id=existing.external_id,
            title=existing.title,
            profile_name=existing.profile_name,
            service_id=existing.service_id,
            note=existing.note,
            created_at=existing.created_at.isoformat() if existing.created_at else "",
        )

    # Create new
    override = ProfileOverride(
        media_type=body.media_type,
        external_id=body.external_id,
        title=body.title,
        profile_name=body.profile_name,
        service_id=body.service_id,
        note=body.note,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)

    return OverrideOut(
        id=override.id,
        media_type=override.media_type,
        external_id=override.external_id,
        title=override.title,
        profile_name=override.profile_name,
        service_id=override.service_id,
        note=override.note,
        created_at=override.created_at.isoformat() if override.created_at else "",
    )


@router.delete("/{override_id}", summary="Delete a profile override")
async def delete_override(
    override_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove a profile override (revert to default)."""
    stmt = delete(ProfileOverride).where(ProfileOverride.id == override_id)
    result = await db.execute(stmt)
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Override not found")
    return {"deleted": True}


@router.get("/profiles", summary="List available TRaSH profiles")
async def list_available_profiles(
    service_type: str = "sonarr",
) -> list[AvailableProfile]:
    """List all TRaSH quality profiles available for a service type."""
    cache = get_trash_cache()
    qps = cache.get_quality_profiles(service_type.lower())

    profiles = []
    seen = set()
    for qp in qps:
        filename = qp.get("_source_file", "").replace(".json", "")
        if not filename or filename in seen:
            continue
        seen.add(filename)
        profiles.append(AvailableProfile(
            filename=filename,
            display_name=qp.get("name", filename),
            service_type=service_type.lower(),
        ))

    return sorted(profiles, key=lambda p: p.display_name)

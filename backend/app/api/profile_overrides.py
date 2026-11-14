"""Profile Override API — manage per-media TRaSH profile assignments."""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
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
    profile_name: str = Field(
        ..., description="TRaSH profile filename, e.g. 'french-multi-vo-bluray-web-2160p'"
    )
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
        profiles.append(
            AvailableProfile(
                filename=filename,
                display_name=qp.get("name", filename),
                service_type=service_type.lower(),
            )
        )

    return sorted(profiles, key=lambda p: p.display_name)


# ── Apply Override to Sonarr/Radarr ───────────────────────────


class ApplyOverrideResult(BaseModel):
    success: bool
    cfs_created: int = 0
    cfs_updated: int = 0
    profile_name: str = ""
    profile_id: int | None = None
    media_updated: bool = False
    errors: list[str] = []


@router.post(
    "/{override_id}/apply",
    response_model=ApplyOverrideResult,
    summary="Apply a profile override to Sonarr/Radarr",
)
async def apply_override(
    override_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Apply the TRaSH profile override to the actual Sonarr/Radarr instance.

    This will:
    1. Reuse the Quality Profile if it already exists (never rewritten here)
    2. Otherwise create it, with its Custom Formats and their TRaSH scores
    3. Assign the Quality Profile to the specific series/movie
    """

    from app.models.service import Service
    from app.services.arr_client import ArrBaseClient
    from app.services.encryption import decrypt_api_key
    from app.services.notification_service import create_notification

    # 1. Get the override
    stmt = select(ProfileOverride).where(ProfileOverride.id == override_id)
    result = await db.execute(stmt)
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    # 2. Get the service — if service_id is 0 or invalid, find by type
    service = None
    if override.service_id and override.service_id > 0:
        stmt = select(Service).where(Service.id == override.service_id)
        result = await db.execute(stmt)
        service = result.scalar_one_or_none()

    if not service:
        # Fallback: find first enabled Sonarr or Radarr service by media type
        expected_type = "sonarr" if override.media_type == "series" else "radarr"
        logger.info(
            "Override %d: service_id=%s not found, searching for type '%s'",
            override_id,
            override.service_id,
            expected_type,
        )
        stmt = (
            select(Service)
            .where(
                Service.type.in_([expected_type, expected_type.capitalize()]),
                Service.is_enabled == True,  # noqa: E712
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        service = result.scalar_one_or_none()

        if not service:
            # Last resort: get ANY sonarr/radarr service regardless of enabled
            logger.warning("No enabled %s service, trying all services", expected_type)
            stmt = (
                select(Service)
                .where(Service.type.in_([expected_type, expected_type.capitalize()]))
                .limit(1)
            )
            result = await db.execute(stmt)
            service = result.scalar_one_or_none()

        if service:
            # Update override with the found service_id for next time
            logger.info(
                "Found service %s (id=%d) for override %d", service.name, service.id, override_id
            )
            override.service_id = service.id

    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"No {override.media_type == 'series' and 'Sonarr' or 'Radarr'} service found. Please check your services are configured.",
        )

    service_type = service.type.lower()
    if service_type not in ("sonarr", "radarr"):
        raise HTTPException(status_code=400, detail="Only Sonarr/Radarr supported")

    # 3. Données TRaSH (une panne de GitHub ne bloque pas si le cache est rempli)
    from app.services import media_version as mv
    from app.services.trash_apply import build_profile_plan

    cache = get_trash_cache()
    if cache.is_stale:
        with contextlib.suppress(Exception):
            await cache.sync()

    # 4. Build client
    client = ArrBaseClient(
        url=service.url,
        api_key=decrypt_api_key(service.api_key),
        timeout=60,
    )
    client.API_PREFIX = "/api/v3"

    errors: list[str] = []
    cfs_created = 0
    cfs_updated = 0
    profile_id: int | None = None
    media_updated = False
    qp_display_name = override.profile_name
    kind = "series" if override.media_type == "series" else "movie"

    try:
        # Même moteur que « Appliquer TRaSH » et que la « version par titre »
        # (l'ancien code clonait le premier profil venu et laissait tous les
        # scores à 0, donc sans effet sur le choix des releases). Un profil
        # déjà présent est repris tel quel ; sinon il est créé, avec les
        # groupes écran / son du profil actuel du média.
        media_data = await client.get(f"/{kind}/{override.external_id}")
        profiles = await client.get("/qualityprofile")
        current = next(
            (p for p in profiles if p.get("id") == media_data.get("qualityProfileId")), None
        )
        plan = build_profile_plan(
            cache,
            service_type,
            override.profile_name,
            extra_groups=mv.infer_groups(cache, service_type, current),
        )
        if plan is None:
            raise HTTPException(
                status_code=404,
                detail=f"TRaSH profile '{override.profile_name}' not found in cache",
            )
        qp_display_name = plan.name
        before = {str(cf["name"]).lower() for cf in await client.get("/customformat")}
        profile, created = await mv.ensure_profile(client, service_type, plan, profiles)
        profile_id = profile["id"]
        if created:
            cfs_created = sum(1 for fmt in plan.formats if fmt.name.lower() not in before)
            cfs_updated = len(plan.formats) - cfs_created

        if media_data.get("qualityProfileId") != profile_id:
            media_data["qualityProfileId"] = profile_id
            await client.put(f"/{kind}/{override.external_id}", media_data)
        media_updated = True

        # Notification
        with contextlib.suppress(Exception):
            await create_notification(
                db,
                type="trash_apply",
                title=f"Profil TRaSH appliqué : {override.title}",
                message=(
                    f"Profil '{qp_display_name}' → {cfs_created} CFs créés, "
                    f"{cfs_updated} mis à jour"
                ),
                severity="success" if not errors else "warning",
                service_name=service.name,
            )

    except HTTPException:
        raise
    except Exception as e:
        errors.append(f"Connection error: {e}")
        logger.error("Apply override failed: %s", e, exc_info=True)
    finally:
        await client.close()

    await db.commit()

    return ApplyOverrideResult(
        success=len(errors) == 0,
        cfs_created=cfs_created,
        cfs_updated=cfs_updated,
        profile_name=qp_display_name,
        profile_id=profile_id,
        media_updated=media_updated,
        errors=errors,
    )

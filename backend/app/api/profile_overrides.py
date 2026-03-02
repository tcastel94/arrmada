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
    1. Create/update all Custom Formats referenced by the TRaSH profile
    2. Create or update a Quality Profile with correct CF scores
    3. Assign the Quality Profile to the specific series/movie
    """
    from typing import Any

    from app.models.service import Service
    from app.services.arr_client import ArrBaseClient
    from app.services.encryption import decrypt_api_key
    from app.services.trash_guides import get_trash_cache
    from app.services.notification_service import create_notification

    # 1. Get the override
    stmt = select(ProfileOverride).where(ProfileOverride.id == override_id)
    result = await db.execute(stmt)
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    # 2. Get the service
    stmt = select(Service).where(Service.id == override.service_id)
    result = await db.execute(stmt)
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    service_type = service.type.lower()
    if service_type not in ("sonarr", "radarr"):
        raise HTTPException(status_code=400, detail="Only Sonarr/Radarr supported")

    # 3. Get TRaSH data
    cache = get_trash_cache()
    if cache.is_stale:
        await cache.sync()

    # Find the QP by profile_name (= source filename without .json)
    qp_data = None
    for qp in cache.get_quality_profiles(service_type):
        source = qp.get("_source_file", "").replace(".json", "")
        if source == override.profile_name:
            qp_data = qp
            break

    if not qp_data:
        raise HTTPException(
            status_code=404,
            detail=f"TRaSH profile '{override.profile_name}' not found in cache",
        )

    # 4. Build client
    client = ArrBaseClient(
        url=service.url,
        api_key=decrypt_api_key(service.api_key),
    )
    client.API_PREFIX = "/api/v3"

    errors: list[str] = []
    cfs_created = 0
    cfs_updated = 0
    profile_id: int | None = None

    try:
        # ── Step A: Create/update Custom Formats ──────────────
        current_cfs = await client.get("/customformat")
        current_by_name: dict[str, dict] = {
            cf["name"].lower(): cf for cf in current_cfs
        }

        all_trash_cfs = cache.get_custom_formats(service_type)
        trash_by_id: dict[str, dict] = {
            cf["trash_id"]: cf for cf in all_trash_cfs
        }

        # Extract CF IDs from the QP
        format_items_raw = qp_data.get("formatItems", {})
        qp_cf_ids: set[str] = set()
        cf_scores: dict[str, int] = {}  # trash_id → score

        if isinstance(format_items_raw, dict):
            qp_cf_ids = set(format_items_raw.values())
        elif isinstance(format_items_raw, list):
            for fmt in format_items_raw:
                if isinstance(fmt, dict) and "trash_id" in fmt:
                    qp_cf_ids.add(fmt["trash_id"])
                    cf_scores[fmt["trash_id"]] = fmt.get("score", 0)

        logger.info(
            "Override %d: applying %d CFs from profile '%s'",
            override_id, len(qp_cf_ids), override.profile_name,
        )

        # Map trash_id → Sonarr CF ID after create/update
        trash_to_sonarr_id: dict[str, int] = {}

        from app.api.trash_guides import _build_cf_payload

        for cf_trash_id in qp_cf_ids:
            cf = trash_by_id.get(cf_trash_id)
            if not cf:
                continue

            payload = _build_cf_payload(cf)
            existing = current_by_name.get(cf["name"].lower())

            try:
                if existing:
                    payload["id"] = existing["id"]
                    await client.put(f"/customformat/{existing['id']}", payload)
                    trash_to_sonarr_id[cf_trash_id] = existing["id"]
                    cfs_updated += 1
                else:
                    new_cf = await client.post("/customformat", payload)
                    trash_to_sonarr_id[cf_trash_id] = new_cf["id"]
                    current_by_name[cf["name"].lower()] = new_cf
                    cfs_created += 1
            except Exception as e:
                errors.append(f"CF '{cf['name']}': {e}")

        # ── Step B: Create/update Quality Profile ─────────────
        qp_display_name = qp_data.get("name", override.profile_name)

        existing_profiles = await client.get("/qualityprofile")
        existing_qp = None
        for ep in existing_profiles:
            if ep["name"].lower() == qp_display_name.lower():
                existing_qp = ep
                break

        # Build formatItems for the QP
        sonarr_format_items = []
        for cf_trash_id, sonarr_id in trash_to_sonarr_id.items():
            score = cf_scores.get(cf_trash_id, 0)
            sonarr_format_items.append({
                "format": sonarr_id,
                "score": score,
            })

        if existing_qp:
            # Update: merge our CFs into the existing QP
            existing_formats = existing_qp.get("formatItems", [])
            existing_format_ids = {f["format"] for f in existing_formats}

            for item in sonarr_format_items:
                if item["format"] not in existing_format_ids:
                    existing_formats.append(item)
                else:
                    # Update score
                    for ef in existing_formats:
                        if ef["format"] == item["format"]:
                            ef["score"] = item["score"]
                            break

            existing_qp["formatItems"] = existing_formats
            try:
                await client.put(
                    f"/qualityprofile/{existing_qp['id']}", existing_qp
                )
                profile_id = existing_qp["id"]
            except Exception as e:
                errors.append(f"Update QP: {e}")
        else:
            # Create new QP — we need a base. Clone the first existing one.
            if existing_profiles:
                base_qp = existing_profiles[0].copy()
                base_qp.pop("id", None)
                base_qp["name"] = qp_display_name
                base_qp["formatItems"] = sonarr_format_items
                try:
                    new_qp = await client.post("/qualityprofile", base_qp)
                    profile_id = new_qp["id"]
                except Exception as e:
                    errors.append(f"Create QP: {e}")
            else:
                errors.append("No existing profiles to use as template")

        # ── Step C: Assign QP to the series/movie ─────────────
        media_updated = False
        if profile_id:
            try:
                if override.media_type == "series":
                    media_data = await client.get(
                        f"/series/{override.external_id}"
                    )
                    media_data["qualityProfileId"] = profile_id
                    await client.put(
                        f"/series/{override.external_id}", media_data
                    )
                    media_updated = True
                else:
                    media_data = await client.get(
                        f"/movie/{override.external_id}"
                    )
                    media_data["qualityProfileId"] = profile_id
                    await client.put(
                        f"/movie/{override.external_id}", media_data
                    )
                    media_updated = True
            except Exception as e:
                errors.append(f"Assign QP to media: {e}")

        # Notification
        try:
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
        except Exception:
            pass

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
        profile_name=qp_data.get("name", override.profile_name),
        profile_id=profile_id,
        media_updated=media_updated,
        errors=errors,
    )


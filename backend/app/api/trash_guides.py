"""API routes for TRaSH Guides integration.

Provides endpoints to sync TRaSH data, generate recommendations
based on user preferences, audit current Sonarr/Radarr config,
and apply recommended Custom Formats / Quality Profiles.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.schemas.trash_guides import (
    ApplyResult,
    AuditResult,
    MediaPreferences,
    RecommendedProfile,
    TrashCFSummary,
    TrashSyncStatus,
)
from app.services.trash_guides import get_trash_cache
from app.services.trash_profiles import generate_recommendations
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/trash-guides", tags=["TRaSH Guides"])


# ── Request models ────────────────────────────────────────────

class SyncRequest(BaseModel):
    force: bool = Field(default=False, description="Force re-fetch ignoring cache TTL")


class ApplyRequest(BaseModel):
    service_id: int = Field(description="ArrMada service ID to apply to")
    recommendations: list[str] = Field(
        description="List of profile IDs to apply"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, only simulate — don't actually modify"
    )


class AuditRequest(BaseModel):
    service_id: int = Field(description="ArrMada service ID to audit")


# ── Endpoints ─────────────────────────────────────────────────

@router.get(
    "/status",
    response_model=TrashSyncStatus,
    summary="Get TRaSH Guides cache status",
)
async def get_status(_auth: str = Depends(get_current_user)):
    """Return current cache status: last sync, counts, staleness."""
    cache = get_trash_cache()
    s = cache.status
    return TrashSyncStatus(**s)


@router.post(
    "/sync",
    summary="Sync TRaSH Guides data from GitHub",
)
async def sync_data(
    body: Optional[SyncRequest] = None,
    _auth: str = Depends(get_current_user),
):
    """Fetch or refresh all TRaSH Guides data from GitHub.

    By default respects the 24h cache TTL. Use force=true to re-fetch.
    """
    cache = get_trash_cache()
    force = body.force if body else False

    try:
        results = await cache.sync(force=force)
        return {
            "status": "ok",
            "fetched": results,
            **cache.status,
        }
    except Exception as e:
        logger.error("TRaSH sync failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to sync from GitHub: {e}",
        )


@router.get(
    "/custom-formats",
    response_model=list[TrashCFSummary],
    summary="List all available Custom Formats",
)
async def list_custom_formats(
    service: str = "sonarr",
    search: Optional[str] = None,
    category: Optional[str] = None,
    _auth: str = Depends(get_current_user),
):
    """List all TRaSH Custom Formats, optionally filtered.

    Categories: hdr, audio, language, anime, quality, unwanted, streaming, other
    """
    cache = get_trash_cache()

    if cache.is_stale:
        await cache.sync()

    if search:
        cfs = cache.search_cfs(search, service)
    else:
        cfs = cache.get_custom_formats(service)

    summaries = []
    for cf in cfs:
        cat = _categorize_cf_name(cf.get("_source_file", cf.get("name", "")))
        if category and cat != category:
            continue
        summaries.append(TrashCFSummary(
            trash_id=cf["trash_id"],
            name=cf["name"],
            scores=cf.get("trash_scores"),
            category=cat,
        ))

    return summaries


@router.post(
    "/recommend",
    response_model=list[RecommendedProfile],
    summary="Get profile recommendations based on preferences",
)
async def get_recommendations(
    prefs: MediaPreferences,
    _auth: str = Depends(get_current_user),
):
    """Generate TRaSH Guides recommendations based on user media preferences.

    Takes display type, audio, language, quality, and content type preferences
    and returns the ideal Custom Formats and Quality Profile configuration.
    """
    cache = get_trash_cache()

    if cache.is_stale:
        await cache.sync()

    try:
        recs = generate_recommendations(prefs, cache)
        if not recs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No matching profiles found for these preferences",
            )
        return recs
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Recommendation generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {e}",
        )


@router.post(
    "/audit",
    response_model=AuditResult,
    summary="Audit current config vs TRaSH recommendations",
)
async def audit_config(
    body: AuditRequest,
    _auth: str = Depends(get_current_user),
):
    """Compare current Sonarr/Radarr configuration against TRaSH recommendations.

    Returns compliance percentage, missing CFs, and outdated CFs.
    """
    from app.db.session import get_db_session
    from app.db.models import Service

    cache = get_trash_cache()
    if cache.is_stale:
        await cache.sync()

    # Get service from DB
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Service).where(Service.id == body.service_id)
        )
        service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {body.service_id} not found",
        )

    service_type = service.type.lower()  # sonarr or radarr
    if service_type not in ("sonarr", "radarr"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audit is only available for Sonarr and Radarr services",
        )

    # Get current CFs from the service
    from app.services.arr_client import ArrBaseClient
    from app.services.encryption import decrypt

    client = ArrBaseClient(
        url=service.url,
        api_key=decrypt(service.api_key),
    )
    client.API_PREFIX = "/api/v3"

    try:
        current_cfs = await client.get("/customformat")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot reach {service.name}: {e}",
        )
    finally:
        await client.close()

    # Get all recommended CFs
    all_trash_cfs = cache.get_custom_formats(service_type)
    trash_cf_names = {cf["name"].lower(): cf for cf in all_trash_cfs}
    current_cf_names = {cf["name"].lower() for cf in current_cfs}

    # Find missing CFs
    missing = []
    for cf in all_trash_cfs[:50]:  # Limit to top 50 most important
        if cf["name"].lower() not in current_cf_names:
            missing.append(TrashCFSummary(
                trash_id=cf["trash_id"],
                name=cf["name"],
                scores=cf.get("trash_scores"),
                category=_categorize_cf_name(cf.get("_source_file", "")),
            ))

    # Calculate compliance
    total_recommended = len(all_trash_cfs[:50])
    found = total_recommended - len(missing)
    compliance = (found / total_recommended * 100) if total_recommended > 0 else 100.0

    return AuditResult(
        service_name=service.name,
        service_type=service_type,
        compliance_pct=round(compliance, 1),
        missing_cfs=missing[:20],  # Top 20 missing
        extra_cfs=[
            name for name in current_cf_names
            if name not in trash_cf_names
        ][:10],
    )


@router.post(
    "/apply",
    response_model=ApplyResult,
    summary="Apply TRaSH recommendations to Sonarr/Radarr",
)
async def apply_recommendations(
    body: ApplyRequest,
    _auth: str = Depends(get_current_user),
):
    """Push recommended Custom Formats and Quality Profiles to a service.

    Use dry_run=true to preview changes without modifying anything.
    """
    from app.db.session import get_db_session
    from app.db.models import Service

    cache = get_trash_cache()
    if cache.is_stale:
        await cache.sync()

    # Get service from DB
    async with get_db_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(Service).where(Service.id == body.service_id)
        )
        service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {body.service_id} not found",
        )

    service_type = service.type.lower()
    if service_type not in ("sonarr", "radarr"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apply is only available for Sonarr and Radarr services",
        )

    from app.services.arr_client import ArrBaseClient
    from app.services.encryption import decrypt

    client = ArrBaseClient(
        url=service.url,
        api_key=decrypt(service.api_key),
    )
    client.API_PREFIX = "/api/v3"

    errors: list[str] = []
    cfs_created = 0
    cfs_updated = 0

    try:
        # Get current CFs to avoid duplicates
        current_cfs = await client.get("/customformat")
        current_by_name: dict[str, dict] = {
            cf["name"].lower(): cf for cf in current_cfs
        }

        # Get recommended CFs from cache
        all_trash_cfs = cache.get_custom_formats(service_type)

        for rec_id in body.recommendations:
            # Find the quality profile recommendation
            qp = None
            for qp_data in cache.get_quality_profiles(service_type):
                if qp_data.get("name", "").replace(" ", "-").lower() == rec_id.lower():
                    qp = qp_data
                    break

            if not qp:
                continue

            # Get CFs referenced in the QP
            qp_cf_ids = set()
            for fmt_item in (qp.get("formatItems") or []):
                if "trash_id" in fmt_item:
                    qp_cf_ids.add(fmt_item["trash_id"])

            # Create/update each referenced CF
            for cf in all_trash_cfs:
                if cf["trash_id"] not in qp_cf_ids:
                    continue

                # Build Sonarr-compatible CF payload
                payload = _build_cf_payload(cf)

                existing = current_by_name.get(cf["name"].lower())

                if body.dry_run:
                    if existing:
                        cfs_updated += 1
                    else:
                        cfs_created += 1
                    continue

                try:
                    if existing:
                        payload["id"] = existing["id"]
                        await client.put(f"/customformat/{existing['id']}", payload)
                        cfs_updated += 1
                    else:
                        result = await client.post("/customformat", payload)
                        cfs_created += 1
                        # Update our local map
                        current_by_name[cf["name"].lower()] = result
                except Exception as e:
                    errors.append(f"CF '{cf['name']}': {e}")

    except Exception as e:
        errors.append(f"Connection error: {e}")
    finally:
        await client.close()

    return ApplyResult(
        success=len(errors) == 0,
        cfs_created=cfs_created,
        cfs_updated=cfs_updated,
        errors=errors,
    )


# ── Helpers ───────────────────────────────────────────────────

def _categorize_cf_name(name: str) -> str:
    """Categorize a CF by its filename/name."""
    n = name.lower().replace(".json", "")
    if "anime" in n:
        return "anime"
    if any(kw in n for kw in ("french", "vostfr", "multi", "vff", "vfq", "vof")):
        return "language"
    if any(kw in n for kw in ("hdr", "dv", "dolby")):
        return "hdr"
    if any(kw in n for kw in ("atmos", "truehd", "dts", "dd", "surround", "sound")):
        return "audio"
    if any(kw in n for kw in ("tier", "remux", "bluray")):
        return "quality"
    if any(kw in n for kw in ("lq", "br-disk", "obfuscated", "retag")):
        return "unwanted"
    return "other"


def _build_cf_payload(trash_cf: dict[str, Any]) -> dict[str, Any]:
    """Convert a TRaSH CF JSON into a Sonarr/Radarr API payload."""
    specs = []
    for spec in trash_cf.get("specifications", []):
        sonarr_spec: dict[str, Any] = {
            "name": spec["name"],
            "implementation": spec["implementation"],
            "negate": spec.get("negate", False),
            "required": spec.get("required", False),
            "fields": [],
        }

        # Convert fields
        fields = spec.get("fields", {})
        if isinstance(fields, dict):
            for field_name, field_value in fields.items():
                sonarr_spec["fields"].append({
                    "name": field_name,
                    "value": field_value,
                })
        specs.append(sonarr_spec)

    return {
        "name": trash_cf["name"],
        "includeCustomFormatWhenRenaming": trash_cf.get(
            "includeCustomFormatWhenRenaming", False
        ),
        "specifications": specs,
    }

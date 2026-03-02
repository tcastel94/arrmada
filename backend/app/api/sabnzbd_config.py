"""SABnzbd TRaSH Guides configuration audit and apply.

Audits SABnzbd settings against TRaSH Guides recommendations and
can apply the optimal configuration.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/sabnzbd-config",
    tags=["sabnzbd-config"],
    dependencies=[Depends(get_current_user)],
)


# ── TRaSH Recommended Settings ──────────────────────────────

TRASH_RECOMMENDED = {
    "categories": [
        {
            "name": "sonarr",
            "dir": "sonarr",
            "newzbin": "",
            "priority": -100,
            "pp": "",
            "script": "Default",
            "order": 0,
        },
        {
            "name": "radarr",
            "dir": "radarr",
            "newzbin": "",
            "priority": -100,
            "pp": "",
            "script": "Default",
            "order": 0,
        },
        {
            "name": "lidarr",
            "dir": "lidarr",
            "newzbin": "",
            "priority": -100,
            "pp": "",
            "script": "Default",
            "order": 0,
        },
    ],
    "switches": {
        "direct_unpack": True,
        "pause_on_post_processing": False,
        "flat_unpack": True,          # unpack in same folder for Sonarr/Radarr
        "safe_postproc": True,        # only unpack verified jobs
        "enable_recursive": True,     # unpack archives within archives
        "enable_unrar": True,
        "enable_unzip": True,
        "enable_7zip": True,
        "enable_filejoin": True,
        "enable_par_cleanup": True,
        "deobfuscate_final_filenames": True,
        "ignore_samples": 0,          # let Sonarr/Radarr handle samples
    },
    "sorting": {
        # TRaSH says: MAKE SURE THAT SORTING IS ENTIRELY DISABLED
        "enable_tv_sorting": False,
        "enable_movie_sorting": False,
        "enable_date_sorting": False,
    },
}


# ── Schemas ──────────────────────────────────────────────────

class ConfigCheck(BaseModel):
    """One setting check result."""
    key: str
    label: str
    current_value: Any
    recommended_value: Any
    is_compliant: bool
    category: str  # "categories", "switches", "sorting", "general"


class AuditResult(BaseModel):
    """Full audit result."""
    service_name: str
    total_checks: int
    passed: int
    failed: int
    compliance_pct: float
    checks: list[ConfigCheck]


class ApplyResult(BaseModel):
    """Result of applying TRaSH config."""
    success: bool
    categories_created: int = 0
    settings_updated: int = 0
    errors: list[str] = []


# ── Helpers ──────────────────────────────────────────────────

async def _get_sabnzbd_client(db):
    """Get the first enabled SABnzbd service and build a client."""
    from sqlalchemy import select
    from app.models.service import Service
    from app.services.sabnzbd import SabnzbdClient
    from app.services.encryption import decrypt_api_key

    stmt = (
        select(Service)
        .where(
            Service.type.in_(["sabnzbd", "SABnzbd"]),
            Service.is_enabled == True,  # noqa: E712
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SABnzbd service configured",
        )

    client = SabnzbdClient(
        url=service.url,
        api_key=decrypt_api_key(service.api_key),
    )
    return client, service


# ── Endpoints ────────────────────────────────────────────────

@router.get(
    "/audit",
    response_model=AuditResult,
    summary="Audit SABnzbd config against TRaSH recommendations",
)
async def audit_sabnzbd(db=Depends(get_db)):
    """Compare current SABnzbd configuration against TRaSH Guides best practices."""
    client, service = await _get_sabnzbd_client(db)
    checks: list[ConfigCheck] = []

    try:
        # Get current config
        config_data = await client._call("get_config")
        config = config_data.get("config", config_data)
        misc = config.get("misc", {})
        categories = config.get("categories", [])

        # ── Check Categories ──────────────────────────────
        existing_cats = {c["name"].lower(): c for c in categories if "name" in c}

        for rec_cat in TRASH_RECOMMENDED["categories"]:
            cat_name = rec_cat["name"]
            existing = existing_cats.get(cat_name.lower())
            is_ok = existing is not None
            checks.append(ConfigCheck(
                key=f"category_{cat_name}",
                label=f"Catégorie '{cat_name}'",
                current_value="Existe" if is_ok else "Manquante",
                recommended_value="Doit exister",
                is_compliant=is_ok,
                category="categories",
            ))

            if existing:
                # Check if dir is set
                cat_dir = existing.get("dir", "")
                dir_ok = cat_dir.lower() == cat_name.lower() or cat_name.lower() in cat_dir.lower()
                checks.append(ConfigCheck(
                    key=f"category_{cat_name}_dir",
                    label=f"Catégorie '{cat_name}' → dossier",
                    current_value=cat_dir or "(vide)",
                    recommended_value=cat_name,
                    is_compliant=dir_ok,
                    category="categories",
                ))

        # ── Check Switches ─────────────────────────────────
        switch_labels = {
            "direct_unpack": "Direct Unpack",
            "pause_on_post_processing": "Pause pendant Post-Processing",
            "flat_unpack": "Unpack à plat",
            "safe_postproc": "Post-process uniquement les jobs vérifiés",
            "enable_recursive": "Unpack récursif (archives dans archives)",
            "enable_unrar": "Support RAR",
            "enable_unzip": "Support ZIP",
            "enable_7zip": "Support 7-Zip",
            "enable_filejoin": "File join",
            "enable_par_cleanup": "Nettoyage PAR",
            "deobfuscate_final_filenames": "Dé-obfuscation des noms",
            "ignore_samples": "Ignorer les samples (0 = désactivé)",
        }

        for key, recommended in TRASH_RECOMMENDED["switches"].items():
            current = misc.get(key)
            # Normalize booleans
            if isinstance(recommended, bool):
                if isinstance(current, int):
                    current_bool = bool(current)
                elif isinstance(current, str):
                    current_bool = current.lower() in ("1", "true", "yes")
                else:
                    current_bool = bool(current) if current is not None else None
                is_ok = current_bool == recommended
                display_current = current_bool
            else:
                is_ok = current == recommended
                display_current = current

            checks.append(ConfigCheck(
                key=f"switch_{key}",
                label=switch_labels.get(key, key),
                current_value=display_current if display_current is not None else "Non défini",
                recommended_value=recommended,
                is_compliant=is_ok,
                category="switches",
            ))

        # ── Check Sorting ──────────────────────────────────
        sorting_labels = {
            "enable_tv_sorting": "Tri TV",
            "enable_movie_sorting": "Tri Films",
            "enable_date_sorting": "Tri par date",
        }

        for key, recommended in TRASH_RECOMMENDED["sorting"].items():
            current = misc.get(key)
            if isinstance(current, int):
                current = bool(current)
            elif isinstance(current, str):
                current = current.lower() in ("1", "true", "yes")
            else:
                current = bool(current) if current is not None else None

            checks.append(ConfigCheck(
                key=f"sorting_{key}",
                label=sorting_labels.get(key, key),
                current_value=current if current is not None else "Non défini",
                recommended_value=recommended,
                is_compliant=current == recommended,
                category="sorting",
            ))

        # ── Check Completed Download Folder ────────────────
        complete_dir = misc.get("complete_dir", "")
        has_complete = bool(complete_dir)
        checks.append(ConfigCheck(
            key="complete_dir",
            label="Dossier de téléchargement terminé",
            current_value=complete_dir or "(non défini)",
            recommended_value="Doit être configuré",
            is_compliant=has_complete,
            category="general",
        ))

    except Exception as e:
        logger.error("SABnzbd audit failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audit failed: {e}",
        )
    finally:
        await client.close()

    passed = sum(1 for c in checks if c.is_compliant)
    total = len(checks)

    return AuditResult(
        service_name=service.name,
        total_checks=total,
        passed=passed,
        failed=total - passed,
        compliance_pct=round(passed / total * 100, 1) if total > 0 else 0,
        checks=checks,
    )


@router.post(
    "/apply",
    response_model=ApplyResult,
    summary="Apply TRaSH recommended settings to SABnzbd",
)
async def apply_trash_config(db=Depends(get_db)):
    """Push TRaSH Guides recommended configuration to SABnzbd."""
    client, service = await _get_sabnzbd_client(db)
    errors: list[str] = []
    cats_created = 0
    settings_updated = 0

    try:
        # Get current config
        config_data = await client._call("get_config")
        config = config_data.get("config", config_data)
        categories = config.get("categories", [])
        existing_cats = {c["name"].lower() for c in categories if "name" in c}

        # ── Create missing categories ─────────────────────
        for rec_cat in TRASH_RECOMMENDED["categories"]:
            if rec_cat["name"].lower() not in existing_cats:
                try:
                    await client._call("set_config", {
                        "section": "categories",
                        "keyword": rec_cat["name"],
                        "name": rec_cat["name"],
                        "dir": rec_cat["dir"],
                        "priority": rec_cat["priority"],
                    })
                    cats_created += 1
                    logger.info("Created SABnzbd category: %s", rec_cat["name"])
                except Exception as e:
                    errors.append(f"Category '{rec_cat['name']}': {e}")

        # ── Apply switch settings ─────────────────────────
        for key, value in TRASH_RECOMMENDED["switches"].items():
            try:
                # SABnzbd API: set_config section=misc keyword=key value=val
                sab_value = 1 if value is True else (0 if value is False else value)
                await client._call("set_config_default", {
                    "section": "misc",
                    "keyword": key,
                    "value": sab_value,
                })
                settings_updated += 1
            except Exception as e:
                errors.append(f"Switch '{key}': {e}")

        # ── Disable sorting ───────────────────────────────
        for key, value in TRASH_RECOMMENDED["sorting"].items():
            try:
                sab_value = 1 if value is True else 0
                await client._call("set_config_default", {
                    "section": "misc",
                    "keyword": key,
                    "value": sab_value,
                })
                settings_updated += 1
            except Exception as e:
                errors.append(f"Sorting '{key}': {e}")

        # Create notification
        try:
            from app.services.notification_service import create_notification
            await create_notification(
                db,
                type="sabnzbd_config",
                title="SABnzbd TRaSH Config appliqué",
                message=(
                    f"{cats_created} catégories créées, "
                    f"{settings_updated} réglages mis à jour"
                ),
                severity="success" if not errors else "warning",
                service_name=service.name,
            )
        except Exception:
            pass

    except Exception as e:
        errors.append(f"Connection error: {e}")
        logger.error("SABnzbd apply failed: %s", e, exc_info=True)
    finally:
        await client.close()

    await db.commit()

    return ApplyResult(
        success=len(errors) == 0,
        categories_created=cats_created,
        settings_updated=settings_updated,
        errors=errors,
    )

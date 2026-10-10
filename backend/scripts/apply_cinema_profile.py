# -*- coding: utf-8 -*-
"""ArrMada — Deploy 100% Quality Profile & Custom Formats to Radarr and Sonarr.

Applies TRaSH Guides best practices tailored for Cinema Room (Atmos/DTS-HD)
and Living Room Shield (DV/HDR10 hybrid, VO/MULTI audio priority).
"""

from __future__ import annotations

import asyncio
import json
import logging
import httpx
from sqlalchemy import select

from app.database import async_session_factory
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.trash_guides import get_trash_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("apply_cinema_profile")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION DU PROFIL ET SCORES DES CUSTOM FORMATS
# ─────────────────────────────────────────────────────────────────────────────

PROFILE_NAME = "👑 Ultra-HD Cinema & Auto-Upgrade"

CF_SCORE_TARGETS = {
    # ── Vidéo & HDR (Hybride DV + HDR10) ───────────────────────
    "DV HDR10": 2000,
    "DV (WEBDL)": 1700,
    "Dolby Vision": 1700,
    "HDR10Plus Boost": 1400,
    "HDR10+ Boost": 1400,
    "HDR10+": 1400,
    "HDR": 1200,
    "HDR10": 1200,
    "SDR": -1000,
    "DV (Disk)": -500,
    "DV without HDR fallback": -10000,
    "DV (WEBDL) without HDR fallback": -10000,

    # ── Audio Immersif & Multicanal ────────────────────────────
    "TrueHD Atmos": 1500,
    "TrueHD with Atmos": 1500,
    "DTS-X": 1500,
    "DTS:X": 1500,
    "DTS-HD MA": 1200,
    "TrueHD": 1200,
    "DD+ Atmos": 800,
    "E-AC-3 Atmos": 800,
    "DD+": 300,
    "DTS": 300,
    "5.1 Surround": 300,
    "7.1 Surround": 500,
    "AAC Stereo": -1000,
    "2.0 Stereo": -1000,

    # ── Langues (VO > MULTI > VFF) ────────────────────────────
    "Original Audio": 1000,
    "English Audio": 1000,
    "MULTI": 800,
    "French (VFF)": 500,
    "French (VF2)": 400,
    "French (VFI)": 300,
    "French (VOSTFR)": 900,
    "French (VFQ)": -10000,
    "Line Audio": -10000,
    "Bad Dual Audio": -10000,
    "LQ Release Groups": -10000,
    "Extras": -10000,
}


async def get_service_client(service_type: str) -> tuple[httpx.AsyncClient | None, str]:
    """Get authenticated httpx client for Radarr or Sonarr."""
    async with async_session_factory() as session:
        stmt = select(Service).where(Service.type == service_type, Service.is_enabled == True)
        res = await session.execute(stmt)
        svc = res.scalars().first()
        if not svc:
            return None, f"Service {service_type} non configure"

        api_key = decrypt_api_key(svc.api_key)
        client = httpx.AsyncClient(
            base_url=svc.url,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )
        return client, svc.name


async def sync_custom_formats(client: httpx.AsyncClient, service_type: str, cache) -> dict[str, int]:
    """Ensure all required TRaSH Custom Formats are imported and return {name: id}."""
    logger.info("Synchronisation des Custom Formats pour %s...", service_type)
    
    # 1. Fetch current CFs from Radarr/Sonarr
    existing_cfs = (await client.get(f"/api/v3/customformat")).json()
    existing_map = {cf["name"].lower(): cf["id"] for cf in existing_cfs}

    # 2. Fetch TRaSH CFs from cache
    trash_cfs = cache.get_custom_formats(service_type)
    name_to_id: dict[str, int] = {}

    for trash_cf in trash_cfs:
        name = trash_cf.get("name", "")
        norm_name = name.lower()

        # Check if this CF matches one of our score targets
        matched_target = None
        for target_name in CF_SCORE_TARGETS:
            if target_name.lower() in norm_name or norm_name in target_name.lower():
                matched_target = target_name
                break

        if not matched_target and norm_name not in existing_map:
            continue

        payload = {
            "name": name,
            "includeCustomFormatWhenRenaming": False,
            "specifications": trash_cf.get("specifications", []),
        }

        if norm_name in existing_map:
            cf_id = existing_map[norm_name]
            name_to_id[name] = cf_id
        else:
            # Create in Radarr/Sonarr
            try:
                res = await client.post("/api/v3/customformat", json=payload)
                if res.status_code in (200, 201):
                    created = res.json()
                    cf_id = created["id"]
                    name_to_id[name] = cf_id
                    logger.info("  + Cree CF: %s (ID: %d)", name, cf_id)
                else:
                    logger.warning("  ! Echec creation CF %s: %s", name, res.text)
            except Exception as exc:
                logger.warning("  ! Erreur creation CF %s: %s", name, exc)

    logger.info("Total Custom Formats actifs dans %s : %d", service_type, len(name_to_id))
    return name_to_id


async def configure_quality_profile(client: httpx.AsyncClient, service_type: str, cf_map: dict[str, int]) -> int:
    """Create or update the '👑 Ultra-HD Cinema & Auto-Upgrade' profile."""
    logger.info("Configuration du Profil de Qualite '%s' dans %s...", PROFILE_NAME, service_type)

    # 1. Fetch available quality schema / profiles
    schema_res = await client.get("/api/v3/qualityprofile/schema")
    schema = schema_res.json() if schema_res.status_code == 200 else {}
    items = schema.get("items", [])

    profiles = (await client.get("/api/v3/qualityprofile")).json()
    existing_profile = next((p for p in profiles if p.get("name") == PROFILE_NAME), None)

    if existing_profile:
        items = existing_profile.get("items", items)

    # Enable 2160p and 1080p qualities in top-down order
    allowed_qualities = [
        "Remux-2160p", "Bluray-2160p", "WEBDL-2160p", "WEBRip-2160p", "HDTV-2160p",
        "Remux-1080p", "Bluray-1080p", "WEBDL-1080p", "WEBRip-1080p", "HDTV-1080p"
    ]

    cutoff_id = 1
    for it in items:
        q_name = it.get("quality", {}).get("name", "")
        # Enable if in allowed list
        should_enable = any(aq.lower() in q_name.lower() or q_name.lower() in aq.lower() for aq in allowed_qualities)
        it["allowed"] = should_enable
        if "Remux-2160p" in q_name or "2160p Remux" in q_name:
            cutoff_id = it.get("quality", {}).get("id", cutoff_id)

    # Build formatItems with our scoring
    format_items = []
    for cf_name, cf_id in cf_map.items():
        score = 0
        for target, target_score in CF_SCORE_TARGETS.items():
            if target.lower() in cf_name.lower() or cf_name.lower() in target.lower():
                score = target_score
                break
        format_items.append({
            "format": cf_id,
            "name": cf_name,
            "score": score,
        })

    profile_payload = {
        "name": PROFILE_NAME,
        "upgradeAllowed": True,
        "cutoff": cutoff_id,
        "cutoffFormatScore": 10000,
        "minFormatScore": 0,
        "items": items,
        "formatItems": format_items,
    }

    if existing_profile:
        pid = existing_profile["id"]
        profile_payload["id"] = pid
        res = await client.put(f"/api/v3/qualityprofile/{pid}", json=profile_payload)
        logger.info("  ✓ Profil '%s' mis a jour (ID: %d)", PROFILE_NAME, pid)
    else:
        res = await client.post("/api/v3/qualityprofile", json=profile_payload)
        created = res.json()
        pid = created.get("id", 1)
        logger.info("  ✓ Profil '%s' cree avec succes (ID: %d)", PROFILE_NAME, pid)

    return pid


async def apply_profile_to_all_media(client: httpx.AsyncClient, service_type: str, profile_id: int):
    """Assign the new profile to all existing movies / series in library."""
    logger.info("Application du profil '%s' aux medias existants dans %s...", PROFILE_NAME, service_type)
    
    endpoint = "/api/v3/movie" if service_type == "radarr" else "/api/v3/series"
    media_list = (await client.get(endpoint)).json()
    
    updated_count = 0
    for m in media_list:
        if m.get("qualityProfileId") != profile_id:
            m["qualityProfileId"] = profile_id
            m["monitored"] = True
            try:
                if service_type == "radarr":
                    await client.put(f"/api/v3/movie/{m['id']}", json=m)
                else:
                    await client.put(f"/api/v3/series/{m['id']}", json=m)
                updated_count += 1
            except Exception as e:
                logger.warning("  ! Erreur update media %s: %s", m.get("title"), e)

    logger.info("✓ %d %s mis a jour sur le nouveau profil dans %s.", updated_count, "films" if service_type == "radarr" else "series", service_type)


async def main():
    logger.info("======================================================================")
    logger.info("  DEPLOIEMENT PROFIL CINEMA 4K DV/HDR10 & ATMOS DANS RADARR / SONARR")
    logger.info("======================================================================")

    cache = get_trash_cache()
    if cache.is_stale:
        logger.info("Rafraichissement du cache TRaSH Guides...")
        await cache.sync(force=True)

    for stype in ("radarr", "sonarr"):
        client, name = await get_service_client(stype)
        if not client:
            logger.warning("Service %s non accessible : %s", stype, name)
            continue

        try:
            cf_map = await sync_custom_formats(client, stype, cache)
            profile_id = await configure_quality_profile(client, stype, cf_map)
            await apply_profile_to_all_media(client, stype, profile_id)
        finally:
            await client.aclose()

    logger.info("======================================================================")
    logger.info("  DEPLOIEMENT TERMINE AVEC SUCCES !")
    logger.info("======================================================================")


if __name__ == "__main__":
    asyncio.run(main())

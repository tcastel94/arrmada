# -*- coding: utf-8 -*-
"""ArrMada — Configurator for 100% Highest Quality Cinema Profile (Radarr & Sonarr)."""

from __future__ import annotations

import asyncio
import copy
import logging
import httpx
from sqlalchemy import select

from app.database import async_session_factory
from app.models.service import Service
from app.services.encryption import decrypt_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("configure_cinema_profile")

PROFILE_NAME = "👑 Ultra-HD Cinema & Auto-Upgrade"

CF_RULES = {
    # ── Vidéo ──────────────────────────────────────────────────
    "dv + hdr10": 2000,
    "dolby vision & hdr10": 2000,
    "dv-boost": 1700,
    "dv boost": 1700,
    "dolby vision": 1700,
    "hdr10+ boost": 1400,
    "hdr10plus-boost": 1400,
    "hdr10+": 1400,
    "hdr10": 1200,
    "hdr": 1200,
    "exclude sdr": 500,
    "sdr": -1000,
    "dv without hdr fallback": -10000,

    # ── Audio ──────────────────────────────────────────────────
    "dolby atmos (truehd/eac3)": 1500,
    "truehd-atmos": 1500,
    "truehd atmos": 1500,
    "truehd with atmos": 1500,
    "dts-x": 1500,
    "dts:x": 1500,
    "dts-hd ma": 1200,
    "dts-hd-ma": 1200,
    "dolby truehd": 1200,
    "truehd": 1200,
    "ddplus-atmos": 800,
    "dolby digital plus (eac3)": 800,
    "ddplus": 500,
    "dolby digital (ac3)": 300,
    "dd": 300,
    "dts": 300,
    "audio: 5.1+": 300,
    "51-surround": 300,
    "71-surround": 500,
    "exclude aac/mp3/2.0": 500,
    "2.0 stereo": -1000,
    "aac stereo": -1000,

    # ── Langues ────────────────────────────────────────────────
    "original audio": 1000,
    "english audio": 1000,
    "lang: vostfr": 900,
    "french-vostfr": 900,
    "multi": 800,
    "lang: multi": 800,
    "vff, multi & audio 5.1+": 800,
    "vff": 500,
    "lang: vff": 500,
    "french-vff": 500,
    "french-vf2": 400,
    "vf2": 400,
    "french-vfi": 300,
    "vfi": 300,
    "vfq": -10000,
    "french-vfq": -10000,
    "vq": -10000,

    # ── Unwanted / Rejections ──────────────────────────────────
    "br-disk": -10000,
    "extras": -10000,
    "lq": -10000,
    "lq (release title)": -10000,
    "fr lq": -10000,
    "upscaled": -10000,
    "line audio": -10000,
    "bad dual audio": -10000,
}


async def setup_service_profile(service_type: str):
    logger.info("======================================================================")
    logger.info("  Configuration de %s pour le profil Ultra-HD Cinema...", service_type.upper())
    logger.info("======================================================================")

    async with async_session_factory() as session:
        stmt = select(Service).where(Service.type == service_type, Service.is_enabled == True)
        res = await session.execute(stmt)
        svc = res.scalars().first()
        if not svc:
            logger.error("Service %s non trouvé", service_type)
            return

        api_key = decrypt_api_key(svc.api_key)
        client = httpx.AsyncClient(base_url=svc.url, headers={"X-Api-Key": api_key}, timeout=30.0)

    try:
        # 1. Fetch existing profiles and CFs
        qps = (await client.get("/api/v3/qualityprofile")).json()
        cfs = (await client.get("/api/v3/customformat")).json()
        logger.info("Trouvé %d profils et %d Custom Formats dans %s", len(qps), len(cfs), service_type)

        # Build formatItems
        cf_id_to_score: dict[int, int] = {}
        for cf in cfs:
            cid = cf["id"]
            cname = cf["name"].lower().strip()
            score = 0
            for rule_key, rule_score in CF_RULES.items():
                if rule_key in cname or cname in rule_key:
                    score = rule_score
                    break
            cf_id_to_score[cid] = score

        # 2. Pick a template profile (e.g. Ultra-HD or HD-1080p)
        template = next((p for p in qps if "ultra" in p["name"].lower() or "hd" in p["name"].lower()), qps[0])
        profile_data = copy.deepcopy(template)

        # Check if our named profile already exists
        existing = next((p for p in qps if p["name"] == PROFILE_NAME), None)
        if existing:
            profile_data = copy.deepcopy(existing)

        profile_data["name"] = PROFILE_NAME
        profile_data["upgradeAllowed"] = True
        profile_data["cutoffFormatScore"] = 10000
        profile_data["minFormatScore"] = 0
        profile_data["minUpgradeFormatScore"] = 1

        # Enable both 2160p and 1080p qualities
        items = profile_data.get("items", [])
        cutoff_id = 31  # Default Remux-2160p if found

        for item in items:
            q = item.get("quality", {})
            qname = q.get("name", "") or item.get("name", "")
            # Enable 2160p and 1080p Web/Bluray/Remux
            if any(k in qname for k in ["2160p", "1080p", "WEB", "Bluray", "Remux"]):
                item["allowed"] = True
                if "item" in item and isinstance(item["item"], list):
                    for sub in item["item"]:
                        sub["allowed"] = True
                if "items" in item and isinstance(item["items"], list):
                    for sub in item["items"]:
                        sub["allowed"] = True

            if "Remux-2160p" in qname or "2160p Remux" in qname:
                cutoff_id = q.get("id") or item.get("id") or cutoff_id

        profile_data["cutoff"] = cutoff_id

        # Update formatItems scores
        format_items = []
        for cf in cfs:
            cid = cf["id"]
            format_items.append({
                "format": cid,
                "name": cf["name"],
                "score": cf_id_to_score.get(cid, 0),
            })
        profile_data["formatItems"] = format_items

        # Save or update quality profile
        if existing:
            pid = existing["id"]
            profile_data["id"] = pid
            put_res = await client.put(f"/api/v3/qualityprofile/{pid}", json=profile_data)
            logger.info("✓ Profil mis à jour (ID: %d): status %d", pid, put_res.status_code)
        else:
            profile_data.pop("id", None)
            post_res = await client.post("/api/v3/qualityprofile", json=profile_data)
            if post_res.status_code in (200, 201):
                created = post_res.json()
                pid = created["id"]
                logger.info("✓ Profil créé avec succès (ID: %d)", pid)
            else:
                logger.error("Erreur création profil: %s", post_res.text)
                return

        # 3. Apply profile to all media
        endpoint = "/api/v3/movie" if service_type == "radarr" else "/api/v3/series"
        media_list = (await client.get(endpoint)).json()
        logger.info("Mise à jour des %d médias vers le profil '%s'...", len(media_list), PROFILE_NAME)

        updated = 0
        for m in media_list:
            if m.get("qualityProfileId") != pid:
                m["qualityProfileId"] = pid
                m["monitored"] = True
                try:
                    if service_type == "radarr":
                        await client.put(f"/api/v3/movie/{m['id']}", json=m)
                    else:
                        await client.put(f"/api/v3/series/{m['id']}", json=m)
                    updated += 1
                except Exception as e:
                    logger.warning("  ! Erreur update %s: %s", m.get("title"), e)

        logger.info("✓ %d médias mis à jour sur le nouveau profil dans %s.", updated, service_type)

    finally:
        await client.aclose()


async def main():
    await setup_service_profile("radarr")
    await setup_service_profile("sonarr")
    logger.info("======================================================================")
    logger.info("  TOUS LES PROFILS ONT ETE CONFIGURÉS ET APPLIQUÉS AVEC SUCCÈS !")
    logger.info("======================================================================")


if __name__ == "__main__":
    asyncio.run(main())

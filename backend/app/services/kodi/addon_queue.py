"""Add-on Kodi : recommandations, file de téléchargement (pause, reprise, retrait), orphelins, ajouts récents."""

import contextlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


async def get_recommendations_for_addon(db: AsyncSession) -> dict[str, Any]:
    """Fetch trending movies, trending series and smart recommendations for Kodi."""
    from app.api.recommendations import get_recommendations

    try:
        res = await get_recommendations(db)
        return {"status": "ok", "data": res}
    except Exception as exc:
        logger.error(f"Failed to get recommendations for Kodi: {exc}", exc_info=True)
        return {"status": "error", "message": str(exc), "data": {}}


async def remove_queue_item_for_addon(
    db: AsyncSession,
    service_type: str,
    item_id: int,
    remove_from_client: bool = True,
    blocklist: bool = False,
) -> dict[str, Any]:
    """Remove a download queue item via Radarr or Sonarr."""
    from app.api.downloads import _get_arr_client_for_service

    try:
        client = await _get_arr_client_for_service(db, service_type)
        await client.remove_queue_item(
            item_id, remove_from_client=remove_from_client, blocklist=blocklist
        )
        await client.close()
        return {
            "status": "ok",
            "message": f"Téléchargement #{item_id} supprimé (blocklist={blocklist})",
        }
    except Exception as exc:
        logger.error("Failed to remove queue item from Kodi: %s", exc)
        return {"status": "error", "message": str(exc)}


async def resume_queue_item_for_addon(
    db: AsyncSession, service_type: str, item_id: int
) -> dict[str, Any]:
    """Resume / unpause a download."""
    from sqlalchemy import select

    from app.models.service import Service
    from app.services.encryption import decrypt_api_key
    from app.services.sabnzbd import SabnzbdClient

    # 1. Unpause SABnzbd if present
    try:
        stmt = select(Service).where(Service.is_enabled == True, Service.type == "sabnzbd")
        res = await db.execute(stmt)
        sab = res.scalars().first()
        if sab:
            sab_client = SabnzbdClient(url=sab.url, api_key=decrypt_api_key(sab.api_key))
            await sab_client.resume()
            await sab_client.close()
    except Exception as exc:
        logger.warning("Resume SABnzbd failed: %s", exc)

    # 2. Trigger Sonarr / Radarr refresh
    from app.api.downloads import _get_arr_client_for_service

    try:
        client = await _get_arr_client_for_service(db, service_type)
        with contextlib.suppress(Exception):
            await client._post("command", json={"name": "RefreshMonitoredDownloads"})
        await client.close()
        return {"status": "ok", "message": f"Reprise envoyée pour le téléchargement #{item_id}"}
    except Exception as exc:
        logger.error("Failed to resume item from Kodi: %s", exc)
        return {"status": "error", "message": str(exc)}


async def pause_queue_item_for_addon(
    db: AsyncSession, service_type: str, item_id: int
) -> dict[str, Any]:
    """Pause a download."""
    from sqlalchemy import select

    from app.models.service import Service
    from app.services.encryption import decrypt_api_key
    from app.services.sabnzbd import SabnzbdClient

    try:
        stmt = select(Service).where(Service.is_enabled == True, Service.type == "sabnzbd")
        res = await db.execute(stmt)
        sab = res.scalars().first()
        if sab:
            sab_client = SabnzbdClient(url=sab.url, api_key=decrypt_api_key(sab.api_key))
            await sab_client.pause()
            await sab_client.close()
        return {"status": "ok", "message": f"Téléchargement #{item_id} mis en pause"}
    except Exception as exc:
        logger.error("Failed to pause item from Kodi: %s", exc)
        return {"status": "error", "message": str(exc)}


async def clean_orphans_for_addon(db: AsyncSession) -> dict[str, Any]:
    """Clean empty folders and non-media orphan files in download directories."""
    import asyncio

    try:
        from scripts.import_orphans import DOWNLOAD_SOURCES, clean_empty_and_orphans

        # Execute in thread pool to avoid blocking async event loop
        loop = asyncio.get_running_loop()
        deleted_dirs, deleted_files = await loop.run_in_executor(
            None, clean_empty_and_orphans, DOWNLOAD_SOURCES, False
        )
        return {
            "status": "ok",
            "message": f"Nettoyage terminé : {deleted_dirs} dossiers et {deleted_files} fichiers orphelins supprimés.",
            "deleted_dirs": deleted_dirs,
            "deleted_files": deleted_files,
        }
    except Exception as exc:
        logger.error("Failed to clean orphans: %s", exc)
        return {"status": "error", "message": str(exc)}


async def get_recent_media_for_addon(db: AsyncSession) -> list[dict[str, Any]]:
    """Return recently added movies and series for Kodi widgets."""
    from app.services.media_aggregator import fetch_all_media

    try:
        all_media = await fetch_all_media(db)
        # Sort by added date or id descending
        # Clé « added » (date ISO 8601 de *arr, triable telle quelle). L'ancienne
        # clé « added_at » n'existait pas : la liste n'était pas triée du tout.
        sorted_media = sorted(
            [m for m in all_media if m.get("has_file")],
            key=lambda x: x.get("added") or "",
            reverse=True,
        )
        return sorted_media[:20]
    except Exception as exc:
        logger.error("Failed to fetch recent media for Kodi: %s", exc)
        return []

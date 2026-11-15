"""Kodi : maintenance de la bibliothèque (nettoyage, test de connexion, écarts avec Radarr)."""

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.kodi.rpc import _auth_of, _pick, _rpc
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


# ── Feature: maintenance (clean + drift) ──────────────────────
async def clean_library(db: AsyncSession, service_id: int | None = None) -> dict[str, Any]:
    """Trigger VideoLibrary.Clean on a Kodi instance."""
    kodi = await _pick(db, service_id)
    if not kodi:
        return {"status": "error", "detail": "Aucun Kodi configuré"}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await _rpc(client, kodi.url, auth, "VideoLibrary.Clean", {"showdialogs": False})
        return {"status": "ok", "kodi": kodi.name}
    except Exception as exc:
        logger.error("Kodi clean failed: %s", exc)
        return {"status": "error", "detail": f"{type(exc).__name__}"}


async def test_connection(db: AsyncSession, service_id: int) -> dict[str, Any]:
    """Ping a Kodi instance and read its version."""
    svc = await db.get(Service, service_id)
    if not svc or svc.type != "kodi":
        return {"ok": False, "detail": "Instance inconnue"}
    auth = _auth_of(svc)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await _rpc(client, svc.url, auth, "JSONRPC.Ping")
            app = await _rpc(
                client,
                svc.url,
                auth,
                "Application.GetProperties",
                {"properties": ["version", "name"]},
            )
        v = (app or {}).get("version", {})
        return {
            "ok": True,
            "version": f"{v.get('major', '?')}.{v.get('minor', '')}",
            "name": (app or {}).get("name", "Kodi"),
        }
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}"}


async def get_drift(db: AsyncSession) -> dict[str, Any]:
    """Compare the Radarr library with the Kodi library (by TMDB id).

    Returns movies present in Radarr but missing from Kodi (need a scan) and
    movies present in Kodi but unknown to Radarr (orphans).
    """
    from app.services.radarr import RadarrClient

    # Radarr side
    radarr_by_tmdb: dict[str, dict] = {}
    stmt = select(Service).where(Service.is_enabled == True, Service.type == "radarr")  # noqa: E712
    rsvc = (await db.execute(stmt)).scalars().first()
    if rsvc:
        client = RadarrClient(url=rsvc.url, api_key=decrypt_api_key(rsvc.api_key))
        try:
            for m in await client.get("/movie"):
                if m.get("tmdbId") and m.get("hasFile"):
                    radarr_by_tmdb[str(m["tmdbId"])] = {
                        "title": m.get("title"),
                        "year": m.get("year"),
                    }
        except Exception as exc:
            logger.warning("Drift: Radarr fetch failed: %s", exc)
        finally:
            await client.close()

    # Kodi side
    kodi_tmdb: set[str] = set()
    kodi = await _pick(db, None)
    if kodi:
        auth = _auth_of(kodi)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await _rpc(
                    client, kodi.url, auth, "VideoLibrary.GetMovies", {"properties": ["uniqueid"]}
                )
            for m in (res or {}).get("movies", []):
                t = (m.get("uniqueid") or {}).get("tmdb")
                if t:
                    kodi_tmdb.add(str(t))
        except Exception as exc:
            logger.warning("Drift: Kodi fetch failed: %s", exc)

    missing_in_kodi = [
        {"tmdb_id": t, **info} for t, info in radarr_by_tmdb.items() if t not in kodi_tmdb
    ]
    return {
        "radarr_total": len(radarr_by_tmdb),
        "kodi_total": len(kodi_tmdb),
        "missing_in_kodi": sorted(missing_in_kodi, key=lambda x: x.get("year") or 0, reverse=True),
        "missing_count": len(missing_in_kodi),
    }

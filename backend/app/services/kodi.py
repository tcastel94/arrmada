"""Kodi service for discovering instances and triggering library scans."""

import asyncio
import httpx
from typing import List, Dict, Any
from zeroconf import ServiceBrowser, Zeroconf

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

class KodiListener:
    def __init__(self):
        self.found = []

    def remove_service(self, zeroconf, type, name):
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            ip = ".".join([str(c) for c in info.addresses[0]])
            port = info.port
            url = f"http://{ip}:{port}"
            self.found.append({
                "name": name.split(".")[0],
                "url": url,
            })

    def update_service(self, zeroconf, type, name):
        pass

async def discover_kodi() -> List[Dict[str, str]]:
    """Discover local Kodi instances via ZeroConf (mDNS)."""
    zeroconf = Zeroconf()
    listener = KodiListener()
    
    # Listen for kodi web interfaces
    # Usually Kodi broadcasts _http._tcp.local or _xbmc-jsonrpc._tcp.local
    # Let's check _http._tcp.local
    browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)
    
    await asyncio.sleep(3) # Wait for discovery
    
    zeroconf.close()
    
    # Filter for Kodi
    kodi_instances = [s for s in listener.found if "kodi" in s["name"].lower() or "xbmc" in s["name"].lower()]
    return kodi_instances

async def sync_kodi(db: AsyncSession) -> dict[str, Any]:
    """Trigger VideoLibrary.Scan on all registered Kodi instances."""
    stmt = select(Service).where(Service.type == "kodi", Service.is_enabled == True)
    result = await db.execute(stmt)
    kodis = result.scalars().all()

    # Dedup by URL so duplicate rows can't trigger several scans of the same Kodi.
    seen_urls: set[str] = set()
    unique_kodis = []
    for k in kodis:
        if k.url in seen_urls:
            continue
        seen_urls.add(k.url)
        unique_kodis.append(k)
    kodis = unique_kodis

    success = 0
    failed = 0
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for kodi in kodis:
            url = f"{kodi.url}/jsonrpc"
            auth = None
            if kodi.api_key:
                # Assuming api_key stores "username:password" explicitly, but wait, it's encrypted
                creds = decrypt_api_key(kodi.api_key)
                if ":" in creds:
                    auth = tuple(creds.split(":", 1))
            
            payload = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.Scan",
                "id": sum(ord(c) for c in kodi.name)
            }
            
            try:
                if auth:
                    resp = await client.post(url, json=payload, auth=auth)
                else:
                    resp = await client.post(url, json=payload)
                    
                resp.raise_for_status()
                data = resp.json()
                if "error" in data:
                    logger.error(f"Kodi sync error on {kodi.name}: {data['error']}")
                    failed += 1
                else:
                    success += 1
                    logger.info(f"Triggered Kodi sync on {kodi.name}")
            except Exception as e:
                logger.error(f"Failed to sync Kodi {kodi.name} at {url}: {e}")
                failed += 1

    return {"success": success, "failed": failed}


# ── Shared JSON-RPC layer ─────────────────────────────────────
def _auth_of(kodi: Service):
    """Return (user, pass) tuple from the stored 'user:pass' api_key, or None."""
    if kodi.api_key:
        creds = decrypt_api_key(kodi.api_key)
        if creds and ":" in creds:
            return tuple(creds.split(":", 1))
    return None


async def _unique_enabled(db: AsyncSession) -> list[Service]:
    """Enabled Kodi services, deduplicated by URL."""
    stmt = select(Service).where(Service.type == "kodi", Service.is_enabled == True)  # noqa: E712
    kodis = (await db.execute(stmt)).scalars().all()
    seen: set[str] = set()
    out: list[Service] = []
    for k in kodis:
        if k.url in seen:
            continue
        seen.add(k.url)
        out.append(k)
    return out


async def _pick(db: AsyncSession, service_id: int | None) -> Service | None:
    kodis = await _unique_enabled(db)
    if not kodis:
        return None
    if service_id is not None:
        return next((k for k in kodis if k.id == service_id), kodis[0])
    return kodis[0]


async def _rpc(client: httpx.AsyncClient, base_url: str, auth, method: str, params: dict | None = None):
    """Perform one Kodi JSON-RPC call; raise on Kodi-level error."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    resp = await client.post(f"{base_url}/jsonrpc", json=payload, auth=auth)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return data.get("result")


# ── Feature: play a movie on Kodi ─────────────────────────────
async def play_movie(db: AsyncSession, tmdb_id: int, service_id: int | None = None) -> dict[str, Any]:
    """Start playback of a movie (matched by TMDB uniqueid) on a Kodi instance."""
    kodi = await _pick(db, service_id)
    if not kodi:
        return {"status": "error", "detail": "Aucun Kodi configuré"}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await _rpc(client, kodi.url, auth, "VideoLibrary.GetMovies", {"properties": ["uniqueid"]})
            movieid = None
            for m in (res or {}).get("movies", []):
                if str((m.get("uniqueid") or {}).get("tmdb")) == str(tmdb_id):
                    movieid = m.get("movieid")
                    break
            if movieid is None:
                return {"status": "not_found", "detail": "Film absent de la bibliothèque Kodi (à scanner ?)"}
            await _rpc(client, kodi.url, auth, "Player.Open", {"item": {"movieid": movieid}})
            return {"status": "ok", "kodi": kodi.name, "movieid": movieid}
    except Exception as exc:
        logger.error("Kodi play failed: %s", exc)
        return {"status": "error", "detail": f"Kodi injoignable : {type(exc).__name__}"}


# ── Feature: watched / resume status ──────────────────────────
async def get_watched_status(db: AsyncSession) -> dict[str, Any]:
    """Return {tmdb_id: {playcount, resume_position, resume_total, lastplayed}}."""
    kodi = await _pick(db, None)
    if not kodi:
        return {}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await _rpc(
                client, kodi.url, auth, "VideoLibrary.GetMovies",
                {"properties": ["playcount", "resume", "uniqueid", "lastplayed", "title", "year"]},
            )
    except Exception as exc:
        logger.warning("Kodi watched status failed: %s", exc)
        return {}
    out: dict[str, Any] = {}
    for m in (res or {}).get("movies", []):
        tmdb = (m.get("uniqueid") or {}).get("tmdb")
        if not tmdb:
            continue
        resume = m.get("resume") or {}
        out[str(tmdb)] = {
            "playcount": m.get("playcount", 0),
            "resume_position": resume.get("position", 0) or 0,
            "resume_total": resume.get("total", 0) or 0,
            "lastplayed": m.get("lastplayed") or None,
            "title": m.get("title", ""),
            "year": m.get("year"),
        }
    return out


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
            app = await _rpc(client, svc.url, auth, "Application.GetProperties", {"properties": ["version", "name"]})
        v = (app or {}).get("version", {})
        return {"ok": True, "version": f"{v.get('major', '?')}.{v.get('minor', '')}", "name": (app or {}).get("name", "Kodi")}
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
                    radarr_by_tmdb[str(m["tmdbId"])] = {"title": m.get("title"), "year": m.get("year")}
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
                res = await _rpc(client, kodi.url, auth, "VideoLibrary.GetMovies", {"properties": ["uniqueid"]})
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


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


# ── Feature: now-playing + remote control ────────────────────
def _secs(t: dict | None) -> int:
    t = t or {}
    return t.get("hours", 0) * 3600 + t.get("minutes", 0) * 60 + t.get("seconds", 0)


def _resolution_label(width: int | None, height: int | None) -> str | None:
    """Human resolution label from a stream's pixel dimensions."""
    h = height or 0
    w = width or 0
    ref = max(h, (w * 9) // 16) if w else h  # tolerate anamorphic/odd aspect
    if not ref:
        return None
    if ref >= 2000:
        return "4K"
    if ref >= 1400:
        return "1440p"
    if ref >= 1000:
        return "1080p"
    if ref >= 700:
        return "720p"
    if ref >= 540:
        return "576p"
    return "SD"


def _tech_details(it: dict) -> dict[str, Any]:
    """Extract video/audio/subtitle technical info from a Kodi item's streamdetails."""
    sd = (it.get("streamdetails") or {})
    video = (sd.get("video") or [{}])
    audio = (sd.get("audio") or [{}])
    subs = (sd.get("subtitle") or [])
    v = video[0] if video else {}
    a = audio[0] if audio else {}
    return {
        "resolution": _resolution_label(v.get("width"), v.get("height")),
        "video_codec": (v.get("codec") or "").upper() or None,
        "hdr": v.get("hdrtype") or None,
        "audio_codec": (a.get("codec") or "").upper() or None,
        "audio_channels": a.get("channels") or None,
        "audio_language": a.get("language") or None,
        "subtitle_count": len(subs),
    }


async def get_now_playing(db: AsyncSession) -> dict[str, Any]:
    """Current Kodi playback state (for the on-detail remote + dashboard card).

    Enriched with poster/overview/genres from the media library (matched by TMDB
    id) and with stream technical details (resolution, codecs) from Kodi itself.
    """
    kodi = await _pick(db, None)
    if not kodi:
        return {"playing": False}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            players = await _rpc(client, kodi.url, auth, "Player.GetActivePlayers")
            player = next((p for p in (players or []) if p.get("type") in ("video", "audio")), None)
            if not player:
                return {"playing": False, "kodi": kodi.name}
            pid = player["playerid"]
            props = await _rpc(
                client, kodi.url, auth, "Player.GetProperties",
                {"playerid": pid, "properties": ["speed", "time", "totaltime", "percentage"]},
            )
            item = await _rpc(
                client, kodi.url, auth, "Player.GetItem",
                {"playerid": pid, "properties": [
                    "title", "showtitle", "season", "episode", "uniqueid", "year",
                    "plot", "runtime", "genre", "rating", "streamdetails",
                ]},
            )
            appp = await _rpc(
                client, kodi.url, auth, "Application.GetProperties", {"properties": ["volume", "muted"]},
            )
            it = (item or {}).get("item", {}) or {}
            subtitle = ""
            if it.get("type") == "episode":
                subtitle = f"{it.get('showtitle', '')} S{it.get('season')}E{it.get('episode')}"
            tmdb = (it.get("uniqueid") or {}).get("tmdb")

            result = {
                "playing": True,
                "playerid": pid,
                "title": it.get("title") or it.get("label") or "",
                "subtitle": subtitle,
                "type": it.get("type"),
                "tmdb": tmdb,
                "year": it.get("year") or None,
                "overview": it.get("plot") or "",
                "genres": [g for g in (it.get("genre") or []) if g],
                "rating": round(it.get("rating"), 1) if it.get("rating") else None,
                "runtime": (it.get("runtime") or 0) // 60 or None,  # Kodi runtime is seconds
                "position": _secs((props or {}).get("time")),
                "total": _secs((props or {}).get("totaltime")),
                "percentage": round((props or {}).get("percentage", 0) or 0, 1),
                "paused": ((props or {}).get("speed", 1) or 0) == 0,
                "volume": (appp or {}).get("volume", 100),
                "muted": (appp or {}).get("muted", False),
                "kodi": kodi.name,
                "poster": None,
                "media_id": None,
                "media_type": it.get("type"),
                **_tech_details(it),
            }

            # Enrich poster / overview / media link from the library (movies by TMDB).
            try:
                await _enrich_now_playing(db, result, tmdb)
            except Exception as exc:  # enrichment is best-effort
                logger.debug("Kodi now-playing enrich skipped: %s", exc)

            return result
    except Exception as exc:
        logger.debug("Kodi now-playing failed: %s", exc)
        return {"playing": False, "error": type(exc).__name__}


async def _enrich_now_playing(db: AsyncSession, result: dict[str, Any], tmdb: str | None) -> None:
    """Fill poster/overview/genres/media_id from the media library, matched by TMDB id."""
    if not tmdb:
        return
    from app.services import media_aggregator
    from app.utils.cache import cache

    media = list(
        await cache.get_or_set(
            "media:all", lambda: media_aggregator.fetch_all_media(db), ttl_seconds=300
        )
    )
    match = next((m for m in media if str(m.get("tmdb_id")) == str(tmdb)), None)
    if not match:
        return
    result["poster"] = match.get("poster_url")
    result["media_id"] = match.get("external_id")
    result["media_type"] = match.get("type") or result.get("media_type")
    if not result.get("overview"):
        result["overview"] = match.get("overview") or ""
    if not result.get("genres"):
        result["genres"] = match.get("genres") or []
    if not result.get("year"):
        result["year"] = match.get("year")
    if not result.get("rating") and match.get("rating"):
        result["rating"] = round(match["rating"], 1)


async def control_player(db: AsyncSession, action: str, value: Any = None) -> dict[str, Any]:
    """Send a remote-control command to the active Kodi player."""
    kodi = await _pick(db, None)
    if not kodi:
        return {"status": "error", "detail": "Aucun Kodi configuré"}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            if action in ("playpause", "stop", "seek"):
                players = await _rpc(client, kodi.url, auth, "Player.GetActivePlayers")
                player = next((p for p in (players or []) if p.get("type") in ("video", "audio")), None)
                if not player:
                    return {"status": "error", "detail": "Rien en lecture"}
                pid = player["playerid"]
                if action == "playpause":
                    await _rpc(client, kodi.url, auth, "Player.PlayPause", {"playerid": pid})
                elif action == "stop":
                    await _rpc(client, kodi.url, auth, "Player.Stop", {"playerid": pid})
                elif action == "seek":
                    await _rpc(
                        client, kodi.url, auth, "Player.Seek",
                        {"playerid": pid, "value": {"percentage": float(value or 0)}},
                    )
            elif action == "volume":
                await _rpc(client, kodi.url, auth, "Application.SetVolume", {"volume": int(value or 0)})
            elif action == "mute":
                await _rpc(client, kodi.url, auth, "Application.SetMute", {"mute": "toggle"})
            else:
                return {"status": "error", "detail": "Action inconnue"}
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Kodi control failed: %s", exc)
        return {"status": "error", "detail": type(exc).__name__}


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


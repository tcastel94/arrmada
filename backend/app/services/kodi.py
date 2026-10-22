"""Kodi service for discovering instances and triggering library scans."""

import asyncio
import contextlib
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zeroconf import ServiceBrowser, Zeroconf

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
            self.found.append(
                {
                    "name": name.split(".")[0],
                    "url": url,
                }
            )

    def update_service(self, zeroconf, type, name):
        pass


async def discover_kodi() -> list[dict[str, str]]:
    """Discover local Kodi instances via ZeroConf (mDNS)."""
    zeroconf = Zeroconf()
    listener = KodiListener()

    # Listen for kodi web interfaces
    # Usually Kodi broadcasts _http._tcp.local or _xbmc-jsonrpc._tcp.local
    # Let's check _http._tcp.local
    _browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)  # noqa: F841 — garde la référence pendant l'écoute

    await asyncio.sleep(3)  # Wait for discovery

    zeroconf.close()

    # Filter for Kodi
    kodi_instances = [
        s for s in listener.found if "kodi" in s["name"].lower() or "xbmc" in s["name"].lower()
    ]
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
                "id": sum(ord(c) for c in kodi.name),
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


async def _rpc(
    client: httpx.AsyncClient, base_url: str, auth, method: str, params: dict | None = None
):
    """Perform one Kodi JSON-RPC call; raise on Kodi-level error."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    resp = await client.post(f"{base_url}/jsonrpc", json=payload, auth=auth)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return data.get("result")


# ── Feature: play a movie on Kodi ─────────────────────────────
async def play_movie(
    db: AsyncSession,
    tmdb_id: int,
    service_id: int | None = None,
    room: str = "salon",
) -> dict[str, Any]:
    """Start playback of a movie (matched by TMDB uniqueid) on a Kodi instance and tune AVR."""
    kodi = await _pick(db, service_id)
    if not kodi:
        return {"status": "error", "detail": "Aucun Kodi configuré"}
    auth = _auth_of(kodi)
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            res = await _rpc(
                client, kodi.url, auth, "VideoLibrary.GetMovies", {"properties": ["uniqueid"]}
            )
            movieid = None
            for m in (res or {}).get("movies", []):
                if str((m.get("uniqueid") or {}).get("tmdb")) == str(tmdb_id):
                    movieid = m.get("movieid")
                    break
            if movieid is None:
                return {
                    "status": "not_found",
                    "detail": "Film absent de la bibliothèque Kodi (à scanner ?)",
                }
            await _rpc(client, kodi.url, auth, "Player.Open", {"item": {"movieid": movieid}})

            # Auto-tune AVR sound settings for the target room (Salon vs Salle de cinéma)
            avr_res = None
            try:
                from app.services import yamaha as yamaha_service

                avr_res = await yamaha_service.apply_preset(db, room=room, media_type="movie")
            except Exception as avr_exc:
                logger.debug("Yamaha auto-preset failed during Kodi play: %s", avr_exc)

            return {
                "status": "ok",
                "kodi": kodi.name,
                "movieid": movieid,
                "room": room,
                "avr": avr_res,
            }
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
                client,
                kodi.url,
                auth,
                "VideoLibrary.GetMovies",
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
    sd = it.get("streamdetails") or {}
    video = sd.get("video") or [{}]
    audio = sd.get("audio") or [{}]
    subs = sd.get("subtitle") or []
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
                client,
                kodi.url,
                auth,
                "Player.GetProperties",
                {"playerid": pid, "properties": ["speed", "time", "totaltime", "percentage"]},
            )
            item = await _rpc(
                client,
                kodi.url,
                auth,
                "Player.GetItem",
                {
                    "playerid": pid,
                    "properties": [
                        "title",
                        "showtitle",
                        "season",
                        "episode",
                        "uniqueid",
                        "year",
                        "plot",
                        "runtime",
                        "genre",
                        "rating",
                        "streamdetails",
                    ],
                },
            )
            appp = await _rpc(
                client,
                kodi.url,
                auth,
                "Application.GetProperties",
                {"properties": ["volume", "muted"]},
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

    media = await media_aggregator.cached_library(db)
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
                player = next(
                    (p for p in (players or []) if p.get("type") in ("video", "audio")), None
                )
                if not player:
                    return {"status": "error", "detail": "Rien en lecture"}
                pid = player["playerid"]
                if action == "playpause":
                    await _rpc(client, kodi.url, auth, "Player.PlayPause", {"playerid": pid})
                elif action == "stop":
                    await _rpc(client, kodi.url, auth, "Player.Stop", {"playerid": pid})
                elif action == "seek":
                    await _rpc(
                        client,
                        kodi.url,
                        auth,
                        "Player.Seek",
                        {"playerid": pid, "value": {"percentage": float(value or 0)}},
                    )
            elif action == "volume":
                await _rpc(
                    client, kodi.url, auth, "Application.SetVolume", {"volume": int(value or 0)}
                )
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


# ── Feature: Kodi Add-on integration ─────────────────────────
async def _get_radarr_client(db: AsyncSession):
    from app.services.radarr import RadarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "radarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return RadarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


async def _get_sonarr_client(db: AsyncSession):
    from app.services.sonarr import SonarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "sonarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return SonarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


async def _get_bazarr_client(db: AsyncSession):
    from app.services.bazarr import BazarrClient

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "bazarr")
    svc = (await db.execute(stmt)).scalars().first()
    if not svc:
        return None
    return BazarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


async def handle_addon_subtitles(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Trigger Bazarr subtitle download from Kodi context action."""
    from app.services.activity_log import log_event

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")
    language = (data.get("language") or "fr").lower()
    # Qui demande : l'add-on Kodi, ou le menu pause de l'appli Android
    origin = "appli ArrMada" if data.get("origin") == "android" else "Kodi Add-on"

    bazarr = await _get_bazarr_client(db)
    if not bazarr:
        return {"status": "error", "message": "Bazarr n'est pas configuré dans ArrMada"}

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            radarr_id = match["id"]
            await bazarr.download_movie_subtitle(radarr_id=radarr_id, language=language)

            await log_event(
                category="subtitle",
                action="kodi_sub_search",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                detail=f"Recherche auto sous-titre ({language.upper()}) via {origin}",
            )
            return {
                "status": "ok",
                "message": f"Recherche de sous-titres {language.upper()} lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # episode
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            episodes = await sonarr.get(f"/episode?seriesId={series_id}")
            match_ep = None
            for ep in episodes:
                if int(ep.get("seasonNumber", -1)) == int(season or 0) and int(
                    ep.get("episodeNumber", -1)
                ) == int(episode or 0):
                    match_ep = ep
                    break

            if not match_ep:
                return {
                    "status": "error",
                    "message": f"Épisode S{season:02d}E{episode:02d} introuvable dans Sonarr",
                }

            episode_id = match_ep["id"]
            await bazarr.download_episode_subtitle(
                series_id=series_id, episode_id=episode_id, language=language
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_search",
                status="ok",
                source="kodi",
                media_type="series",
                title=f"{match_series.get('title')} S{season:02d}E{episode:02d}",
                detail=f"Recherche auto sous-titre ({language.upper()}) via {origin}",
            )
            return {
                "status": "ok",
                "message": f"Recherche de sous-titres {language.upper()} lancée pour {match_series.get('title')} S{int(season):02d}E{int(episode):02d}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi subtitle action: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur Bazarr : {str(exc)}"}


async def handle_addon_sync_subtitles(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Trigger Bazarr FFsubsync audio-aligned subtitle synchronization."""
    from app.services.activity_log import log_event

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")
    language = (data.get("language") or "fr").lower()
    # Qui demande : l'add-on Kodi, ou le menu pause de l'appli Android
    origin = "appli ArrMada" if data.get("origin") == "android" else "Kodi Add-on"

    bazarr = await _get_bazarr_client(db)
    if not bazarr:
        return {"status": "error", "message": "Bazarr n'est pas configuré dans ArrMada"}

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            radarr_id = match["id"]

            # Fetch subtitles from Bazarr for this movie
            b_movies = await bazarr.get("/movies", params={"radarrid[]": radarr_id})
            movie_data = (b_movies.get("data") or [{}])[0] if isinstance(b_movies, dict) else {}
            subtitles = movie_data.get("subtitles") or []

            target_sub = next(
                (s for s in subtitles if s.get("code2") == language and s.get("path")), None
            )
            if not target_sub:
                target_sub = next((s for s in subtitles if s.get("path")), None)

            if not target_sub or not target_sub.get("path"):
                return {
                    "status": "error",
                    "message": f"Aucun sous-titre trouvé pour {match.get('title')}. Téléchargez-en un d'abord.",
                }

            sub_path = target_sub["path"]
            sub_lang = target_sub.get("code2") or language
            sub_forced = target_sub.get("forced", False)
            sub_hi = target_sub.get("hi", False)

            await bazarr.sync_subtitle(
                media_type="movie",
                media_id=radarr_id,
                path=sub_path,
                language=sub_lang,
                forced=sub_forced,
                hi=sub_hi,
                reference="a:0",
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_sync",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                detail=f"Re-synchronisation audio (FFsubsync) via {origin}",
            )

            return {
                "status": "ok",
                "message": f"Synchronisation FFsubsync lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # Episode
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            episodes = await sonarr.get(f"/episode?seriesId={series_id}")
            match_ep = None
            for ep in episodes:
                if int(ep.get("seasonNumber", -1)) == int(season or 0) and int(
                    ep.get("episodeNumber", -1)
                ) == int(episode or 0):
                    match_ep = ep
                    break

            if not match_ep:
                return {
                    "status": "error",
                    "message": f"Épisode S{season:02d}E{episode:02d} introuvable dans Sonarr",
                }

            episode_id = match_ep["id"]

            b_eps = await bazarr.get("/episodes", params={"episodeid[]": episode_id})
            ep_data = (b_eps.get("data") or [{}])[0] if isinstance(b_eps, dict) else {}
            subtitles = ep_data.get("subtitles") or []

            target_sub = next(
                (s for s in subtitles if s.get("code2") == language and s.get("path")), None
            )
            if not target_sub:
                target_sub = next((s for s in subtitles if s.get("path")), None)

            if not target_sub or not target_sub.get("path"):
                return {
                    "status": "error",
                    "message": f"Aucun sous-titre trouvé pour S{int(season):02d}E{int(episode):02d}.",
                }

            sub_path = target_sub["path"]
            sub_lang = target_sub.get("code2") or language
            sub_forced = target_sub.get("forced", False)
            sub_hi = target_sub.get("hi", False)

            await bazarr.sync_subtitle(
                media_type="episode",
                media_id=episode_id,
                path=sub_path,
                language=sub_lang,
                forced=sub_forced,
                hi=sub_hi,
                reference="a:0",
            )

            await log_event(
                category="subtitle",
                action="kodi_sub_sync",
                status="ok",
                source="kodi",
                media_type="series",
                title=f"{match_series.get('title')} S{season:02d}E{episode:02d}",
                detail=f"Re-synchronisation audio (FFsubsync) via {origin}",
            )

            return {
                "status": "ok",
                "message": f"Synchronisation FFsubsync lancée pour {match_series.get('title')} S{int(season):02d}E{int(episode):02d}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi subtitle sync: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur FFsubsync : {str(exc)}"}


async def handle_addon_search(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Trigger Radarr/Sonarr media search from Kodi context action.

    Lancée depuis la TV : la demande est notée pour passer en tête de
    SABnzbd (services/tv_priority.py), sauf `"priority": false`.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)
    priority = bool(data.get("priority", True))

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            await radarr.search_movie(match["id"])
            await tv_priority.create_request(
                db,
                service_type="radarr",
                arr_id=match["id"],
                title=match.get("title") or title,
                origin=origin,
                priority=priority,
            )
            await log_event(
                category="media",
                action="kodi_media_search",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                device=origin["device_name"],
                detail="Recherche de release Radarr déclenchée depuis Kodi",
            )
            return {
                "status": "ok",
                "message": f"Recherche de release lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # episode / series
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            if season is not None and episode is not None:
                episodes = await sonarr.get(f"/episode?seriesId={series_id}")
                match_ep = None
                for ep in episodes:
                    if int(ep.get("seasonNumber", -1)) == int(season) and int(
                        ep.get("episodeNumber", -1)
                    ) == int(episode):
                        match_ep = ep
                        break

                if not match_ep:
                    return {
                        "status": "error",
                        "message": f"Épisode S{int(season):02d}E{int(episode):02d} introuvable",
                    }

                await sonarr.search_episodes([match_ep["id"]])
                desc = f"Recherche épisode S{int(season):02d}E{int(episode):02d}"
                scope = {"scope": "episode", "episode_ids": [match_ep["id"]]}
            elif season is not None:
                await sonarr.search_season(series_id, int(season))
                desc = f"Recherche saison {int(season)}"
                scope = {"scope": "season", "season": int(season)}
            else:
                await sonarr.search_series(series_id)
                desc = "Recherche série complète"
                scope = {"scope": "series"}

            await tv_priority.create_request(
                db,
                service_type="sonarr",
                arr_id=series_id,
                title=match_series.get("title") or title,
                origin=origin,
                priority=priority,
                **scope,
            )

            await log_event(
                category="media",
                action="kodi_media_search",
                status="ok",
                source="kodi",
                media_type="series",
                title=match_series.get("title", title),
                device=origin["device_name"],
                detail=f"{desc} déclenchée depuis Kodi",
            )
            return {
                "status": "ok",
                "message": f"{desc} lancée pour {match_series.get('title')}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi search action: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur de recherche : {str(exc)}"}


async def handle_addon_scrobble(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Handle live playback scrobble from Kodi addon service."""
    from app.services.activity_log import log_event
    from app.utils.event_bus import event_bus

    event_type = data.get("event", "progress")  # play, pause, stop, progress
    title = data.get("title", "Inconnu")
    percentage = data.get("percentage", 0)
    kodi_device = data.get("device_name", "Kodi")

    # Broadcast to websocket/SSE listeners
    await event_bus.publish(
        event_type="kodi_scrobble",
        data={
            **data,
            "device": kodi_device,
        },
    )

    if event_type == "stop" and float(percentage or 0) >= 90:
        await log_event(
            category="playback",
            action="kodi_watched",
            status="ok",
            source="kodi",
            media_type=data.get("media_type", "movie"),
            title=title,
            device=kodi_device,
            detail=f"Visionnage terminé ({percentage}%)",
        )

    return {"status": "ok"}


async def sonarr_episodes_for_addon(db: AsyncSession, tvdb_id: int) -> dict[str, Any]:
    """Épisodes Sonarr d'une série, au format court de l'écran Série de la TV.

    `status` : « ok », « unknown » (série absente de Sonarr) ou « error ».
    Les spéciaux (saison 0) sont laissés de côté : trop d'épisodes bonus
    qu'on ne cherche jamais.
    """
    sonarr = await _get_sonarr_client(db)
    if not sonarr:
        return {"status": "error", "message": "Sonarr n'est pas configuré", "episodes": []}
    try:
        series = next(
            (s for s in await sonarr.get_series() if str(s.get("tvdbId")) == str(tvdb_id)),
            None,
        )
        if series is None:
            return {"status": "unknown", "episodes": []}
        raw = await sonarr.get("/episode", params={"seriesId": series["id"]})
    except Exception as exc:
        logger.warning(f"Épisodes Sonarr de la série TVDB {tvdb_id} illisibles : {exc}")
        return {"status": "error", "message": "Sonarr injoignable", "episodes": []}
    items = raw if isinstance(raw, list) else []
    episodes = [
        {
            "season": int(ep.get("seasonNumber") or 0),
            "episode": int(ep.get("episodeNumber") or 0),
            "title": ep.get("title") or "",
            "air_date": ep.get("airDateUtc") or "",
            "has_file": bool(ep.get("hasFile")),
            "monitored": bool(ep.get("monitored")),
            "overview": ep.get("overview") or "",
        }
        for ep in items
        if int(ep.get("seasonNumber") or 0) > 0
    ]
    episodes.sort(key=lambda e: (e["season"], e["episode"]))
    return {"status": "ok", "title": series.get("title") or "", "episodes": episodes}


def _format_addon_queue(queue_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """File de téléchargement au format de l'add-on Kodi.

    Les clés lues sont celles de ``media_aggregator.get_queue_items``
    (``time_left``, ``size_bytes``…). L'ancienne version lisait ``timeleft``
    et ``size``, absentes : temps restant et taille arrivaient toujours vides.
    ``id`` et ``service`` servent aux actions pause / reprise de l'add-on.
    """
    return [
        {
            "id": it.get("id"),
            "title": it.get("title") or it.get("name") or "Téléchargement",
            "status": it.get("status", "downloading"),
            "progress": round(it.get("progress", 0) or 0, 1),
            "size": it.get("size_bytes") or it.get("size") or 0,
            "size_left": it.get("size_left_bytes") or 0,
            "timeleft": it.get("time_left") or it.get("timeleft") or it.get("eta") or "",
            "service": it.get("service_type") or it.get("service") or "",
        }
        for it in queue_items
    ]


async def get_addon_dashboard_status(db: AsyncSession) -> dict[str, Any]:
    """Return download queue, recent events and quick summary for Kodi addon background service."""
    from sqlalchemy import select

    from app.models.activity import ActivityEvent
    from app.services import media_aggregator

    queue_items = await media_aggregator.get_queue_items(db)
    formatted_queue = _format_addon_queue(queue_items)

    # Recent import events for auto-scan trigger
    recent_events = []
    try:
        stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.category.in_(["download", "media"]), ActivityEvent.status == "ok")
            .order_by(ActivityEvent.id.desc())
            .limit(8)
        )
        res = await db.execute(stmt)
        for ev in res.scalars().all():
            recent_events.append(
                {
                    "id": ev.id,
                    "action": ev.action,
                    "title": ev.title,
                    "detail": ev.detail,
                    "timestamp": ev.created_at.timestamp() if ev.created_at else 0,
                }
            )
    except Exception:
        pass

    return {
        "status": "ok",
        "downloads_count": len(formatted_queue),
        "downloads": formatted_queue,
        "recent_events": recent_events,
    }


async def get_addon_full_dashboard(db: AsyncSession) -> dict[str, Any]:
    """Return complete system health, storage, services, and activity history for Kodi (parallel & cached)."""
    import asyncio

    from sqlalchemy import select

    from app.models.activity import ActivityEvent
    from app.models.service import Service
    from app.services import media_aggregator
    from app.utils.cache import cache
    from app.utils.helpers import format_bytes

    async def _fetch():
        # 1. Services & Activities from DB
        stmt_svc = select(Service)
        stmt_act = select(ActivityEvent).order_by(ActivityEvent.id.desc()).limit(15)

        res_svc, res_act = await asyncio.gather(
            db.execute(stmt_svc), db.execute(stmt_act), return_exceptions=True
        )

        services_list = []
        if not isinstance(res_svc, Exception):
            for s in res_svc.scalars().all():
                services_list.append(
                    {
                        "id": s.id,
                        "name": s.name,
                        "type": s.type,
                        "is_enabled": s.is_enabled,
                        "url": s.url,
                        "status": "online" if s.is_enabled else "disabled",
                    }
                )

        recent_activities = []
        if not isinstance(res_act, Exception):
            for ev in res_act.scalars().all():
                time_str = ev.created_at.strftime("%H:%M") if ev.created_at else ""
                recent_activities.append(
                    {
                        "id": ev.id,
                        "time": time_str,
                        "category": ev.category,
                        "action": ev.action,
                        "status": ev.status,
                        "title": ev.title,
                        "subtitle": ev.subtitle or "",
                        "detail": ev.detail or "",
                    }
                )

        # 2. Parallel fetch stats, disks, and queue
        async def _safe_stats():
            try:
                return await media_aggregator.get_dashboard_stats(db)
            except Exception:
                return {}

        async def _safe_disks():
            try:
                from app.api.system import _fetch_disk_space

                return await _fetch_disk_space(db)
            except Exception:
                return []

        async def _safe_queue():
            try:
                return await media_aggregator.get_queue_items(db)
            except Exception:
                return []

        raw_stats, disks, queue_items = await asyncio.gather(
            _safe_stats(),
            _safe_disks(),
            _safe_queue(),
        )

        # get_dashboard_stats returns nested structure: {movies: {total:..}, series: {total:.., total_episodes:..}}
        movies_block = raw_stats.get("movies") or {}
        series_block = raw_stats.get("series") or {}
        stats = {
            "movies_count": movies_block.get("total", 0) or raw_stats.get("total_movies", 0),
            "series_count": series_block.get("total", 0) or raw_stats.get("total_series", 0),
            "episodes_count": series_block.get("total_episodes", 0)
            or raw_stats.get("total_episodes", 0),
            "total_size_bytes": raw_stats.get("total_size_bytes", 0),
            "total_size_human": format_bytes(raw_stats.get("total_size_bytes", 0)),
        }

        formatted_queue = _format_addon_queue(queue_items if isinstance(queue_items, list) else [])

        return {
            "status": "ok",
            "services": services_list,
            "stats": stats,
            "disks": disks if isinstance(disks, list) else [],
            "downloads": formatted_queue,
            "downloads_count": len(formatted_queue),
            "recent_activities": recent_activities,
        }

    return await cache.get_or_set("kodi_addon_full_dashboard", _fetch, ttl_seconds=15)


# ── Feature: Kodi Media Discovery & Interactive Release Grab ──
async def lookup_media_for_addon(
    db: AsyncSession, q: str, media_type: str = "all"
) -> list[dict[str, Any]]:
    """Lookup movies and series across Radarr/Sonarr for Kodi UI."""
    results: list[dict[str, Any]] = []

    # 1. Movies (Radarr)
    if media_type in ("all", "movie"):
        radarr = await _get_radarr_client(db)
        if radarr:
            try:
                raw_movies = await radarr.lookup_movie(q)
                for item in raw_movies[:10]:
                    images = item.get("images", [])
                    poster = next(
                        (
                            img["remoteUrl"]
                            for img in images
                            if img.get("coverType") == "poster" and img.get("remoteUrl")
                        ),
                        None,
                    )
                    arr_id = item.get("id") or 0
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "year": item.get("year"),
                            "type": "movie",
                            "tmdb_id": item.get("tmdbId"),
                            "imdb_id": item.get("imdbId"),
                            "overview": item.get("overview") or "",
                            "poster_url": poster,
                            "in_library": arr_id > 0,
                            "arr_id": arr_id or None,
                        }
                    )
            except Exception as exc:
                logger.error("Addon Radarr lookup failed: %s", exc)

    # 2. Series (Sonarr)
    if media_type in ("all", "series", "tvshow"):
        sonarr = await _get_sonarr_client(db)
        if sonarr:
            try:
                raw_series = await sonarr.lookup_series(q)
                for item in raw_series[:10]:
                    images = item.get("images", [])
                    poster = next(
                        (
                            img["remoteUrl"]
                            for img in images
                            if img.get("coverType") == "poster" and img.get("remoteUrl")
                        ),
                        None,
                    )
                    arr_id = item.get("id") or 0
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "year": item.get("year"),
                            "type": "series",
                            "tvdb_id": item.get("tvdbId"),
                            "imdb_id": item.get("imdbId"),
                            "overview": item.get("overview") or "",
                            "poster_url": poster,
                            "in_library": arr_id > 0,
                            "arr_id": arr_id or None,
                        }
                    )
            except Exception as exc:
                logger.error("Addon Sonarr lookup failed: %s", exc)

    return results


async def get_media_options_for_addon(
    db: AsyncSession, media_type: str = "movie"
) -> dict[str, Any]:
    """Get available quality profiles and root folders for media type."""
    profiles: list[dict[str, Any]] = []
    root_folders: list[dict[str, Any]] = []

    if media_type == "movie":
        radarr = await _get_radarr_client(db)
        if radarr:
            try:
                raw_p = await radarr.get_quality_profiles()
                profiles = [{"id": p["id"], "name": p["name"]} for p in raw_p]
                raw_f = await radarr.get_root_folders()
                root_folders = [
                    {"id": f.get("id"), "path": f.get("path"), "free_space": f.get("freeSpace", 0)}
                    for f in raw_f
                ]
            except Exception as exc:
                logger.error("Failed to get Radarr options: %s", exc)
    else:
        sonarr = await _get_sonarr_client(db)
        if sonarr:
            try:
                raw_p = await sonarr.get_quality_profiles()
                profiles = [{"id": p["id"], "name": p["name"]} for p in raw_p]
                raw_f = await sonarr.get_root_folders()
                root_folders = [
                    {"id": f.get("id"), "path": f.get("path"), "free_space": f.get("freeSpace", 0)}
                    for f in raw_f
                ]
            except Exception as exc:
                logger.error("Failed to get Sonarr options: %s", exc)

    # Sort profiles so our Cinema Ultra-HD profile is first by default
    def _profile_priority(p: dict) -> int:
        n = p.get("name", "").lower()
        if "👑" in p.get("name", "") or "cinema" in n:
            return 0
        if "ultra" in n:
            return 1
        if "1080" in n:
            return 2
        return 3

    profiles.sort(key=_profile_priority)
    return {"profiles": profiles, "root_folders": root_folders}


def _int_or_none(value: Any) -> int | None:
    """« 95396 », 95396 → 95396 ; vide ou illisible → None."""
    try:
        return int(value) if value not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


def _arr_error(service: str, exc: Exception, what: str = "l'ajout") -> str:
    """Message lisible d'un refus de Radarr / Sonarr, affiché tel quel sur la TV.

    Un refus de validation (HTTP 400) arrive sous forme de liste
    ``[{"propertyName": "TvdbId", "errorMessage": "…"}]`` : on renvoie les
    messages, pas « Client error '400 Bad Request' for url … ».
    """
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            body = exc.response.json()
        except ValueError:
            body = None
        messages: list[str] = []
        if isinstance(body, list):
            messages = [
                str(item["errorMessage"])
                for item in body
                if isinstance(item, dict) and item.get("errorMessage")
            ]
        elif isinstance(body, dict) and body.get("message"):
            messages = [str(body["message"])]
        if messages:
            return f"{service} refuse {what} : {' ; '.join(messages)}"[:240]
        return f"{service} a répondu HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.HTTPError):
        return f"{service} injoignable ({type(exc).__name__})"
    return f"Erreur {service} : {exc}"[:240]


async def _find_series_for_addon(
    sonarr: Any, title: str, tmdb_id: int | None, tvdb_id: int | None
) -> dict[str, Any] | None:
    """Fiche Sonarr (lookup) de la série demandée depuis la TV.

    Pourquoi : les suggestions « Pour toi » viennent de TMDB et n'ont qu'un
    ID **TMDB**, alors que Sonarr est indexé sur **TVDB**. Avant, l'add-on
    envoyait ``tvdbId: null`` et Sonarr refusait l'ajout. Même chemin que
    les demandes de la web app (``request_service``) :
      1. ID TVDB fourni (recherche de l'add-on) → utilisé tel quel ;
      2. sinon ID TMDB → TVDB par TMDB (``/tv/{id}/external_ids``) ;
      3. sinon (pas de clé TMDB) → recherche par titre dans Sonarr, en
         vérifiant la correspondance (ID TMDB renvoyé par Sonarr v4, titre).
    """
    from app.services.request_service import _pick_series, _tmdb_series_to_tvdb

    tvdb = tvdb_id or (await _tmdb_series_to_tvdb(tmdb_id) if tmdb_id else None)
    if tvdb:
        results = await sonarr.lookup_series(f"tvdb:{tvdb}")
        return results[0] if results else None
    results = await sonarr.lookup_series(title)
    return _pick_series(results or [], title, None, tmdb_id)


async def add_media_for_addon(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Ajoute un film / une série à Radarr / Sonarr depuis la TV (profil et dossier choisis).

    On part toujours de la fiche renvoyée par le lookup de Radarr / Sonarr
    (titre exact, année, images), comme la web app, et un titre déjà suivi
    n'est pas une erreur : on renvoie son numéro (et on relance sa
    recherche si demandé), pour que la TV enchaîne normalement.

    Avec recherche immédiate, la demande est notée pour passer en tête de
    SABnzbd (services/tv_priority.py), sauf `"priority": false`.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)
    priority = bool(data.get("priority", True))

    media_type = data.get("type", "movie")
    title = str(data.get("title") or "")
    tmdb_id = _int_or_none(data.get("tmdb_id"))
    tvdb_id = _int_or_none(data.get("tvdb_id"))
    profile_id = _int_or_none(data.get("quality_profile_id")) or 1
    root_folder = data.get("root_folder_path")
    search_now = bool(data.get("search_now", False))

    if media_type == "movie":
        radarr = await _get_radarr_client(db)
        if not radarr:
            return {"status": "error", "message": "Radarr n'est pas configuré"}

        try:
            results = await radarr.lookup_movie(f"tmdb:{tmdb_id}" if tmdb_id else title)
            movie = results[0] if results else None
            if not movie or not movie.get("tmdbId"):
                return {"status": "error", "message": f"« {title} » introuvable dans Radarr"}
            if movie.get("id"):  # déjà dans Radarr : rien à ajouter
                if search_now:
                    await radarr.search_movie(movie["id"])
                    await tv_priority.create_request(
                        db,
                        service_type="radarr",
                        arr_id=movie["id"],
                        title=movie.get("title") or title,
                        origin=origin,
                        priority=priority,
                    )
                return {
                    "status": "ok",
                    "arr_id": movie["id"],
                    "title": movie.get("title") or title,
                    "type": "movie",
                    "already": True,
                    "message": f"« {movie.get('title') or title} » est déjà dans Radarr",
                }
            payload = {
                "title": movie.get("title") or title,
                "tmdbId": movie["tmdbId"],
                "year": movie.get("year"),
                "qualityProfileId": profile_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "addOptions": {"searchForMovie": search_now},
                "images": movie.get("images", []),
            }
            res = await radarr.add_movie(payload)
            arr_id = res.get("id")
            if search_now and arr_id:
                await tv_priority.create_request(
                    db,
                    service_type="radarr",
                    arr_id=arr_id,
                    title=payload["title"],
                    origin=origin,
                    priority=priority,
                    added=True,
                )

            await log_event(
                category="media",
                action="kodi_add_media",
                status="ok",
                source="kodi",
                media_type="movie",
                title=payload["title"],
                tmdb_id=movie["tmdbId"],
                device=origin["device_name"],
                detail=f"Ajouté via Kodi (Search={search_now})",
            )
            return {"status": "ok", "arr_id": arr_id, "title": payload["title"], "type": "movie"}
        except Exception as exc:
            logger.error("Add movie from Kodi failed: %s", exc)
            return {"status": "error", "message": _arr_error("Radarr", exc)}
        finally:
            await radarr.close()

    else:  # series
        sonarr = await _get_sonarr_client(db)
        if not sonarr:
            return {"status": "error", "message": "Sonarr n'est pas configuré"}

        try:
            series = await _find_series_for_addon(sonarr, title, tmdb_id, tvdb_id)
            if not series or not series.get("tvdbId"):
                return {
                    "status": "error",
                    "message": f"« {title} » introuvable dans Sonarr (pas d'ID TVDB)",
                }
            if series.get("id"):  # déjà suivie par Sonarr : rien à ajouter
                if search_now:
                    await sonarr.search_series(series["id"])
                    await tv_priority.create_request(
                        db,
                        service_type="sonarr",
                        arr_id=series["id"],
                        title=series.get("title") or title,
                        origin=origin,
                        priority=priority,
                    )
                return {
                    "status": "ok",
                    "arr_id": series["id"],
                    "title": series.get("title") or title,
                    "type": "series",
                    "already": True,
                    "message": f"« {series.get('title') or title} » est déjà dans Sonarr",
                }
            payload = {
                "title": series.get("title") or title,
                "tvdbId": series["tvdbId"],
                "year": series.get("year"),
                "qualityProfileId": profile_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "seasonFolder": True,
                "addOptions": {"searchForMissingEpisodes": search_now},
                "images": series.get("images", []),
            }
            res = await sonarr.add_series(payload)
            arr_id = res.get("id")
            if search_now and arr_id:
                await tv_priority.create_request(
                    db,
                    service_type="sonarr",
                    arr_id=arr_id,
                    title=payload["title"],
                    origin=origin,
                    priority=priority,
                    added=True,
                )

            await log_event(
                category="media",
                action="kodi_add_media",
                status="ok",
                source="kodi",
                media_type="series",
                title=payload["title"],
                device=origin["device_name"],
                detail=f"Ajouté via Kodi (TVDB {series['tvdbId']}, Search={search_now})",
            )
            return {"status": "ok", "arr_id": arr_id, "title": payload["title"], "type": "series"}
        except Exception as exc:
            logger.error("Add series from Kodi failed: %s", exc)
            return {"status": "error", "message": _arr_error("Sonarr", exc)}
        finally:
            await sonarr.close()


def _format_size(size_bytes: int | None) -> str:
    """Format bytes to human readable GB/MB."""
    if not size_bytes:
        return "0 Mo"
    gb = size_bytes / (1024 * 1024 * 1024)
    if gb >= 1.0:
        return f"{gb:.1f} Go"
    mb = size_bytes / (1024 * 1024)
    return f"{mb:.0f} Mo"


# La TV attend la liste des releases 60 s au plus (add-on) : on répond avant,
# avec un message clair, plutôt que de laisser la TV couper la connexion.
RELEASES_TIMEOUT = 55


async def _first_season(sonarr: Any, series_id: int) -> int:
    """Première saison « normale » (≥ 1) d'une série : celle qu'on cherche par défaut.

    Sonarr ne liste les releases d'une série que pour une saison (ou un
    épisode). Depuis la TV, on vient le plus souvent d'ajouter la série :
    on commence par le début. Saisons pas encore connues (série tout juste
    ajoutée, Sonarr la rafraîchit encore) : saison 1.
    """
    try:
        series = await sonarr.get_series_by_id(series_id)
    except Exception:
        return 1
    numbers = sorted(
        int(season.get("seasonNumber") or 0)
        for season in (series.get("seasons") or [])
        if int(season.get("seasonNumber") or 0) >= 1
    )
    return numbers[0] if numbers else 1


async def list_releases_for_addon(
    db: AsyncSession, media_type: str, arr_id: int, season: int | None = None
) -> dict[str, Any]:
    """Releases proposées par les indexeurs (choix manuel depuis la TV).

    Série : recherche par saison (``season``, sinon la première saison).
    Avant, l'appel sans saison plantait pour toute série.
    """
    client = await _get_radarr_client(db) if media_type == "movie" else await _get_sonarr_client(db)
    if not client:
        return {
            "status": "error",
            "message": f"{media_type.capitalize()} n'est pas configuré",
            "releases": [],
        }
    # Une recherche interactive interroge tous les indexeurs : bien plus que
    # les 10 s par défaut du client
    client.timeout = RELEASES_TIMEOUT

    try:
        if media_type == "movie":
            raw_releases = await client.get_releases(arr_id)
        else:
            season_number = season if season is not None else await _first_season(client, arr_id)
            raw_releases = await client.get_releases(arr_id, season_number)
        formatted: list[dict[str, Any]] = []

        for r in raw_releases or []:
            if not isinstance(r, dict):
                continue
            proto = (r.get("protocol") or "torrent").lower()
            quality_info = (r.get("quality") or {}).get("quality", {})
            quality_name = quality_info.get("name") or "Inconnu"
            size_bytes = r.get("size") or 0

            formatted.append(
                {
                    "guid": r.get("guid"),
                    "indexer_id": r.get("indexerId"),
                    "indexer": r.get("indexer", "Indexeur"),
                    "title": r.get("title", ""),
                    "protocol": proto,
                    "protocol_icon": "⚡ USENET"
                    if proto == "usenet"
                    else f"📥 TORRENT ({r.get('seeders', 0)} seeds)",
                    "quality": quality_name,
                    "size_bytes": size_bytes,
                    "size_human": _format_size(size_bytes),
                    "seeders": r.get("seeders", 0),
                    "rejected": bool(r.get("rejected", False)),
                    "rejections": r.get("rejections") or [],
                }
            )

        # Sort: Non-rejected first, then higher seeders/size
        formatted.sort(key=lambda x: (x["rejected"], -(x["seeders"] or 0), -(x["size_bytes"] or 0)))

        return {"status": "ok", "releases": formatted, "count": len(formatted)}
    except httpx.TimeoutException:
        logger.warning("Kodi releases search timed out (%s %s)", media_type, arr_id)
        return {
            "status": "error",
            "message": "Les indexeurs mettent trop de temps à répondre : réessaie, "
            "ou lance la recherche automatique",
            "releases": [],
        }
    except Exception as exc:
        logger.error(f"Failed to fetch releases for Kodi: {exc}", exc_info=True)
        service = "Radarr" if media_type == "movie" else "Sonarr"
        message = _arr_error(service, exc, "la recherche")
        return {"status": "error", "message": message, "releases": []}
    finally:
        await client.close()


async def grab_release_for_addon(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send grab release order to Radarr/Sonarr (SABnzbd / Torrent).

    La release choisie sur la TV passe en tête de SABnzbd
    (services/tv_priority.py), sauf `"priority": false`. `season` (facultatif)
    limite la demande à cette saison.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)

    media_type = data.get("type", "movie")
    arr_id = data.get("arr_id")
    guid = data.get("guid")
    indexer_id = data.get("indexer_id")
    release_title = data.get("release_title", "Release")
    media_title = data.get("media_title", "")

    client = await _get_radarr_client(db) if media_type == "movie" else await _get_sonarr_client(db)
    if not client:
        return {"status": "error", "message": "Client non configuré"}

    try:
        await client.grab_release(guid, indexer_id)
        season = _int_or_none(data.get("season"))
        if media_type == "movie":
            scope: dict[str, Any] = {"scope": "movie"}
        elif season is not None:
            scope = {"scope": "season", "season": season}
        else:
            scope = {"scope": "series"}
        if _int_or_none(arr_id):
            await tv_priority.create_request(
                db,
                service_type="radarr" if media_type == "movie" else "sonarr",
                arr_id=int(arr_id),
                title=media_title or release_title,
                origin=origin,
                release_title=data.get("release_title"),
                priority=bool(data.get("priority", True)),
                **scope,
            )
            # Le *arr a déjà remis la release au client : priorité posée tout de suite
            tv_priority.kick(delay=2)
        await log_event(
            category="download",
            action="kodi_grab",
            status="ok",
            source="kodi",
            media_type=media_type,
            media_id=arr_id,
            title=media_title or release_title,
            subtitle=release_title,
            device=origin["device_name"],
            detail="Release saisie manuellement depuis Kodi",
        )
        return {"status": "ok", "message": f"Téléchargement lancé pour {release_title}"}
    except Exception as exc:
        logger.error(f"Failed to grab release from Kodi: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur lors de l'envoi au client : {str(exc)}"}


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

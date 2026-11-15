"""Kodi : lecture d'un film, statut vu / reprise, « en cours de lecture » et télécommande."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kodi.rpc import _auth_of, _pick, _rpc
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


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

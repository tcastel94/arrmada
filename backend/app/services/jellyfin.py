"""Jellyfin integration.

Three concerns live here:
  • ``JellyfinClient`` — the health-check client (used by the service registry).
  • Cast helpers — resolve a movie or an episode and build a Cast-friendly
    transcoded stream URL, so Chromecast devices can play the heavy 2160p Dolby
    Vision remuxes (which they can't decode) via Jellyfin's on-the-fly transcoding.
  • Marqueurs d'épisode (« media segments », Jellyfin 10.10+) : intro, récap et
    générique de fin, calculés par un plugin (Intro Skipper, Chapter Segments
    Provider…). La TV s'en sert pour « Passer l'intro » quand le fichier n'a
    pas de chapitres nommés, et pour ouvrir « Épisode suivant » au générique.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.arr_client import ArrBaseClient, HealthStatus
from app.services.encryption import decrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)


class JellyfinClient(ArrBaseClient):
    """Client for the Jellyfin API.

    Jellyfin uses token-based auth: ``Authorization: MediaBrowser Token="…"``
    (see ``auth_header``). The older ``X-Emby-Token`` header is refused by
    Jellyfin 12 unless legacy authorization is re-enabled.
    """

    API_PREFIX: str = ""

    @property
    def client(self):
        """Lazy-create httpx client with Jellyfin auth."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=auth_header(self.api_key),
                timeout=self.timeout,
            )
        return self._client

    # ── Health Check ──────────────────────────────────────────
    async def health_check(self) -> HealthStatus:
        """Check Jellyfin health via system/info endpoint."""
        start = time.monotonic()
        try:
            resp = await self.client.get("/System/Info")
            resp.raise_for_status()
            data = resp.json()
            elapsed_ms = int((time.monotonic() - start) * 1000)
            version = data.get("Version", None)
            return HealthStatus(status="online", latency_ms=elapsed_ms, version=version)
        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="offline", latency_ms=elapsed_ms, error="Timeout")
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="offline", latency_ms=elapsed_ms, error=str(exc))

    # ── Items (Library) ───────────────────────────────────────
    async def get_items(self, item_type: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Fetch library items."""
        params: dict[str, Any] = {
            "Recursive": "true",
            "Limit": limit,
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
        }
        if item_type:
            params["IncludeItemTypes"] = item_type
        resp = await self.client.get("/Items", params=params)
        resp.raise_for_status()
        return resp.json()

    async def search_items(self, search_term: str, limit: int = 20) -> dict[str, Any]:
        """Search library items."""
        resp = await self.client.get(
            "/Items",
            params={
                "searchTerm": search_term,
                "Recursive": "true",
                "Limit": limit,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── Libraries ─────────────────────────────────────────────
    async def get_libraries(self) -> dict[str, Any]:
        """Fetch media libraries/folders."""
        resp = await self.client.get("/Library/VirtualFolders")
        resp.raise_for_status()
        return resp.json()


# ── Authentification ──────────────────────────────────────────

# Jellyfin 12 désactive par défaut l'« authentification historique » :
# le paramètre ``api_key=`` et l'en-tête ``X-Emby-Token`` sont refusés (401).
# On utilise ce que toutes les versions depuis 10.10 acceptent : le paramètre
# ``ApiKey=`` (adresses données au Chromecast, qui ne sait pas envoyer d'en-tête)
# et l'en-tête standard ``Authorization: MediaBrowser Token="…"``.
KEY_PARAM = "ApiKey"


def auth_header(key: str) -> dict[str, str]:
    return {"Authorization": f'MediaBrowser Token="{key}"'}


# ── Cast helpers ───────────────────────────────────────────────


def _base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if u and not u.startswith("http"):
        u = f"http://{u}"
    p = urlsplit(u)
    return f"{p.scheme}://{p.netloc}"


async def get_config(db: AsyncSession) -> tuple[str, str] | None:
    """Return (base_url, api_key) for the enabled Jellyfin service, or None."""
    res = await db.execute(
        select(Service).where(Service.type == "jellyfin", Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if not svc:
        return None
    return _base(svc.url), decrypt_api_key(svc.api_key)


# Index {TMDB → film Jellyfin}, par serveur, gardé 10 min (comme celui des
# séries) : la liste complète des films n'est relue qu'une fois, pas à chaque
# fiche ouverte sur la TV.
MOVIES_TTL = 600.0
_movie_cache: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}


async def _movie_index(base: str, key: str, refresh: bool = False) -> dict[str, dict[str, Any]]:
    cached = _movie_cache.get(base)
    if cached and not refresh and time.monotonic() - cached[0] < MOVIES_TTL:
        return cached[1]
    # Jellyfin's AnyProviderIdEquals filter is unreliable, so we fetch the movie
    # list with provider ids and match client-side. Libraries are a few thousand
    # items at most — one call, then cached.
    params = {
        KEY_PARAM: key,
        "recursive": "true",
        "includeItemTypes": "Movie",
        "hasTmdbId": "true",
        "fields": "ProviderIds",
        "limit": 10000,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{base}/Items?{urlencode(params)}")
        r.raise_for_status()
        items = r.json().get("Items", [])
    index = {
        _provider(it, "Tmdb"): {
            "id": it["Id"],
            "name": it.get("Name"),
            "year": it.get("ProductionYear"),
        }
        for it in items
        if _provider(it, "Tmdb") and it.get("Id")
    }
    _movie_cache[base] = (time.monotonic(), index)
    return index


async def find_movie_item(db: AsyncSession, tmdb_id: int) -> dict[str, Any] | None:
    """Find the Jellyfin movie whose TMDB provider id matches, else None."""
    cfg = await get_config(db)
    if not cfg:
        return None
    base, key = cfg
    index = await _movie_index(base, key)
    item = index.get(str(tmdb_id))
    if item is None and base in _movie_cache:
        # Film ajouté depuis la dernière lecture de l'index : on le relit une fois
        item = (await _movie_index(base, key, refresh=True)).get(str(tmdb_id))
    return item


def stream_url(
    base: str, key: str, item_id: str, *, max_width: int = 1920, bitrate: int = 8_000_000
) -> str:
    """Build a progressive MP4 URL Jellyfin transcodes to Chromecast-friendly H.264/AAC.

    We deliberately use a progressive (single-file) MP4 stream rather than HLS.
    Chromecast's Default Media Receiver rejects adaptive (HLS/DASH) streams that
    lack CORS headers, and Jellyfin's transcode endpoints don't emit
    Access-Control-Allow-Origin — so an HLS ``master.m3u8`` loads and then fails
    immediately with ``idle_reason=ERROR`` (playback never starts). A progressive
    ``video/mp4`` stream is a plain single media file that needs no CORS, so the
    receiver plays it reliably.
    """
    params = {
        KEY_PARAM: key,
        "VideoCodec": "h264",
        "AudioCodec": "aac",
        "AudioChannels": 2,
        "MaxAudioChannels": 2,
        "VideoBitrate": bitrate,
        "AudioBitrate": 192_000,
        "MaxWidth": max_width,
        "Container": "mp4",
        "TranscodingContainer": "mp4",
        "h264-profile": "high",
        "h264-level": "41",
        "deviceId": "arrmada-cast",
        "PlaySessionId": f"arrmada-{item_id}",
    }
    return f"{base}/Videos/{item_id}/stream.mp4?{urlencode(params)}"


async def build_movie_stream(db: AsyncSession, tmdb_id: int) -> dict[str, Any] | None:
    """Resolve a movie by TMDB and return {url, title, item_id} ready to cast."""
    cfg = await get_config(db)
    if not cfg:
        return None
    base, key = cfg
    item = await find_movie_item(db, tmdb_id)
    if not item:
        return None
    return {
        "url": stream_url(base, key, item["id"]),
        "content_type": "video/mp4",
        "title": item.get("name"),
        "item_id": item["id"],
    }


async def test_connection(db: AsyncSession) -> dict[str, Any]:
    """Ping Jellyfin, read server info and what can provide episode markers."""
    cfg = await get_config(db)
    if not cfg:
        return {"ok": False, "detail": "Jellyfin non configuré"}
    base, key = cfg
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{base}/System/Info?{KEY_PARAM}={key}")
            r.raise_for_status()
            info = r.json()
            plugins: list[dict[str, Any]] | None = None
            try:  # liste des plugins : clé d'API administrateur (cas normal)
                rp = await client.get(f"{base}/Plugins?{KEY_PARAM}={key}")
                rp.raise_for_status()
                plugins = rp.json() if isinstance(rp.json(), list) else None
            except Exception:
                plugins = None
        return {
            "ok": True,
            "server": info.get("ServerName"),
            "version": info.get("Version"),
            "segments": segments_support(info.get("Version"), plugins),
        }
    except Exception as exc:
        return {"ok": False, "detail": type(exc).__name__}


# ── Épisodes : retrouver l'épisode Jellyfin (TVDB + saison + épisode) ─────────

# Index {TVDB → id Jellyfin} des séries, par serveur, gardé 10 min : une seule
# grosse requête au premier épisode lancé, puis rien (comme un cache ARP).
SERIES_TTL = 600.0
_series_cache: dict[str, tuple[float, dict[str, str]]] = {}


def _provider(item: dict[str, Any], name: str) -> str:
    """Identifiant d'un fournisseur (« Tvdb », « Tmdb »), casse ignorée."""
    ids = {str(k).lower(): v for k, v in (item.get("ProviderIds") or {}).items()}
    value = ids.get(name.lower())
    return str(value) if value not in (None, "") else ""


async def _series_index(
    client: httpx.AsyncClient, base: str, key: str, refresh: bool = False
) -> dict[str, str]:
    cached = _series_cache.get(base)
    if cached and not refresh and time.monotonic() - cached[0] < SERIES_TTL:
        return cached[1]
    params = {
        KEY_PARAM: key,
        "recursive": "true",
        "includeItemTypes": "Series",
        "fields": "ProviderIds",
        "limit": 10000,
    }
    r = await client.get(f"{base}/Items?{urlencode(params)}")
    r.raise_for_status()
    index = {
        _provider(it, "Tvdb"): it["Id"]
        for it in r.json().get("Items", [])
        if _provider(it, "Tvdb") and it.get("Id")
    }
    _series_cache[base] = (time.monotonic(), index)
    return index


def pick_episode(items: list[dict[str, Any]], season: int, episode: int) -> dict[str, Any] | None:
    """L'épisode demandé parmi ceux d'une saison (fichier double « E01-E02 » compris)."""
    for it in items:
        if it.get("ParentIndexNumber") != season or not isinstance(it.get("IndexNumber"), int):
            continue
        last = it.get("IndexNumberEnd") if isinstance(it.get("IndexNumberEnd"), int) else None
        if it["IndexNumber"] == episode or (last and it["IndexNumber"] <= episode <= last):
            return it
    return None


async def find_episode_item(
    db: AsyncSession, tvdb_id: int, season: int, episode: int
) -> dict[str, Any] | None:
    """Épisode Jellyfin d'une série (TVDB) : {id, name, series} ou None."""
    cfg = await get_config(db)
    if not cfg:
        return None
    base, key = cfg
    async with httpx.AsyncClient(timeout=20) as client:
        index = await _series_index(client, base, key)
        series_id = index.get(str(tvdb_id))
        if series_id is None and base in _series_cache:
            # Série ajoutée depuis la dernière lecture de l'index : on le relit une fois
            index = await _series_index(client, base, key, refresh=True)
            series_id = index.get(str(tvdb_id))
        if series_id is None:
            return None
        r = await client.get(
            f"{base}/Shows/{series_id}/Episodes?{urlencode({KEY_PARAM: key, 'season': season})}"
        )
        r.raise_for_status()
        item = pick_episode(r.json().get("Items", []), season, episode)
    if item is None:
        return None
    return {"id": item["Id"], "name": item.get("Name"), "series": item.get("SeriesName")}


async def build_episode_stream(
    db: AsyncSession, tvdb_id: int, season: int, episode: int
) -> dict[str, Any] | None:
    """Comme build_movie_stream, pour un épisode (TVDB de la série + numéros)."""
    cfg = await get_config(db)
    if not cfg:
        return None
    base, key = cfg
    item = await find_episode_item(db, tvdb_id, season, episode)
    if not item:
        return None
    code = f"S{season:02d}E{episode:02d}"
    title = " · ".join(p for p in (item.get("series"), code, item.get("name")) if p)
    return {
        "url": stream_url(base, key, item["id"]),
        "content_type": "video/mp4",
        "title": title,
        "item_id": item["id"],
    }


# ── Marqueurs d'épisode (media segments, Jellyfin 10.10+) ────────────────────

TICKS_PER_SECOND = 10_000_000  # Jellyfin compte en « ticks » de 100 ns
# Type Jellyfin → sorte connue de la TV (Preview / Commercial : ignorés)
SEGMENT_KINDS = {"Intro": "intro", "Recap": "recap", "Outro": "credits"}
# Plugins connus qui calculent des marqueurs (nom affiché par Jellyfin, en minuscules)
SEGMENT_PLUGINS = ("intro skipper", "chapter segments", "segment")


def parse_segments(items: Any) -> list[dict[str, Any]]:
    """Réponse de /MediaSegments → [{kind, start, end}] en secondes, triés."""
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        kind = SEGMENT_KINDS.get(str(it.get("Type") or ""))
        try:
            start = int(it.get("StartTicks") or 0) / TICKS_PER_SECOND
            end = int(it.get("EndTicks") or 0) / TICKS_PER_SECOND
        except (TypeError, ValueError):
            continue
        if kind and end - start >= 1:  # un marqueur de moins d'1 s ne sert à rien
            out.append({"kind": kind, "start": round(start, 2), "end": round(end, 2)})
    return sorted(out, key=lambda seg: seg["start"])


def _version(text: Any) -> tuple[int, ...]:
    parts = []
    for chunk in str(text or "").split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def segments_support(version: Any, plugins: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Ce serveur peut-il donner des marqueurs, et qui les calcule ?"""
    supported = bool(version) and _version(version) >= (10, 10)
    providers = [
        str(p.get("Name"))
        for p in plugins or []
        if isinstance(p, dict)
        and any(word in str(p.get("Name") or "").lower() for word in SEGMENT_PLUGINS)
        and str(p.get("Status") or "Active").lower() not in ("disabled", "malfunctioned")
    ]
    return {"supported": supported, "providers": providers, "checked": plugins is not None}


async def episode_segments(
    db: AsyncSession, tvdb_id: int, season: int, episode: int
) -> dict[str, Any]:
    """Intro, récap et générique de fin d'un épisode, d'après Jellyfin.

    status : « ok » (segments, éventuellement vide), « unavailable » (pas de
    Jellyfin, ou trop ancien) ou « error » (injoignable). La TV ne s'en sert
    que s'il y a des segments : tout le reste revient à « rien à proposer ».
    """
    cfg = await get_config(db)
    if not cfg:
        return {"status": "unavailable", "reason": "Jellyfin non configuré", "segments": []}
    base, key = cfg
    try:
        item = await find_episode_item(db, tvdb_id, season, episode)
        if item is None:
            return {"status": "ok", "found": False, "segments": []}
        params = [(KEY_PARAM, key)] + [("includeSegmentTypes", t) for t in SEGMENT_KINDS]
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}/MediaSegments/{item['id']}?{urlencode(params)}")
        if r.status_code == 404:
            return {
                "status": "unavailable",
                "reason": "Jellyfin antérieur à 10.10 : pas de marqueurs",
                "segments": [],
            }
        r.raise_for_status()
        segments = parse_segments(r.json().get("Items"))
    except Exception as exc:
        logger.debug("Marqueurs Jellyfin S%sE%s (TVDB %s) : %s", season, episode, tvdb_id, exc)
        return {"status": "error", "message": type(exc).__name__, "segments": []}
    return {"status": "ok", "found": True, "item_id": item["id"], "segments": segments}

"""Jellyfin integration.

Two concerns live here:
  • ``JellyfinClient`` — the health-check client (used by the service registry).
  • Cast helpers — resolve a movie and build a Cast-friendly transcoded stream
    URL, so Chromecast devices can play the heavy 2160p Dolby Vision remuxes
    (which they can't decode) via Jellyfin's on-the-fly transcoding.
"""

from __future__ import annotations

import time
from typing import Any, Optional
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

    Jellyfin uses token-based auth via the ``X-Emby-Token`` header.
    """

    API_PREFIX: str = ""

    @property
    def client(self):
        """Lazy-create httpx client with Jellyfin auth."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-Emby-Token": self.api_key},
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


# ── Cast helpers ───────────────────────────────────────────────

def _base(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if u and not u.startswith("http"):
        u = f"http://{u}"
    p = urlsplit(u)
    return f"{p.scheme}://{p.netloc}"


async def get_config(db: AsyncSession) -> Optional[tuple[str, str]]:
    """Return (base_url, api_key) for the enabled Jellyfin service, or None."""
    res = await db.execute(
        select(Service).where(Service.type == "jellyfin", Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if not svc:
        return None
    return _base(svc.url), decrypt_api_key(svc.api_key)


async def find_movie_item(db: AsyncSession, tmdb_id: int) -> Optional[dict[str, Any]]:
    """Find the Jellyfin movie whose TMDB provider id matches, else None."""
    cfg = await get_config(db)
    if not cfg:
        return None
    base, key = cfg
    # Jellyfin's AnyProviderIdEquals filter is unreliable, so we fetch the movie
    # list with provider ids and match client-side. Libraries are a few thousand
    # items at most — one call, done on-demand when casting.
    params = {
        "api_key": key,
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
    for it in items:
        if str((it.get("ProviderIds") or {}).get("Tmdb")) == str(tmdb_id):
            return {"id": it["Id"], "name": it.get("Name"), "year": it.get("ProductionYear")}
    return None


def stream_url(base: str, key: str, item_id: str, *, max_width: int = 1920, bitrate: int = 8_000_000) -> str:
    """Build an HLS master URL Jellyfin transcodes to Chromecast-friendly H.264/AAC."""
    params = {
        "api_key": key,
        "MediaSourceId": item_id,
        "VideoCodec": "h264",
        "AudioCodec": "aac",
        "AudioChannels": 2,
        "MaxAudioChannels": 2,
        "VideoBitrate": bitrate,
        "AudioBitrate": 192_000,
        "MaxWidth": max_width,
        "SegmentContainer": "ts",
        "TranscodingContainer": "ts",
        "TranscodingProtocol": "hls",
        "BreakOnNonKeyFrames": "true",
        "h264-profile": "high",
        "h264-level": "41",
        "deviceId": "arrmada-cast",
        "PlaySessionId": f"arrmada-{item_id}",
    }
    return f"{base}/Videos/{item_id}/master.m3u8?{urlencode(params)}"


async def build_movie_stream(db: AsyncSession, tmdb_id: int) -> Optional[dict[str, Any]]:
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
        "content_type": "application/x-mpegurl",
        "title": item.get("name"),
        "item_id": item["id"],
    }


async def test_connection(db: AsyncSession) -> dict[str, Any]:
    """Ping Jellyfin and read server info."""
    cfg = await get_config(db)
    if not cfg:
        return {"ok": False, "detail": "Jellyfin non configuré"}
    base, key = cfg
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(f"{base}/System/Info?api_key={key}")
            r.raise_for_status()
            info = r.json()
        return {"ok": True, "server": info.get("ServerName"), "version": info.get("Version")}
    except Exception as exc:
        return {"ok": False, "detail": type(exc).__name__}

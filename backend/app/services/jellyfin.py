"""Jellyfin API client — media server integration."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.arr_client import ArrBaseClient, HealthStatus
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

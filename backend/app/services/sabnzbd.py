"""SABnzbd API client — Usenet download management."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.arr_client import ArrBaseClient, HealthStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)


class SabnzbdClient(ArrBaseClient):
    """Client for the SABnzbd API.

    SABnzbd uses a completely different API structure (query-param based).
    """

    API_PREFIX: str = "/api"

    @property
    def client(self):
        """Lazy-create httpx client (no X-Api-Key header for SABnzbd)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def _call(self, mode: str, extra_params: dict[str, Any] | None = None) -> Any:
        """Make a SABnzbd API call using mode + apikey params."""
        params: dict[str, Any] = {
            "mode": mode,
            "apikey": self.api_key,
            "output": "json",
        }
        if extra_params:
            params.update(extra_params)
        resp = await self.client.get(self.API_PREFIX, params=params)
        resp.raise_for_status()
        return resp.json()

    # ── Health Check ──────────────────────────────────────────
    async def health_check(self) -> HealthStatus:
        """Check SABnzbd health via version endpoint."""
        start = time.monotonic()
        try:
            data = await self._call("version")
            elapsed_ms = int((time.monotonic() - start) * 1000)
            version = data.get("version") if isinstance(data, dict) else str(data)
            return HealthStatus(status="online", latency_ms=elapsed_ms, version=version)
        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="offline", latency_ms=elapsed_ms, error="Timeout")
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="offline", latency_ms=elapsed_ms, error=str(exc))

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the current download queue."""
        data = await self._call("queue")
        return data.get("queue", data)

    # ── History ───────────────────────────────────────────────
    async def get_history(self, limit: int = 30) -> dict[str, Any]:
        """Fetch download history."""
        data = await self._call("history", {"limit": limit})
        return data.get("history", data)

    # ── Status ────────────────────────────────────────────────
    async def get_status(self) -> dict[str, Any]:
        """Fetch overall SABnzbd status (speed, remaining, etc.)."""
        data = await self._call("queue")
        queue = data.get("queue", {})
        return {
            "speed": queue.get("speed", "0"),
            "size_left": queue.get("sizeleft", "0"),
            "time_left": queue.get("timeleft", "0:00:00"),
            "paused": queue.get("paused", False),
            "slots_count": len(queue.get("slots", [])),
        }

    # ── Controls ──────────────────────────────────────────────
    async def pause(self) -> Any:
        """Pause downloads."""
        return await self._call("pause")

    async def resume(self) -> Any:
        """Resume downloads."""
        return await self._call("resume")

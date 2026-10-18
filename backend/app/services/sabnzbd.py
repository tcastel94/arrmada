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

    async def get_slots(self) -> list[dict[str, Any]]:
        """Éléments de la file, dans l'ordre de SABnzbd (nzo_id, priority, index…)."""
        queue = await self.get_queue()
        slots = queue.get("slots") if isinstance(queue, dict) else None
        return [s for s in slots or [] if isinstance(s, dict) and s.get("nzo_id")]

    # ── Controls ──────────────────────────────────────────────
    async def pause(self) -> Any:
        """Pause downloads."""
        return await self._call("pause")

    async def resume(self) -> Any:
        """Resume downloads."""
        return await self._call("resume")

    # ── Un seul élément de la file (nzo_id) ───────────────────
    # Sonarr / Radarr donnent ce nzo_id comme « downloadId » d'un
    # téléchargement envoyé à SABnzbd : c'est le lien entre les deux.

    async def set_priority(self, nzo_id: str, priority: int) -> Any:
        """Priorité d'un élément : 2 Force, 1 High, 0 Normal, -1 Low.

        « Force » télécharge même quand la file est en pause.
        """
        return await self._call("queue", {"name": "priority", "value": nzo_id, "value2": priority})

    async def move_to(self, nzo_id: str, position: int) -> Any:
        """Place un élément à une position de la file (0 = en tête)."""
        return await self._call("switch", {"value": nzo_id, "value2": position})

    async def pause_item(self, nzo_id: str) -> Any:
        """Met en pause un seul élément (le reste de la file continue)."""
        return await self._call("queue", {"name": "pause", "value": nzo_id})

    async def resume_item(self, nzo_id: str) -> Any:
        """Reprend un seul élément mis en pause."""
        return await self._call("queue", {"name": "resume", "value": nzo_id})

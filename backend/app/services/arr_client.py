"""Base class for all *arr API clients."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthStatus:
    """Result of a health check."""
    status: str  # online, offline, degraded
    latency_ms: int | None = None
    version: str | None = None
    error: str | None = None


class ArrBaseClient:
    """Abstract base class for *arr service API communication.

    Provides generic HTTP methods with timeout handling, error wrapping,
    and a standard health check via ``/api/v1/system/status``.
    """

    # Subclasses can override these
    API_PREFIX: str = "/api/v1"
    STATUS_ENDPOINT: str = "/system/status"

    def __init__(self, url: str, api_key: str, *, timeout: int = 10) -> None:
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ── HTTP client lifecycle ─────────────────────────────────
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-create the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-Api-Key": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Generic HTTP ──────────────────────────────────────────
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Perform a GET request and return the JSON body."""
        url = f"{self.API_PREFIX}{endpoint}"
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def post(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """Perform a POST request and return the JSON body."""
        url = f"{self.API_PREFIX}{endpoint}"
        resp = await self.client.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    async def put(self, endpoint: str, data: dict[str, Any] | None = None) -> Any:
        """Perform a PUT request and return the JSON body."""
        url = f"{self.API_PREFIX}{endpoint}"
        resp = await self.client.put(url, json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete(self, endpoint: str) -> None:
        """Perform a DELETE request."""
        url = f"{self.API_PREFIX}{endpoint}"
        resp = await self.client.delete(url)
        resp.raise_for_status()

    # ── Health check ──────────────────────────────────────────
    async def health_check(self) -> HealthStatus:
        """Check service health via the system/status endpoint.

        Timeouts:
        - Response within timeout      → online
        - Response but slow (>5s)       → degraded
        - No response / error           → offline
        """
        start = time.monotonic()
        try:
            data = await self.get(self.STATUS_ENDPOINT)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            version = data.get("version") if isinstance(data, dict) else None

            if elapsed_ms > 5000:
                return HealthStatus(
                    status="degraded",
                    latency_ms=elapsed_ms,
                    version=version,
                    error="Slow response",
                )

            return HealthStatus(
                status="online",
                latency_ms=elapsed_ms,
                version=version,
            )

        except httpx.TimeoutException:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(
                status="offline",
                latency_ms=elapsed_ms,
                error="Connection timed out",
            )

        except httpx.HTTPStatusError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return HealthStatus(
                status="degraded",
                latency_ms=elapsed_ms,
                error=f"HTTP {exc.response.status_code}",
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.warning("Health check failed for %s: %s", self.base_url, exc)
            return HealthStatus(
                status="offline",
                latency_ms=elapsed_ms,
                error=str(exc),
            )

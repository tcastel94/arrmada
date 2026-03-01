"""Bazarr API client — subtitle management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class BazarrClient(ArrBaseClient):
    """Client for the Bazarr API.

    Bazarr has a different API structure than the other *arr services.
    Uses /api/ prefix and the API key is passed via the ``apikey`` query param
    or ``X-API-KEY`` header.
    """

    API_PREFIX: str = "/api"
    STATUS_ENDPOINT: str = "/system/status"

    # Override to use Bazarr-specific auth header
    @property
    def client(self):
        """Lazy-create httpx client with Bazarr auth headers."""
        import httpx

        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-API-KEY": self.api_key},
                timeout=self.timeout,
            )
        return self._client

    # ── Series Subtitles ──────────────────────────────────────
    async def get_series(self) -> dict[str, Any]:
        """Fetch all series with subtitle info."""
        return await self.get("/series")

    async def get_episodes(self, series_id: int) -> dict[str, Any]:
        """Fetch episodes for a series."""
        return await self.get("/episodes", params={"seriesid[]": series_id})

    # ── Movie Subtitles ───────────────────────────────────────
    async def get_movies(self) -> dict[str, Any]:
        """Fetch all movies with subtitle info."""
        return await self.get("/movies")

    # ── Languages ─────────────────────────────────────────────
    async def get_languages(self) -> list[dict[str, Any]]:
        """Fetch available languages for subtitles."""
        return await self.get("/system/languages")

    # ── Wanted ────────────────────────────────────────────────
    async def get_wanted_series(self) -> dict[str, Any]:
        """Fetch series episodes with wanted subtitles."""
        return await self.get("/episodes/wanted")

    async def get_wanted_movies(self) -> dict[str, Any]:
        """Fetch movies with wanted subtitles."""
        return await self.get("/movies/wanted")

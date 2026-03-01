"""Sonarr API client — series management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class SonarrClient(ArrBaseClient):
    """Client for the Sonarr v3 API."""

    API_PREFIX: str = "/api/v3"

    # ── Series ────────────────────────────────────────────────
    async def get_series(self) -> list[dict[str, Any]]:
        """Fetch all monitored series."""
        return await self.get("/series")

    async def get_series_by_id(self, series_id: int) -> dict[str, Any]:
        """Fetch a single series by ID."""
        return await self.get(f"/series/{series_id}")

    async def lookup_series(self, term: str) -> list[dict[str, Any]]:
        """Search for series by name."""
        return await self.get("/series/lookup", params={"term": term})

    async def add_series(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new series to Sonarr."""
        return await self.post("/series", data=data)

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders for series storage."""
        return await self.get("/rootfolder")

    # ── Calendar ──────────────────────────────────────────────
    async def get_calendar(self, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
        """Fetch upcoming episodes."""
        params: dict[str, str] = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self.get("/calendar", params=params)

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the download queue."""
        return await self.get("/queue", params={"pageSize": 50})

"""Lidarr API client — music management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class LidarrClient(ArrBaseClient):
    """Client for the Lidarr v1 API."""

    API_PREFIX: str = "/api/v1"

    # ── Artists ────────────────────────────────────────────────
    async def get_artists(self) -> list[dict[str, Any]]:
        """Fetch all artists."""
        return await self.get("/artist")

    async def lookup_artist(self, term: str) -> list[dict[str, Any]]:
        """Search for an artist."""
        return await self.get("/artist/lookup", params={"term": term})

    async def add_artist(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new artist."""
        return await self.post("/artist", data=data)

    # ── Albums ────────────────────────────────────────────────
    async def get_albums(self) -> list[dict[str, Any]]:
        """Fetch all albums."""
        return await self.get("/album")

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders."""
        return await self.get("/rootfolder")

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the download queue."""
        return await self.get("/queue", params={"pageSize": 50})

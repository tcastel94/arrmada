"""Radarr API client — movie management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class RadarrClient(ArrBaseClient):
    """Client for the Radarr v3 API."""

    API_PREFIX: str = "/api/v3"

    # ── Movies ────────────────────────────────────────────────
    async def get_movies(self) -> list[dict[str, Any]]:
        """Fetch all movies in the library."""
        return await self.get("/movie")

    async def get_movie_by_id(self, movie_id: int) -> dict[str, Any]:
        """Fetch a single movie by ID."""
        return await self.get(f"/movie/{movie_id}")

    async def lookup_movie(self, term: str) -> list[dict[str, Any]]:
        """Search for movies by name or TMDB/IMDB ID."""
        return await self.get("/movie/lookup", params={"term": term})

    async def add_movie(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new movie to Radarr."""
        return await self.post("/movie", data=data)

    async def delete_movie(self, movie_id: int, delete_files: bool = False) -> None:
        """Delete a movie from Radarr."""
        url = f"/movie/{movie_id}?deleteFiles={str(delete_files).lower()}"
        resp = await self.client.delete(f"{self.API_PREFIX}{url}")
        resp.raise_for_status()

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders for movie storage."""
        return await self.get("/rootfolder")

    # ── Queue ─────────────────────────────────────────────────
    async def get_queue(self) -> dict[str, Any]:
        """Fetch the download queue."""
        return await self.get("/queue", params={"pageSize": 50})

    # ── Disk Space ────────────────────────────────────────────
    async def get_disk_space(self) -> list[dict[str, Any]]:
        """Fetch disk space info."""
        return await self.get("/diskspace")

"""Readarr API client — book management."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class ReadarrClient(ArrBaseClient):
    """Client for the Readarr v1 API."""

    API_PREFIX: str = "/api/v1"

    # ── Authors ───────────────────────────────────────────────
    async def get_authors(self) -> list[dict[str, Any]]:
        """Fetch all authors."""
        return await self.get("/author")

    async def lookup_author(self, term: str) -> list[dict[str, Any]]:
        """Search for an author."""
        return await self.get("/author/lookup", params={"term": term})

    # ── Books ─────────────────────────────────────────────────
    async def get_books(self) -> list[dict[str, Any]]:
        """Fetch all books."""
        return await self.get("/book")

    async def lookup_book(self, term: str) -> list[dict[str, Any]]:
        """Search for a book."""
        return await self.get("/book/lookup", params={"term": term})

    async def add_book(self, data: dict[str, Any]) -> dict[str, Any]:
        """Add a new book."""
        return await self.post("/book", data=data)

    # ── Quality Profiles ──────────────────────────────────────
    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Fetch available quality profiles."""
        return await self.get("/qualityprofile")

    # ── Root Folders ──────────────────────────────────────────
    async def get_root_folders(self) -> list[dict[str, Any]]:
        """Fetch root folders."""
        return await self.get("/rootfolder")

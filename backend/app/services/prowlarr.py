"""Prowlarr API client — indexer management and search."""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient


class ProwlarrClient(ArrBaseClient):
    """Client for the Prowlarr v1 API."""

    API_PREFIX: str = "/api/v1"

    # ── Search ────────────────────────────────────────────────
    async def search(self, query: str, indexer_ids: list[int] | None = None, categories: list[int] | None = None) -> list[dict[str, Any]]:
        """Search across all configured indexers."""
        params: dict[str, Any] = {"query": query}
        if indexer_ids:
            params["indexerIds"] = ",".join(str(i) for i in indexer_ids)
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)
        return await self.get("/search", params=params)

    # ── Indexers ──────────────────────────────────────────────
    async def get_indexers(self) -> list[dict[str, Any]]:
        """Fetch all configured indexers."""
        return await self.get("/indexer")

    async def get_indexer_stats(self) -> dict[str, Any]:
        """Fetch indexer statistics."""
        return await self.get("/indexerstats")

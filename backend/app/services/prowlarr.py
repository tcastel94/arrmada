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

    async def get_indexer(self, indexer_id: int) -> dict[str, Any]:
        """Fetch a single indexer definition by ID."""
        return await self.get(f"/indexer/{indexer_id}")

    async def get_indexer_stats(self) -> dict[str, Any]:
        """Fetch indexer statistics."""
        return await self.get("/indexerstats")

    # ── Indexer management ────────────────────────────────────
    async def test_indexer(self, indexer_id: int) -> dict[str, Any]:
        """Test an existing indexer's connectivity/credentials.

        Prowlarr's ``POST /indexer/test`` expects the full indexer body.
        On success it returns 200/201 (often with an empty body); on
        failure it returns HTTP 400 with validation messages.
        """
        indexer = await self.get_indexer(indexer_id)
        url = f"{self.API_PREFIX}/indexer/test"
        resp = await self.client.post(url, json=indexer)
        if resp.status_code >= 400:
            errors: Any
            try:
                errors = resp.json()
            except Exception:
                errors = resp.text
            return {"ok": False, "status_code": resp.status_code, "errors": errors}
        return {"ok": True, "status_code": resp.status_code}

    async def toggle_indexer(self, indexer_id: int, enable: bool) -> dict[str, Any]:
        """Enable or disable an indexer via PUT /indexer/{id}."""
        indexer = await self.get_indexer(indexer_id)
        indexer["enable"] = enable
        return await self.put(f"/indexer/{indexer_id}", data=indexer)

    async def delete_indexer(self, indexer_id: int) -> None:
        """Delete an indexer via DELETE /indexer/{id}."""
        url = f"{self.API_PREFIX}/indexer/{indexer_id}"
        resp = await self.client.delete(url)
        resp.raise_for_status()

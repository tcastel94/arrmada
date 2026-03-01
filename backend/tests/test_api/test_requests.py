"""Tests for the requests API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestRequestsEndpoints:
    """Test media request (Overseerr-like) endpoints."""

    async def test_list_requests_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/requests")
        assert resp.status_code == 401

    async def test_list_requests_empty(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/requests", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    async def test_create_request(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/requests",
            json={
                "title": "Test Movie Request",
                "type": "movie",
                "tmdb_id": 12345,
                "year": 2024,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Movie Request"
        assert data["status"] in ("pending", "searching")

    async def test_create_and_delete_request(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        # Create
        create_resp = await client.post(
            "/api/requests",
            json={"title": "To Delete", "type": "series"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        # Delete
        del_resp = await client.delete(
            f"/api/requests/{req_id}", headers=auth_headers
        )
        assert del_resp.status_code == 204

    async def test_delete_nonexistent_request(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.delete("/api/requests/9999", headers=auth_headers)
        assert resp.status_code == 404


class TestSearchEndpoints:
    """Test unified search endpoints."""

    async def test_search_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/search?q=test")
        assert resp.status_code == 401

    async def test_search_requires_min_length(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/search?q=a", headers=auth_headers)
        assert resp.status_code == 422  # validation error

    async def test_search_returns_structure(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/search?q=test", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "library" in data
        assert "indexers" in data
        assert data["query"] == "test"

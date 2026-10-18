"""Tests for the requests API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestRequestsEndpoints:
    """Test media request (Overseerr-like) endpoints."""

    async def test_list_requests_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/requests")
        assert resp.status_code == 401

    async def test_list_requests_empty(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/requests", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    async def test_create_request(self, client: AsyncClient, auth_headers: dict) -> None:
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
        # Aucun Radarr configuré en base de test : la demande est bien
        # enregistrée (201) mais marquée « failed » faute de cible.
        assert data["status"] == "failed"

    async def test_create_and_delete_request(self, client: AsyncClient, auth_headers: dict) -> None:
        # Create
        create_resp = await client.post(
            "/api/requests",
            json={"title": "To Delete", "type": "series"},
            headers=auth_headers,
        )
        assert create_resp.status_code == 201
        req_id = create_resp.json()["id"]

        # Delete
        del_resp = await client.delete(f"/api/requests/{req_id}", headers=auth_headers)
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

    async def test_search_returns_structure(self, client: AsyncClient, auth_headers: dict) -> None:
        resp = await client.get("/api/search?q=test", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "query" in data
        assert "library" in data
        assert "indexers" in data
        assert data["query"] == "test"


class TestRequestsWithArr:
    """Demandes envoyées à un faux Radarr / Sonarr (cf. tests/fake_arr.py)."""

    async def _create(self, client: AsyncClient, headers: dict, **payload) -> dict:
        resp = await client.post("/api/requests", json=payload, headers=headers)
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_new_movie_is_added_and_searched(self, client: AsyncClient, arr_stack: dict):
        data = await self._create(
            client, arr_stack, title="Interstellar", type="movie", tmdb_id=157336, year=2014
        )
        assert data["status"] == "searching"
        assert data["arr_id"] == 999  # id renvoyé par le faux Radarr

    async def test_movie_already_on_disk_is_available(self, client: AsyncClient, arr_stack: dict):
        data = await self._create(client, arr_stack, title="Dune", type="movie", tmdb_id=438631)
        assert data["status"] == "available"
        assert data["arr_id"] == 1

    async def test_new_series_by_tvdb(self, client: AsyncClient, arr_stack: dict):
        data = await self._create(
            client, arr_stack, title="Severance", type="series", tvdb_id=371980
        )
        assert data["status"] == "searching"

    async def test_existing_series(self, client: AsyncClient, arr_stack: dict):
        data = await self._create(
            client, arr_stack, title="The Expanse", type="series", tvdb_id=280619
        )
        assert data["status"] in ("available", "searching")

    async def test_lookup(self, client: AsyncClient, arr_stack: dict):
        resp = await client.get(
            "/api/requests/lookup", params={"q": "interstellar", "type": "movie"}, headers=arr_stack
        )
        assert resp.status_code == 200, resp.text

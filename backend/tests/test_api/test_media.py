"""Tests for the media API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestMediaEndpoints:
    """Test media library endpoints."""

    async def test_list_media_requires_auth(self, client: AsyncClient) -> None:
        """Media endpoint should require authentication."""
        resp = await client.get("/api/media")
        assert resp.status_code == 401

    async def test_list_media_empty(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """With no services, media list should return empty or error."""
        resp = await client.get("/api/media", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["total"] >= 0

    async def test_list_media_with_filters(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Test media list with type filter."""
        resp = await client.get(
            "/api/media?type=movie&page=1&per_page=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["pagination"]["per_page"] == 10

    async def test_list_media_with_search(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Test media list with search query."""
        resp = await client.get(
            "/api/media?search=test&sort=title&order=asc",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_search_media_requires_auth(self, client: AsyncClient) -> None:
        """Media search should require auth."""
        resp = await client.get("/api/media/search?q=test")
        assert resp.status_code == 401


class TestDownloadsEndpoints:
    """Test download queue endpoints."""

    async def test_downloads_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/downloads")
        assert resp.status_code == 401

    async def test_downloads_empty(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """With no services, downloads should return empty."""
        resp = await client.get("/api/downloads", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] >= 0


class TestAnalyticsEndpoints:
    """Test analytics endpoints."""

    async def test_analytics_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/analytics")
        assert resp.status_code == 401

    async def test_analytics_returns_data(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/analytics", headers=auth_headers)
        assert resp.status_code == 200


class TestDuplicatesEndpoints:
    """Test duplicate detection endpoints."""

    async def test_duplicates_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/duplicates")
        assert resp.status_code == 401

    async def test_duplicates_empty(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/duplicates", headers=auth_headers)
        assert resp.status_code == 200


class TestRecommendationsEndpoints:
    """Test recommendation endpoints."""

    async def test_recommendations_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/api/recommendations")
        assert resp.status_code == 401

    async def test_recommendations_empty(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/recommendations", headers=auth_headers)
        assert resp.status_code == 200

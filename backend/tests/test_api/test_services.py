"""Tests for the services API endpoints."""

from __future__ import annotations

from httpx import AsyncClient


class TestHealth:
    """Test the public health endpoint."""

    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestAuth:
    """Test authentication endpoints."""

    async def test_login_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"password": "changeme_use_a_strong_password"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/auth/login",
            json={"password": "wrong_password"},
        )
        assert resp.status_code == 401

    async def test_protected_route_no_token(self, client: AsyncClient) -> None:
        resp = await client.get("/api/services")
        assert resp.status_code == 401


class TestServicesCRUD:
    """Test services CRUD operations."""

    async def test_create_service(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.post(
            "/api/services",
            json={
                "name": "Test Sonarr",
                "type": "sonarr",
                "url": "http://localhost:8989",
                "api_key": "test-api-key-123",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Sonarr"
        assert data["type"] == "sonarr"
        assert data["url"] == "http://localhost:8989"

    async def test_list_services(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        # Create two services
        for name in ["Sonarr", "Radarr"]:
            await client.post(
                "/api/services",
                json={
                    "name": name,
                    "type": name.lower(),
                    "url": "http://localhost:8989",
                    "api_key": "key",
                },
                headers=auth_headers,
            )

        resp = await client.get("/api/services", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2

    async def test_update_service(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        # Create
        create_resp = await client.post(
            "/api/services",
            json={
                "name": "Old Name",
                "type": "sonarr",
                "url": "http://localhost:8989",
                "api_key": "key",
            },
            headers=auth_headers,
        )
        service_id = create_resp.json()["id"]

        # Update
        resp = await client.put(
            f"/api/services/{service_id}",
            json={"name": "New Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_delete_service(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        # Create
        create_resp = await client.post(
            "/api/services",
            json={
                "name": "To Delete",
                "type": "sonarr",
                "url": "http://localhost:8989",
                "api_key": "key",
            },
            headers=auth_headers,
        )
        service_id = create_resp.json()["id"]

        # Delete
        resp = await client.delete(
            f"/api/services/{service_id}", headers=auth_headers
        )
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(
            f"/api/services/{service_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_get_nonexistent_service(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await client.get("/api/services/9999", headers=auth_headers)
        assert resp.status_code == 404

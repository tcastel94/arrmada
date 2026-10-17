"""Tests for the zero-config first run: password creation and change."""

from __future__ import annotations

from httpx import AsyncClient

from app.services import auth_store


class TestFirstRun:
    """An unclaimed instance must be claimable exactly once."""

    async def test_status_reports_password(self, client: AsyncClient) -> None:
        resp = await client.get("/api/setup/status")
        assert resp.status_code == 200
        assert resp.json()["password_set"] is True

        auth_store.clear_password()
        resp = await client.get("/api/setup/status")
        assert resp.json()["password_set"] is False

    async def test_login_refused_without_password(self, client: AsyncClient) -> None:
        auth_store.clear_password()
        resp = await client.post("/api/auth/login", json={"password": "changeme"})
        assert resp.status_code == 409

    async def test_create_password_once(self, client: AsyncClient) -> None:
        auth_store.clear_password()
        resp = await client.post("/api/auth/password", json={"password": "short"})
        assert resp.status_code == 422

        resp = await client.post("/api/auth/password", json={"password": "a-new-strong-pass"})
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        resp = await client.get("/api/services", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        # Second claim attempt must fail: the instance is already owned.
        resp = await client.post("/api/auth/password", json={"password": "attacker-password"})
        assert resp.status_code == 409
        assert auth_store.verify_password("a-new-strong-pass")
        assert not auth_store.verify_password("attacker-password")

    async def test_setup_complete_requires_password(self, client: AsyncClient) -> None:
        auth_store.clear_password()
        resp = await client.post(
            "/api/setup/complete",
            json={
                "services": [
                    {"name": "Sonarr", "type": "sonarr", "url": "http://x:8989", "api_key": "k"}
                ]
            },
        )
        assert resp.status_code == 428


class TestChangePassword:
    async def test_change_password(
        self, client: AsyncClient, auth_headers: dict, admin_password: str
    ) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={"current_password": "wrong", "new_password": "another-password"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

        resp = await client.put(
            "/api/auth/password",
            json={"current_password": admin_password, "new_password": "another-password"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert auth_store.verify_password("another-password")
        assert not auth_store.verify_password(admin_password)

    async def test_change_password_requires_session(self, client: AsyncClient) -> None:
        resp = await client.put(
            "/api/auth/password",
            json={"current_password": "x", "new_password": "another-password"},
        )
        assert resp.status_code == 401


class TestLegacyEnvPassword:
    async def test_placeholder_is_never_accepted(self, monkeypatch) -> None:
        auth_store.clear_password()
        monkeypatch.setattr(
            auth_store.settings, "ARRMADA_AUTH_SECRET", "changeme_use_a_strong_password"
        )
        assert auth_store.password_source() == "none"
        assert not auth_store.verify_password("changeme_use_a_strong_password")

    async def test_real_env_value_still_works(self, monkeypatch) -> None:
        auth_store.clear_password()
        monkeypatch.setattr(auth_store.settings, "ARRMADA_AUTH_SECRET", "my-old-env-pass")
        assert auth_store.password_source() == "env"
        assert auth_store.verify_password("my-old-env-pass")
        assert not auth_store.verify_password("nope")

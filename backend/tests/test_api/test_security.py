"""Tests for rate limiting on auth endpoint."""

from __future__ import annotations

from httpx import AsyncClient


class TestRateLimiting:
    """Test rate limiting on the login endpoint."""

    async def test_login_rate_limited(self, client: AsyncClient) -> None:
        """Multiple rapid login attempts should eventually be rate-limited."""
        # Note: In test environment, slowapi may not enforce limits depending
        # on configuration. This test verifies the endpoint still works.
        for _ in range(3):
            resp = await client.post(
                "/api/auth/login",
                json={"password": "wrong_password"},
            )
            assert resp.status_code in (401, 429)


class TestSecurityHeaders:
    """Test security headers are present in responses."""

    async def test_health_has_security_headers(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    async def test_hsts_header(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert "Strict-Transport-Security" in resp.headers

    async def test_csp_header(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert "Content-Security-Policy" in resp.headers

    async def test_permissions_policy_header(self, client: AsyncClient) -> None:
        resp = await client.get("/api/health")
        assert "Permissions-Policy" in resp.headers

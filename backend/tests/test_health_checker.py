"""Tests for the health checker service."""

from __future__ import annotations

from app.services.arr_client import ArrBaseClient, HealthStatus


class TestArrBaseClient:
    """Test ArrBaseClient health check behavior."""

    async def test_health_check_offline_bad_url(self) -> None:
        """A client pointing at a non-existent host should return offline."""
        client = ArrBaseClient(
            url="http://192.0.2.1:9999",  # TEST-NET, won't respond
            api_key="fake",
            timeout=2,
        )
        try:
            result = await client.health_check()
            assert result.status in ("offline", "degraded")
            assert result.error is not None
        finally:
            await client.close()

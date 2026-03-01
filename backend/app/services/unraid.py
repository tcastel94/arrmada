"""Unraid API client — server management via Unraid Connect GraphQL API."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.arr_client import HealthStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# GraphQL queries for Unraid
DOCKER_CONTAINERS_QUERY = """
{
  docker {
    containers {
      id
      names
      image
      state
      status
    }
  }
}
"""

DOCKER_START_MUTATION = """
mutation ($id: String!) {
  dockerContainerStart(id: $id)
}
"""

DOCKER_STOP_MUTATION = """
mutation ($id: String!) {
  dockerContainerStop(id: $id)
}
"""

DOCKER_RESTART_MUTATION = """
mutation ($id: String!) {
  dockerContainerRestart(id: $id)
}
"""

SHARES_QUERY = """
{
  shares {
    name
    size
    free
  }
}
"""


class UnraidClient:
    """Client for the Unraid GraphQL API (via Unraid Connect / port 15000)."""

    def __init__(self, url: str, api_key: str, username: str = "", password: str = ""):
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=15.0,
                verify=False,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                },
            )
        return self._client

    async def _graphql(self, query: str, variables: dict | None = None) -> dict[str, Any]:
        """Execute a GraphQL query against the Unraid API."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        resp = await self.client.post("/graphql", json=payload)
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            logger.error("Unraid GraphQL errors: %s", data["errors"])
            raise Exception(f"GraphQL errors: {data['errors']}")

        return data.get("data", {})

    # ── Docker Containers ─────────────────────────────────────
    async def get_docker_containers(self) -> list[dict[str, Any]]:
        """Fetch all Docker containers via GraphQL."""
        data = await self._graphql(DOCKER_CONTAINERS_QUERY)
        raw = data.get("docker", {}).get("containers", [])

        containers = []
        for c in raw:
            names = c.get("names", ["unknown"])
            name = names[0].lstrip("/") if names else "unknown"
            state_raw = (c.get("state") or "").upper()

            containers.append({
                "name": name,
                "status": "running" if state_raw == "RUNNING" else "stopped",
                "image": c.get("image", ""),
                "id": (c.get("id") or "")[:12],
                "status_text": c.get("status", ""),
                "state_raw": state_raw,
            })
        return containers

    async def docker_action(self, container_id: str, action: str) -> str:
        """Start/stop/restart a Docker container."""
        mutation_map = {
            "start": DOCKER_START_MUTATION,
            "stop": DOCKER_STOP_MUTATION,
            "restart": DOCKER_RESTART_MUTATION,
        }
        mutation = mutation_map.get(action.lower())
        if not mutation:
            return f"Unknown action: {action}"

        try:
            data = await self._graphql(mutation, variables={"id": container_id})
            return str(data)
        except Exception as exc:
            logger.error("Docker action %s on %s failed: %s", action, container_id, exc)
            return f"Failed: {exc}"

    # ── Shares ────────────────────────────────────────────────
    async def get_shares(self) -> list[dict[str, Any]]:
        """List Unraid shares with size/free info."""
        data = await self._graphql(SHARES_QUERY)
        return data.get("shares", [])

    # ── Health Check ──────────────────────────────────────────
    async def health_check(self) -> HealthStatus:
        start = time.monotonic()
        try:
            await self._graphql("{ info { os { hostname } } }")
            elapsed = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="online", latency_ms=elapsed, version="unraid")
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            return HealthStatus(status="offline", latency_ms=elapsed, error=str(exc))

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

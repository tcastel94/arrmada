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

# Actions live under the `docker` mutation namespace and take a PrefixedID
# (the full compound id returned by the containers query, e.g. "<hostId>:<cid>").
DOCKER_START_MUTATION = """
mutation ($id: PrefixedID!) {
  docker { start(id: $id) { id state } }
}
"""

DOCKER_STOP_MUTATION = """
mutation ($id: PrefixedID!) {
  docker { stop(id: $id) { id state } }
}
"""

DOCKER_RESTART_MUTATION = """
mutation ($id: PrefixedID!) {
  docker { restart(id: $id) { id state } }
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


class DockerActionError(Exception):
    """Unraid could not perform a start/stop/restart action."""


def _normalize_state(state_raw: str) -> str:
    """Map an Unraid/Docker state to running | paused | restarting | stopped.

    PAUSED and RESTARTING used to be reported as "stopped", which was
    misleading (a paused container still holds its resources).
    """
    if state_raw == "RUNNING":
        return "running"
    if state_raw == "PAUSED":
        return "paused"
    if state_raw == "RESTARTING":
        return "restarting"
    return "stopped"


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

            # Keep the FULL compound id (Unraid returns "<hostId>:<containerId>").
            # It must stay intact: it's unique per container (used as the React
            # key) and it's the PrefixedID the start/stop/restart mutations expect.
            # Truncating it collapsed every container to the same host prefix.
            containers.append(
                {
                    "name": name,
                    "status": _normalize_state(state_raw),
                    "image": c.get("image", ""),
                    "id": c.get("id") or "",
                    "status_text": c.get("status", ""),
                    "state_raw": state_raw,
                }
            )
        return containers

    async def docker_action(self, container_id: str, action: str) -> str:
        """Start/stop/restart a Docker container.

        Raises ``ValueError`` for an unknown action and ``DockerActionError``
        when Unraid refuses or fails the action — callers turn these into
        real HTTP errors (previously a failure was returned as a 200
        "Failed: …" string, so the UI reported a success).
        """
        mutation_map = {
            "start": DOCKER_START_MUTATION,
            "stop": DOCKER_STOP_MUTATION,
            "restart": DOCKER_RESTART_MUTATION,
        }
        mutation = mutation_map.get(action.lower())
        if not mutation:
            raise ValueError(f"Unknown action: {action}")

        try:
            data = await self._graphql(mutation, variables={"id": container_id})
        except Exception as exc:
            logger.error("Docker action %s on %s failed: %s", action, container_id, exc)
            raise DockerActionError(str(exc)) from exc
        return str(data)

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

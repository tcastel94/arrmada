"""Path mapping — discover Docker container mount mappings via Unraid GraphQL API.

Extracted from media_mover.py following the Single Responsibility Principle.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.unraid import UnraidClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# GraphQL query to get container mounts
MOUNTS_QUERY = """
{
  docker {
    containers {
      names
      state
      mounts
    }
  }
}
"""


async def get_path_mappings() -> dict[str, Any]:
    """Discover path mappings from Docker container mounts.

    Returns a dict with:
      - service_mounts: per-service mount info
      - downloads_host_path: where SABnzbd downloads land on host
      - movies_host_path: where Radarr movies are stored on host
      - series_host_path: where Sonarr series are stored on host
    """
    client = UnraidClient(
        url=settings.UNRAID_URL,
        api_key=settings.UNRAID_API_KEY,
    )
    try:
        data = await client._graphql(MOUNTS_QUERY)
    finally:
        await client.close()

    containers = data.get("docker", {}).get("containers", [])

    service_types = ["radarr", "sonarr", "sabnzbd", "jellyfin", "bazarr"]
    service_mounts: dict[str, list[dict]] = {}

    for c in containers:
        name = (c.get("names") or [""])[0].lstrip("/").lower()
        svc_type = None
        for t in service_types:
            if t in name:
                svc_type = t
                break
        if not svc_type:
            continue

        mounts = []
        for m in c.get("mounts", []):
            if isinstance(m, dict):
                mounts.append({
                    "host": m.get("Source", ""),
                    "container": m.get("Destination", ""),
                    "rw": m.get("RW", False),
                })
        service_mounts[svc_type] = mounts

    # Derive key paths
    downloads_host = ""
    movies_host = ""
    series_host = ""

    # From SABnzbd mounts
    for m in service_mounts.get("sabnzbd", []):
        if m["container"] == "/data":
            downloads_host = m["host"]

    # From Radarr mounts — /media is the movies folder
    for m in service_mounts.get("radarr", []):
        if m["container"] == "/media":
            movies_host = m["host"]

    # From Sonarr or Bazarr mounts — /tv is the series folder
    for m in service_mounts.get("bazarr", []):
        if m["container"] == "/tv":
            series_host = m["host"]

    if not series_host:
        for m in service_mounts.get("sonarr", []):
            if m["container"] in ("/tv", "/media"):
                if "seriesTV" in m["host"] or "series" in m["host"].lower():
                    series_host = m["host"]

    return {
        "service_mounts": service_mounts,
        "downloads_host_path": downloads_host,
        "movies_host_path": movies_host,
        "series_host_path": series_host,
    }

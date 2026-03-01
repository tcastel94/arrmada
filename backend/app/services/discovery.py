"""Network discovery — scan local network for *arr services.

Probes common ports used by *arr services and checks their API endpoints
to auto-detect running instances.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Known *arr service ports and their API health endpoints
SERVICE_SIGNATURES: list[dict[str, Any]] = [
    {"type": "sonarr",   "port": 8989, "api_path": "/api/v3/system/status", "name": "Sonarr"},
    {"type": "radarr",   "port": 7878, "api_path": "/api/v3/system/status", "name": "Radarr"},
    {"type": "lidarr",   "port": 8686, "api_path": "/api/v1/system/status", "name": "Lidarr"},
    {"type": "readarr",  "port": 8787, "api_path": "/api/v1/system/status", "name": "Readarr"},
    {"type": "prowlarr", "port": 9696, "api_path": "/api/v1/system/status", "name": "Prowlarr"},
    {"type": "bazarr",   "port": 6767, "api_path": "/api/system/status",   "name": "Bazarr"},
    {"type": "jellyfin", "port": 8096, "api_path": "/System/Info/Public",   "name": "Jellyfin"},
    {"type": "sabnzbd",  "port": 8080, "api_path": "/api?mode=version",     "name": "SABnzbd"},
]


def _get_local_subnet() -> str:
    """Get the local network gateway to determine scan range."""
    try:
        # Connect to a public address to discover our local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Return the /24 subnet
        parts = local_ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    except Exception:
        return "192.168.1"


async def _probe_host(
    host: str,
    sig: dict[str, Any],
    timeout: float = 2.0,
) -> dict[str, Any] | None:
    """Probe a single host+port for a specific service type."""
    url = f"http://{host}:{sig['port']}"
    api_url = f"{url}{sig['api_path']}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(api_url)
            if resp.status_code in (200, 401, 403):
                # 401/403 means the service exists but needs an API key
                version = None
                needs_api_key = resp.status_code in (401, 403)

                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        version = data.get("version") or data.get("Version")
                    except Exception:
                        pass

                return {
                    "type": sig["type"],
                    "name": sig["name"],
                    "url": url,
                    "port": sig["port"],
                    "host": host,
                    "version": version,
                    "needs_api_key": needs_api_key,
                    "status": "found",
                }
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        pass
    return None


async def discover_services(
    scan_hosts: list[str] | None = None,
    include_localhost: bool = True,
) -> list[dict[str, Any]]:
    """Scan the network for *arr services.

    Args:
        scan_hosts: Specific IPs to scan. If None, scans common local addresses.
        include_localhost: Whether to include 127.0.0.1 and localhost.

    Returns:
        List of discovered services with their type, URL, and detected info.
    """
    if scan_hosts is None:
        subnet = _get_local_subnet()
        # Scan gateway, common NAS IPs, and a small range
        scan_hosts = [
            f"{subnet}.1",    # Gateway
            f"{subnet}.2",
            f"{subnet}.10",
            f"{subnet}.50",
            f"{subnet}.100",
        ]
        # Add some common IPs in the range
        for i in range(200, 256):
            scan_hosts.append(f"{subnet}.{i}")

    if include_localhost:
        scan_hosts = ["127.0.0.1", "localhost"] + scan_hosts

    # Deduplicate
    scan_hosts = list(dict.fromkeys(scan_hosts))

    logger.info("Scanning %d hosts for *arr services...", len(scan_hosts))

    discovered: list[dict[str, Any]] = []
    tasks: list[asyncio.Task] = []

    for host in scan_hosts:
        for sig in SERVICE_SIGNATURES:
            tasks.append(asyncio.create_task(_probe_host(host, sig, timeout=1.5)))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, dict):
            discovered.append(result)

    # Deduplicate by url+type
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for svc in discovered:
        key = f"{svc['type']}:{svc['url']}"
        if key not in seen:
            seen.add(key)
            unique.append(svc)

    logger.info("Discovered %d services", len(unique))
    return unique

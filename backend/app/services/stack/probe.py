"""Find the URL where each app answers, from inside the ArrMada container.

A config file gives the port and URL base, but not the HOST. We try a
short list of candidates in parallel and keep those where the app answers
**with the key we read** (so we never mistake one app for another):

  1. hosts given by the user in the UI (e.g. the NAS LAN IP);
  2. hosts of the services already registered in ArrMada (same machine);
  3. the app's name as a Docker DNS name (``sonarr``, ``radarr-4k``…),
     resolved when the containers share a Docker network;
  4. the Docker host itself: default gateway of the container, then
     ``host.docker.internal`` (Docker Desktop on Windows / macOS).

Order matters: LAN addresses come first because they also work from the
OTHER containers (Prowlarr must reach Sonarr with the URL we give it).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.services.jellyfin import auth_header as jellyfin_auth
from app.services.stack.configs import FoundConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)

PROBE_TIMEOUT = 3.0

# Authenticated status endpoint per app (prefix-relative, without URL base).
STATUS_PATHS = {
    "sonarr": "/api/v3/system/status",
    "radarr": "/api/v3/system/status",
    "whisparr": "/api/v3/system/status",
    "lidarr": "/api/v1/system/status",
    "readarr": "/api/v1/system/status",
    "prowlarr": "/api/v1/system/status",
    "bazarr": "/api/system/status",
}


@dataclass
class Endpoint:
    """An app reachable from ArrMada, with every URL that worked."""

    config: FoundConfig
    urls: list[str] = field(default_factory=list)  # best first
    version: str | None = None
    password_ok: bool | None = None  # downloaders: login verified?
    error: str | None = None

    @property
    def url(self) -> str | None:
        return self.urls[0] if self.urls else None


def default_gateway() -> str | None:
    """IPv4 default gateway of the container = the Docker host (bridge mode)."""
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) > 2 and fields[1] == "00000000":
                return socket.inet_ntoa(bytes.fromhex(fields[2])[::-1])
    except (OSError, ValueError):
        pass
    return None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def candidate_hosts(
    config: FoundConfig, user_hosts: list[str], known_hosts: list[str]
) -> list[str]:
    """Hosts to try for one app, most portable first."""
    names: list[str] = []
    # Docker DNS: folder name (radarr-4k) then the plain app type (radarr).
    folder = Path(config.source).parts[0].lower() if config.source else ""
    for name in (folder, config.type):
        if name and all(c.isalnum() or c in "-_." for c in name):
            names.append(name)
    gateway = default_gateway()
    hosts = [*user_hosts, *known_hosts, *names]
    if gateway:
        hosts.append(gateway)
    hosts.append("host.docker.internal")
    # LAN / known IPs first, then names; keep order, drop duplicates.
    return list(dict.fromkeys(h for h in hosts if h))


async def _check(
    client: httpx.AsyncClient, config: FoundConfig, base: str, password: str | None
) -> dict[str, Any] | None:
    """Return details if ``base`` really is this app (authenticated), else None."""
    t = config.type
    try:
        if t in STATUS_PATHS:
            resp = await client.get(
                f"{base}{STATUS_PATHS[t]}", headers={"X-Api-Key": config.api_key or ""}
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            # Bazarr wraps its payload in {"data": {...}}
            data = data.get("data", data) if isinstance(data, dict) else {}
            app_name = str(data.get("appName") or data.get("instanceName") or t).lower()
            if t != "bazarr" and t not in app_name:
                return None  # another *arr on that port
            return {"version": data.get("version") or data.get("bazarr_version")}
        if t == "sabnzbd":
            resp = await client.get(
                f"{base}/api",
                params={"mode": "version", "apikey": config.api_key, "output": "json"},
            )
            # mode=version answers without a key: check the key with a keyed call.
            auth = await client.get(
                f"{base}/api",
                params={"mode": "queue", "limit": 1, "apikey": config.api_key, "output": "json"},
            )
            if resp.status_code != 200 or auth.status_code != 200 or "queue" not in auth.text:
                return None
            return {"version": resp.json().get("version")}
        if t == "deluge":
            resp = await client.post(
                f"{base}/json", json={"method": "auth.check_session", "params": [], "id": 1}
            )
            if resp.status_code != 200 or "result" not in resp.text:
                return None
            details: dict[str, Any] = {"version": None, "password_ok": None}
            if password:
                login = await client.post(
                    f"{base}/json", json={"method": "auth.login", "params": [password], "id": 2}
                )
                details["password_ok"] = (
                    login.status_code == 200 and login.json().get("result") is True
                )
            return details
        if t == "qbittorrent":
            resp = await client.get(f"{base}/api/v2/app/version")
            # Unauthenticated: 403 "Forbidden". Whitelisted subnet: 200 + version.
            if resp.status_code not in (200, 403) or "<html" in resp.text.lower():
                return None
            details = {
                "version": resp.text.strip() if resp.status_code == 200 else None,
                "password_ok": None,
            }
            if resp.status_code == 200:
                details["password_ok"] = True  # no auth needed from ArrMada's subnet
            elif password:
                login = await client.post(
                    f"{base}/api/v2/auth/login",
                    data={"username": config.username or "admin", "password": password},
                    headers={"Referer": base},
                )
                # qBittorrent < 5: 200 "Ok." + cookie SID.
                # qBittorrent ≥ 5: 204 (vide) + cookie QBT_SID_<port>.
                details["password_ok"] = login.status_code in (200, 204) and (
                    login.text.strip() == "Ok." or any("SID" in name for name in login.cookies)
                )
            return details
        if t == "jellyfin":
            if not config.api_key:
                # No key yet: still locate it (public endpoint), so the UI says
                # "create an API key" instead of a misleading "unreachable".
                resp = await client.get(f"{base}/System/Info/Public")
                if resp.status_code != 200 or "Jellyfin" not in resp.text:
                    return None
                return {"version": resp.json().get("Version")}
            resp = await client.get(f"{base}/System/Info", headers=jellyfin_auth(config.api_key))
            if resp.status_code != 200:
                return None
            return {"version": resp.json().get("Version")}
    except (httpx.HTTPError, ValueError, OSError):
        return None
    return None


async def locate(
    config: FoundConfig,
    *,
    user_hosts: list[str] | None = None,
    known_hosts: list[str] | None = None,
    password: str | None = None,
) -> Endpoint:
    """Probe every candidate host for one app (in parallel)."""
    endpoint = Endpoint(config=config)
    scheme = "https" if config.ssl else "http"
    hosts = candidate_hosts(config, user_hosts or [], known_hosts or [])
    bases = [f"{scheme}://{h}:{config.port}{config.url_base}" for h in hosts]
    password = password or config.password

    async with httpx.AsyncClient(
        timeout=PROBE_TIMEOUT, verify=False, follow_redirects=False
    ) as client:
        results = await asyncio.gather(*(_check(client, config, b, password) for b in bases))

    for base, details in zip(bases, results, strict=True):
        if details is None:
            continue
        endpoint.urls.append(base)
        endpoint.version = endpoint.version or details.get("version")
        if details.get("password_ok") is not None:
            endpoint.password_ok = bool(endpoint.password_ok) or details["password_ok"]

    if not endpoint.urls:
        endpoint.error = (
            f"Injoignable sur le port {config.port} "
            f"(essayé : {', '.join(hosts[:6])}). Indique l'IP de la machine qui l'héberge."
        )
    logger.info("Located %s: %s", config.name, endpoint.urls or endpoint.error)
    return endpoint


def host_of(url: str) -> str | None:
    """Host part of a stored service URL (to reuse it as a candidate)."""
    try:
        return httpx.URL(url).host or None
    except Exception:  # noqa: BLE001
        return None


def lan_first(hosts: list[str]) -> list[str]:
    """Private IPs first (most likely the NAS LAN address), then the rest."""

    def rank(h: str) -> int:
        if (
            _is_ip(h)
            and ipaddress.ip_address(h).is_private
            and not ipaddress.ip_address(h).is_loopback
        ):
            return 0
        return 1

    return sorted(dict.fromkeys(hosts), key=rank)

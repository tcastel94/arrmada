"""Installation neuve : aucun endpoint ne doit planter (HTTP 500).

Cas réel couvert : `/api/files/paths` levait « URL is missing a protocol »
quand Unraid n'était pas configuré. Le réseau est coupé (fixture
`fake_network`) : seuls les comportements « rien de configuré » sont testés.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# Endpoints qui doivent répondre 200 sur une base vide.
EMPTY_OK = [
    "/api/activity/timeline",
    "/api/analytics",
    "/api/calendar",
    "/api/cast/devices",
    "/api/cast/jellyfin",
    "/api/cast/jellyfin/test",
    "/api/cleanup",
    "/api/dashboard/activity",
    "/api/dashboard/stats",
    "/api/downloads",
    "/api/duplicates",
    "/api/events/recent",
    "/api/files/auto-import/reports",
    "/api/files/history",
    "/api/files/paths",
    "/api/files/stuck",
    "/api/kodi/drift",
    "/api/kodi/now-playing",
    "/api/kodi/settings",
    "/api/kodi/watched-status",
    "/api/media",
    "/api/media/facets",
    "/api/notifications",
    "/api/notifications/count",
    "/api/profile-overrides",
    "/api/profile-overrides/profiles",
    "/api/prowlarr/indexers",
    "/api/prowlarr/stats",
    "/api/quality",
    "/api/recommendations",
    "/api/recommendations/discover",
    "/api/requests",
    "/api/services",
    "/api/services/health/all",
    "/api/settings",
    "/api/setup/status",
    "/api/subtitles/status",
    "/api/system/disk",
    "/api/system/kodi/sessions",
    "/api/yamaha/inputs",
    "/api/yamaha/settings",
    "/api/yamaha/state",
]

# Endpoints qui signalent proprement l'absence du service requis.
EMPTY_EXPECTED_ERROR = {
    "/api/sabnzbd-config/audit": 404,  # pas de SABnzbd
    "/api/subtitles/languages": 503,  # pas de Bazarr
}


@pytest.mark.parametrize("path", EMPTY_OK)
async def test_empty_install_ok(
    client: AsyncClient, auth_headers: dict, fake_network: None, path: str
) -> None:
    resp = await client.get(path, headers=auth_headers)
    assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text[:200]}"


@pytest.mark.parametrize(("path", "status"), EMPTY_EXPECTED_ERROR.items())
async def test_empty_install_explicit_error(
    client: AsyncClient, auth_headers: dict, fake_network: None, path: str, status: int
) -> None:
    resp = await client.get(path, headers=auth_headers)
    assert resp.status_code == status
    assert resp.json()["detail"]  # message lisible pour l'interface


async def test_nas_paths_empty_without_unraid(
    client: AsyncClient, auth_headers: dict, fake_network: None
) -> None:
    """Sans Unraid : structure vide (le panneau « Chemins NAS » se masque)."""
    data = (await client.get("/api/files/paths", headers=auth_headers)).json()
    assert data == {
        "service_mounts": {},
        "downloads_host_path": "",
        "movies_host_path": "",
        "series_host_path": "",
    }


async def test_protected_endpoints_require_auth(client: AsyncClient) -> None:
    for path in ("/api/media", "/api/services", "/api/settings", "/api/files/paths"):
        resp = await client.get(path)
        assert resp.status_code in (401, 403), f"{path} accessible sans authentification"

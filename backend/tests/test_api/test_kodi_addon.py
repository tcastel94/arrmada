"""Tests for Kodi Add-on API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_kodi_addon_api_key_auth(client: AsyncClient, admin_password: str):
    """Verify that X-Api-Key authenticates requests properly."""
    # Without auth -> 401
    resp = await client.get("/api/kodi/addon-status")
    assert resp.status_code == 401

    # With X-Api-Key (= admin password) -> 200
    headers = {"X-Api-Key": admin_password}
    resp = await client.get("/api/kodi/addon-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "downloads" in data


@pytest.mark.asyncio
async def test_kodi_addon_scrobble(client: AsyncClient, auth_headers: dict[str, str]):
    """Verify live playback scrobble endpoint."""
    payload = {
        "event": "play",
        "title": "Dune: Part Two",
        "media_type": "movie",
        "tmdb_id": 693134,
        "percentage": 15.5,
        "position": 1200,
        "total": 9600,
        "device_name": "Kodi Salon",
    }
    resp = await client.post("/api/kodi/scrobble", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_kodi_addon_subtitles_no_service(client: AsyncClient, auth_headers: dict[str, str]):
    """Verify subtitles action graceful response when Bazarr is not configured."""
    payload = {
        "title": "Inception",
        "media_type": "movie",
        "tmdb_id": 27205,
        "language": "fr",
    }
    resp = await client.post("/api/kodi/actions/subtitles", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "Bazarr n'est pas configuré" in data["message"]


@pytest.mark.asyncio
async def test_kodi_addon_search_no_service(client: AsyncClient, auth_headers: dict[str, str]):
    """Verify search action graceful response when Radarr is not configured."""
    payload = {
        "title": "Inception",
        "media_type": "movie",
        "tmdb_id": 27205,
    }
    resp = await client.post("/api/kodi/actions/search", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "Radarr n'est pas configuré" in data["message"]

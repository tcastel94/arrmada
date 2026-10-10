"""Recommandations TMDB, avec un faux TMDB (cf. tests/fake_arr.py).

Point clé vérifié : pour une SÉRIE, l'ID stocké est un ID TVDB (Sonarr) ;
il doit être traduit en ID TMDB (/find) avant d'appeler /tv/{id}/…, sinon
TMDB renvoie les recommandations d'une tout autre série.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.fixture
def tmdb_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TMDB_API_KEY", "cle-tmdb-de-test")


class TestRecommendations:
    async def test_full_page(self, client: AsyncClient, arr_stack: dict, tmdb_key: None) -> None:
        resp = await client.get("/api/recommendations", headers=arr_stack)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["tmdb_available"] is True
        assert [m["title"] for m in data["trending_movies"]] == ["Interstellar"]

        by_base = {b["base_title"]: b for b in data["because_you_have"]}
        # Série : TVDB 280619 → TMDB 63639 → recommandations de la BONNE série.
        expanse = by_base["The Expanse"]
        assert expanse["base_type"] == "series"
        assert expanse["base_id"] == "10"  # id Sonarr → lien vers la fiche
        assert [r["title"] for r in expanse["recommendations"]] == ["Game of Thrones"]
        assert "Dune" in by_base

    async def test_without_tmdb_key(self, client: AsyncClient, arr_stack: dict) -> None:
        data = (await client.get("/api/recommendations", headers=arr_stack)).json()
        assert data["tmdb_available"] is False
        assert data["because_you_have"] == []

    async def test_detail_modal(
        self, client: AsyncClient, auth_headers: dict, fake_network: None, tmdb_key: None
    ) -> None:
        resp = await client.get("/api/recommendations/details/movie/157336", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["title"] == "Interstellar"

    async def test_discover_and_based_on(
        self, client: AsyncClient, auth_headers: dict, fake_network: None, tmdb_key: None
    ) -> None:
        for path in (
            "/api/recommendations/discover?media_type=movie&genre=Science-Fiction",
            "/api/recommendations/discover?media_type=tv",
            "/api/recommendations/based_on/movie/438631",
        ):
            resp = await client.get(path, headers=auth_headers)
            assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text[:200]}"

    async def test_based_on_series_from_library(
        self, client: AsyncClient, arr_stack: dict, tmdb_key: None
    ) -> None:
        """Série Sonarr : ID TVDB → converti en TMDB grâce à source=tvdb."""
        page = (await client.get("/api/recommendations", headers=arr_stack)).json()
        expanse = next(i for i in page["library_select_items"] if i["title"] == "The Expanse")
        assert expanse["id"] == "10"
        assert expanse["id_source"] == "tvdb"
        resp = await client.get(
            f"/api/recommendations/based_on/series/{expanse['tmdb_id']}?source=tvdb",
            headers=arr_stack,
        )
        assert [i["title"] for i in resp.json()["items"]] == ["Game of Thrones"]

    async def test_kodi_addon_recommendations(
        self, client: AsyncClient, arr_stack: dict, tmdb_key: None
    ) -> None:
        resp = await client.get("/api/kodi/media/recommendations", headers=arr_stack)
        assert resp.status_code == 200, resp.text


class TestYamahaProfiles:
    """Profils audio par pièce (Salon / Cinéma), sans ampli configuré."""

    async def test_profiles_persisted(
        self,
        client: AsyncClient,
        auth_headers: dict,
        fake_network: None,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.services import yamaha as yamaha_service

        store = tmp_path / "yamaha_room_profiles.json"
        monkeypatch.setattr(yamaha_service, "_PROFILES_FILE", store)

        defaults = (await client.get("/api/yamaha/profiles", headers=auth_headers)).json()
        assert {"salon", "cinema"} <= set(defaults)

        save = await client.post(
            "/api/yamaha/profiles",
            json={"room": "cinema", "profile": {"volume_pct": 42}},
            headers=auth_headers,
        )
        assert save.status_code == 200, save.text
        assert store.exists()  # écrit sur disque, plus seulement en mémoire

        reread = (await client.get("/api/yamaha/profiles", headers=auth_headers)).json()
        assert reread["cinema"]["volume_pct"] == 42
        assert reread["cinema"]["name"] == defaults["cinema"]["name"]  # défauts conservés

        apply = await client.post(
            "/api/yamaha/preset/apply",
            json={"room": "cinema", "media_type": "movie"},
            headers=auth_headers,
        )
        assert apply.status_code == 200, apply.text

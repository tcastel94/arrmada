"""Synopsis en français (TMDB fr-FR, anglais en secours) — services/translations.py.

Fonctions pures, puis bout en bout avec le faux Radarr / Sonarr et un faux
TMDB : fiche d'un film et d'une série, médiathèque, tâche de remplissage.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.translation import MediaTranslation
from app.services import translations
from tests import fake_arr

DUNE_EN = "Paul Atreides, a brilliant and gifted young man born into a great destiny…"
DUNE_FR = "L'histoire de Paul Atréides, jeune homme aussi doué que brillant…"
EXPANSE_EN = "Hundreds of years in the future, humans have colonized the solar system."
EXPANSE_FR = "Dans un futur où l'humanité a colonisé le système solaire…"

# Appels reçus par le faux TMDB : (chemin, langue demandée)
CALLS: list[tuple[str, str]] = []


def _tmdb(overview: str) -> fake_arr.Handler:
    def handler(params: dict[str, str], m: Any) -> Any:
        CALLS.append((m.string, params.get("language", "")))
        return {"id": 1, "overview": overview}

    return handler


@pytest.fixture
def french_tmdb(monkeypatch: pytest.MonkeyPatch, fake_network: None) -> None:
    """Résumés anglais dans Radarr / Sonarr, français chez TMDB (Oppenheimer : pas traduit)."""
    CALLS.clear()
    monkeypatch.setattr(settings, "TMDB_API_KEY", "tmdb-test")
    monkeypatch.setitem(fake_arr.MOVIES[0], "overview", DUNE_EN)
    monkeypatch.setitem(fake_arr.MOVIES[1], "overview", "Story of J. Robert Oppenheimer.")
    monkeypatch.setitem(fake_arr.SERIES[0], "overview", EXPANSE_EN)
    monkeypatch.setitem(fake_arr.SERIES[0], "tmdbId", 63639)
    monkeypatch.setitem(
        fake_arr.ROUTES,
        "api.themoviedb.org",
        [
            (r"/3/movie/438631", _tmdb(DUNE_FR)),
            (r"/3/movie/872585", _tmdb("")),  # pas de traduction française
            (r"/3/tv/63639", _tmdb(EXPANSE_FR)),
        ]
        + fake_arr.TMDB_ROUTES,
    )


# ── Fonctions pures ─────────────────────────────────────────────────────────


class TestPure:
    def test_pick_prefers_french_then_english(self) -> None:
        assert translations.pick("Bonjour", "Hello") == "Bonjour"
        assert translations.pick("  ", "Hello") == "Hello"
        assert translations.pick(None, None) == ""

    def test_parse_overview(self) -> None:
        assert translations.parse_overview({"overview": "  Un film.  "}) == "Un film."
        assert translations.parse_overview({"overview": None}) == ""
        assert translations.parse_overview({}) == ""
        assert translations.parse_overview(["pas", "un", "objet"]) == ""

    def test_key_matches_artwork_convention(self) -> None:
        assert translations.translation_key("movie", "438631") == "movie:438631"
        assert translations.translation_key("series", 280619) == "series:280619"

    @pytest.mark.parametrize(
        ("overview", "age", "expected"),
        [
            ("Un film.", timedelta(days=29), False),
            ("Un film.", timedelta(days=31), True),
            ("", timedelta(days=6), False),  # pas de traduction : on attend une semaine
            ("", timedelta(days=8), True),
        ],
    )
    def test_needs_refresh(self, overview: str, age: timedelta, expected: bool) -> None:
        now = datetime(2026, 10, 28, 20, 0, tzinfo=UTC)
        row = MediaTranslation(
            key="movie:1",
            media_type="movie",
            provider_id=1,
            overview=overview,
            fetched_at=now - age,
        )
        assert translations.needs_refresh(row, now) is expected
        assert translations.needs_refresh(None, now) is True

    def test_targets_skip_series_without_tmdb(self) -> None:
        library = [
            {"type": "movie", "tmdb_id": 438631},
            {"type": "movie", "tmdb_id": 438631},  # doublon (deux Radarr)
            {"type": "series", "tmdb_id": 280619, "tmdb_tv_id": 63639},
            {"type": "series", "tmdb_id": 999, "tmdb_tv_id": None},
            {"type": "file", "tmdb_id": 5},
        ]
        assert translations.library_targets(library) == [
            {"media_type": "movie", "provider_id": 438631, "tmdb_id": 438631},
            {"media_type": "series", "provider_id": 280619, "tmdb_id": 63639},
        ]


# ── Bout en bout ────────────────────────────────────────────────────────────


class TestDetail:
    async def test_movie_detail_in_french_then_from_database(
        self, client: AsyncClient, arr_stack: dict, french_tmdb: None
    ) -> None:
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["overview"] == DUNE_FR
        assert CALLS == [("/3/movie/438631", "fr-FR")]

        # Deuxième ouverture : lue en base, TMDB n'est plus appelé
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["overview"] == DUNE_FR
        assert len(CALLS) == 1

    async def test_movie_without_translation_keeps_english(
        self, client: AsyncClient, arr_stack: dict, french_tmdb: None
    ) -> None:
        detail = (await client.get("/api/media/movie/2", headers=arr_stack)).json()
        assert detail["overview"] == "Story of J. Robert Oppenheimer."

    async def test_series_detail_uses_tmdb_tv_id(
        self, client: AsyncClient, arr_stack: dict, french_tmdb: None
    ) -> None:
        detail = (await client.get("/api/media/series/10", headers=arr_stack)).json()
        assert detail["overview"] == EXPANSE_FR
        assert CALLS == [("/3/tv/63639", "fr-FR")]

    async def test_tmdb_down_keeps_english(
        self,
        client: AsyncClient,
        arr_stack: dict,
        french_tmdb: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def down(_params: dict[str, str], _m: Any) -> httpx.Response:
            return httpx.Response(503)

        monkeypatch.setitem(fake_arr.ROUTES, "api.themoviedb.org", [(r"/3/movie/438631", down)])
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["overview"] == DUNE_EN

    async def test_without_tmdb_key_nothing_is_asked(
        self,
        client: AsyncClient,
        arr_stack: dict,
        french_tmdb: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["overview"] == DUNE_EN
        assert CALLS == []


class TestLibrary:
    async def test_fill_then_library_in_french(
        self, client: AsyncClient, arr_stack: dict, french_tmdb: None
    ) -> None:
        # Avant le passage de la tâche : l'anglais de Radarr / Sonarr
        items = (await client.get("/api/media", headers=arr_stack)).json()["items"]
        assert {m["title"]: m["overview"] for m in items}["Dune"] == DUNE_EN

        counts = await translations.refresh_library()
        # Dune, Oppenheimer, The Expanse (+ « Vieux Film », inconnu du faux TMDB)
        assert counts == {"total": 4, "french": 2, "errors": 0}

        by_title = {
            m["title"]: m
            for m in (await client.get("/api/media", headers=arr_stack)).json()["items"]
        }
        assert by_title["Dune"]["overview"] == DUNE_FR
        assert by_title["The Expanse"]["overview"] == EXPANSE_FR
        assert by_title["Oppenheimer"]["overview"] == "Story of J. Robert Oppenheimer."

        # Passage suivant : rien à redemander
        CALLS.clear()
        assert (await translations.refresh_library())["total"] == 0
        assert CALLS == []

    async def test_failed_fetch_is_retried_soon(
        self, arr_stack: dict, french_tmdb: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def down(_params: dict[str, str], _m: Any) -> httpx.Response:
            return httpx.Response(500)

        monkeypatch.setitem(fake_arr.ROUTES, "api.themoviedb.org", [(r"/3/(movie|tv)/\d+", down)])
        counts = await translations.refresh_library()
        assert counts["errors"] == counts["total"] == 4

        async with translations.session_factory() as db:  # base de test (conftest)
            row = await db.get(MediaTranslation, 1)
            assert row is not None and row.overview == ""
            # Redemandé dans l'heure, pas dans une semaine
            assert translations.needs_refresh(
                row, datetime.now(UTC) + timedelta(hours=1, minutes=1)
            )
            assert not translations.needs_refresh(row, datetime.now(UTC) + timedelta(minutes=50))

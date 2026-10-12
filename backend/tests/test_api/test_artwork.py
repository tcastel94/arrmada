"""Artworks : logos, disques, clearart (fanart.tv + TMDB) — services/artwork.py.

Fonctions pures de choix d'image, puis bout en bout avec le faux Radarr /
Sonarr (tests/fake_arr.py) et un faux fanart.tv : bouton « Récupérer les
artworks », fusion dans la médiathèque, la fiche et la file de téléchargement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import artwork
from tests import fake_arr

NOW = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)

# ── Faux fanart.tv (webservice.fanart.tv/v3) ────────────────────────────────

FANART_DUNE = {
    "name": "Dune",
    "tmdb_id": "438631",
    "hdmovielogo": [
        {"url": "https://assets.fanart.tv/dune-logo-en.png", "lang": "en", "likes": "9"},
        {"url": "https://assets.fanart.tv/dune-logo-fr.png", "lang": "fr", "likes": "1"},
    ],
    "moviedisc": [
        {
            "url": "https://assets.fanart.tv/dune-dvd.png",
            "lang": "en",
            "likes": "5",
            "disc_type": "dvd",
        },
        {
            "url": "https://assets.fanart.tv/dune-bd.png",
            "lang": "en",
            "likes": "2",
            "disc_type": "bluray",
        },
    ],
    "hdmovieclearart": [{"url": "https://assets.fanart.tv/dune-clearart.png", "lang": "en"}],
    "moviebanner": [{"url": "https://assets.fanart.tv/dune-banner.jpg", "lang": "en"}],
    "moviethumb": [{"url": "https://assets.fanart.tv/dune-thumb.jpg", "lang": "fr"}],
}
FANART_OPPENHEIMER = {
    # Pas de logo sur fanart.tv : c'est TMDB qui le fournira
    "moviedisc": [
        {"url": "https://assets.fanart.tv/opp-bd.png", "lang": "00", "disc_type": "bluray"}
    ],
    "movieposter": [{"url": "https://assets.fanart.tv/opp-poster.jpg", "lang": "fr"}],
}
FANART_EXPANSE = {
    "hdtvlogo": [{"url": "https://assets.fanart.tv/expanse-logo.png", "lang": "en"}],
    "hdclearart": [{"url": "https://assets.fanart.tv/expanse-clearart.png", "lang": "en"}],
    "tvbanner": [{"url": "https://assets.fanart.tv/expanse-banner.jpg", "lang": "en"}],
}
FANART_ROUTES = [
    (r"/v3/movies/438631", fake_arr._const(FANART_DUNE)),
    (r"/v3/movies/872585", fake_arr._const(FANART_OPPENHEIMER)),
    (r"/v3/tv/280619", fake_arr._const(FANART_EXPANSE)),
]

TMDB_OPPENHEIMER_IMAGES = {
    "logos": [
        {"file_path": "/opp-vector.svg", "iso_639_1": "fr", "vote_average": 9},
        {"file_path": "/opp-en.png", "iso_639_1": "en", "vote_average": 8},
        {"file_path": "/opp-fr.png", "iso_639_1": "fr", "vote_average": 2},
    ]
}


@pytest.fixture
def artwork_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clés fanart.tv + TMDB, faux fanart.tv, logos TMDB d'Oppenheimer."""
    monkeypatch.setattr(settings, "FANART_API_KEY", "fanart-test")
    monkeypatch.setattr(settings, "TMDB_API_KEY", "tmdb-test")
    monkeypatch.setitem(fake_arr.ROUTES, "webservice.fanart.tv", FANART_ROUTES)
    monkeypatch.setitem(
        fake_arr.ROUTES,
        "api.themoviedb.org",
        [(r"/3/movie/872585/images", fake_arr._const(TMDB_OPPENHEIMER_IMAGES))]
        + fake_arr.TMDB_ROUTES,
    )


# ── Choix des images (pur) ─────────────────────────────────────────────────


class TestPicking:
    def test_french_first_then_english_then_textless(self) -> None:
        assert artwork.lang_rank("fr") < artwork.lang_rank("en") < artwork.lang_rank("00")
        assert artwork.lang_rank("00") == artwork.lang_rank("") == artwork.lang_rank(None)
        assert artwork.lang_rank("de") > artwork.lang_rank("00")

    def test_language_beats_likes(self) -> None:
        image = artwork.pick_fanart(FANART_DUNE, ("hdmovielogo", "movielogo"))
        assert image["url"].endswith("dune-logo-fr.png")

    def test_hd_section_beats_sd_at_same_language(self) -> None:
        data = {
            "movielogo": [{"url": "https://x/sd.png", "lang": "fr", "likes": "50"}],
            "hdmovielogo": [{"url": "https://x/hd.png", "lang": "fr", "likes": "0"}],
        }
        assert artwork.pick_fanart(data, ("hdmovielogo", "movielogo"))["url"] == "https://x/hd.png"

    def test_bluray_disc_beats_dvd(self) -> None:
        found = artwork.parse_fanart(FANART_DUNE, "movie")
        assert found["discart"].endswith("dune-bd.png")
        assert found["disc_type"] == "bluray"
        assert found["clearart"].endswith("dune-clearart.png")
        assert found["banner"].endswith("dune-banner.jpg")
        assert found["landscape"].endswith("dune-thumb.jpg")

    def test_series_have_no_disc(self) -> None:
        found = artwork.parse_fanart(
            {**FANART_EXPANSE, "moviedisc": FANART_DUNE["moviedisc"]}, "series"
        )
        assert "discart" not in found
        assert found["clearlogo"].endswith("expanse-logo.png")

    def test_broken_entries_are_ignored(self) -> None:
        data = {"hdmovielogo": [None, {"lang": "fr"}, {"url": "ftp://nope", "lang": "fr"}]}
        assert artwork.parse_fanart(data, "movie") == {}
        assert artwork.parse_fanart("not json", "movie") == {}

    def test_tmdb_logo_skips_svg_and_prefers_french(self) -> None:
        assert artwork.parse_tmdb_logo(TMDB_OPPENHEIMER_IMAGES) == (
            "https://image.tmdb.org/t/p/w500/opp-fr.png"
        )
        assert artwork.parse_tmdb_logo({"logos": [{"file_path": "/only.svg"}]}) == ""
        assert artwork.parse_tmdb_logo({}) == ""

    @pytest.mark.parametrize(
        ("status", "age", "force", "expected"),
        [
            (None, None, False, True),  # jamais demandé
            ("ok", timedelta(days=29), False, False),
            ("ok", timedelta(days=30), False, True),
            ("empty", timedelta(days=6), False, False),
            ("empty", timedelta(days=7), False, True),
            ("error", timedelta(minutes=30), False, False),
            ("error", timedelta(hours=1), False, True),
            ("ok", timedelta(minutes=1), True, True),  # bouton « tout redemander »
        ],
    )
    def test_refresh_delays(self, status, age, force, expected) -> None:
        fetched = NOW - age if age is not None else None
        assert artwork.needs_refresh(status, fetched, NOW, force) is expected

    def test_naive_dates_from_sqlite(self) -> None:
        naive = (NOW - timedelta(days=1)).replace(tzinfo=None)
        assert artwork.needs_refresh("ok", naive, NOW) is False

    def test_targets_skip_unidentified_and_duplicates(self) -> None:
        library = [
            {"type": "movie", "tmdb_id": 1, "title": "A", "external_id": "7"},
            {"type": "movie", "tmdb_id": 1, "title": "A bis", "external_id": "8"},
            {"type": "series", "tmdb_id": 2, "tmdb_tv_id": 20, "title": "B"},
            {"type": "movie", "tmdb_id": None, "title": "Sans id"},
            {"type": "music", "tmdb_id": 3, "title": "Album"},
        ]
        targets = artwork.library_targets(library)
        assert [(t["media_type"], t["provider_id"]) for t in targets] == [
            ("movie", 1),
            ("series", 2),
        ]
        assert targets[1]["tmdb_tv_id"] == 20


# ── Bout en bout ───────────────────────────────────────────────────────────


class TestArtworkRefresh:
    async def test_button_needs_a_source(
        self, client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FANART_API_KEY", "")
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        resp = await client.post("/api/artwork/refresh", headers=arr_stack)
        assert resp.status_code == 400
        assert "FANART_API_KEY" in resp.json()["detail"]
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["sources"] == {"fanart": False, "tmdb": False}

    async def test_refresh_fills_library_detail_and_queue(
        self, client: AsyncClient, arr_stack: dict, artwork_sources: None
    ) -> None:
        resp = await client.post("/api/artwork/refresh", headers=arr_stack)
        assert resp.status_code == 202
        assert resp.json()["running"] is True
        # Un second clic pendant la récupération est refusé proprement
        again = await client.post("/api/artwork/refresh", headers=arr_stack)
        assert again.status_code in (202, 409)
        await artwork.wait_for_refresh()

        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["running"] is False
        assert status["stored"]["titles"] == 4  # Dune, Oppenheimer, Vieux Film, The Expanse
        assert status["stored"]["discs"] == 2
        assert status["stored"]["logos"] == 3  # Dune, Oppenheimer (TMDB), The Expanse

        # Médiathèque : logo français, disque, clearart ; l'affiche Radarr reste prioritaire
        media = (await client.get("/api/media", headers=arr_stack)).json()["items"]
        by_title = {m["title"]: m for m in media}
        dune = by_title["Dune"]
        assert dune["clearlogo_url"].endswith("dune-logo-fr.png")
        assert dune["discart_url"].endswith("dune-bd.png")
        assert dune["disc_type"] == "bluray"
        assert dune["clearart_url"].endswith("dune-clearart.png")
        assert dune["poster_url"] == "https://img.test/dune.jpg"
        oppenheimer = by_title["Oppenheimer"]
        assert oppenheimer["clearlogo_url"] == "https://image.tmdb.org/t/p/w500/opp-fr.png"
        assert oppenheimer["poster_url"].endswith("opp-poster.jpg")  # comble l'absence
        assert by_title["The Expanse"]["banner_url"].endswith("expanse-banner.jpg")
        assert "discart_url" not in by_title["The Expanse"]

        # Fiche : mêmes images dans `images`
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["images"]["clearlogo"].endswith("dune-logo-fr.png")
        assert detail["images"]["discart"].endswith("dune-bd.png")
        assert detail["images"]["disc_type"] == "bluray"
        series = (await client.get("/api/media/series/10", headers=arr_stack)).json()
        assert series["images"]["clearlogo"].endswith("expanse-logo.png")

        # File de téléchargement : l'affiche vient du serveur (Oppenheimer, movieId 2)
        queue = (await client.get("/api/downloads", headers=arr_stack)).json()
        items = queue["items"] if isinstance(queue, dict) else queue
        opp = next(i for i in items if i.get("movie_id") == 2)
        assert opp["poster_url"].endswith("opp-poster.jpg")
        assert opp["media_title"] == "Oppenheimer"

    async def test_second_run_skips_fresh_titles_unless_forced(
        self, client: AsyncClient, arr_stack: dict, artwork_sources: None
    ) -> None:
        await client.post("/api/artwork/refresh", headers=arr_stack)
        await artwork.wait_for_refresh()
        await client.post("/api/artwork/refresh", headers=arr_stack)
        await artwork.wait_for_refresh()
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["total"] == 0 and status["skipped"] == 4

        await client.post("/api/artwork/refresh?force=true", headers=arr_stack)
        await artwork.wait_for_refresh()
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["total"] == 4 and status["skipped"] == 0

    async def test_one_title_from_its_page(
        self, client: AsyncClient, arr_stack: dict, artwork_sources: None
    ) -> None:
        resp = await client.post("/api/artwork/movie/1/refresh", headers=arr_stack)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["images"]["discart"].endswith("dune-bd.png")
        missing = await client.post("/api/artwork/movie/999/refresh", headers=arr_stack)
        assert missing.status_code == 404
        bad = await client.post("/api/artwork/music/1/refresh", headers=arr_stack)
        assert bad.status_code == 400

    async def test_unreachable_site_is_an_error_not_empty(
        self, client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # fanart.tv seul, et injoignable (hôte inconnu du faux réseau → 503)
        monkeypatch.setattr(settings, "FANART_API_KEY", "fanart-test")
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        resp = await client.post("/api/artwork/movie/1/refresh", headers=arr_stack)
        assert resp.json()["status"] == "error"

    async def test_unknown_title_on_fanart_is_empty(
        self, client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "FANART_API_KEY", "fanart-test")
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setitem(fake_arr.ROUTES, "webservice.fanart.tv", [])  # tout en 404
        resp = await client.post("/api/artwork/movie/3/refresh", headers=arr_stack)
        assert resp.json() == {"status": "empty", "images": {}}

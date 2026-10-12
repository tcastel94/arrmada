"""Artworks : logos, disques, clearart (fanart.tv + TMDB) — services/artwork.py.

Fonctions pures de choix d'image, puis bout en bout avec le faux Radarr /
Sonarr (tests/fake_arr.py) et un faux fanart.tv : bouton « Récupérer les
artworks », fusion dans la médiathèque, la fiche et la file de téléchargement.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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
        monkeypatch.setattr(settings, "FANART_CLIENT_KEY", "")
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setattr(settings, "ARTWORK_LOCAL_ENABLED", False)
        resp = await client.post("/api/artwork/refresh", headers=arr_stack)
        assert resp.status_code == 400
        assert "FANART_CLIENT_KEY" in resp.json()["detail"]
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["sources"] == {"fanart": False, "tmdb": False, "local": False}

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


# ── Galerie : toutes les images d'un titre ─────────────────────────────────


class TestGallery:
    def test_fanart_keeps_every_image_sorted_by_kind_and_language(self) -> None:
        gallery = artwork.parse_fanart_gallery(FANART_DUNE, "movie")
        kinds = [i["kind"] for i in gallery]
        assert kinds == sorted(kinds)  # regroupées par type
        logos = [i["url"] for i in gallery if i["kind"] == "clearlogo"]
        assert logos == [
            "https://assets.fanart.tv/dune-logo-fr.png",  # français d'abord
            "https://assets.fanart.tv/dune-logo-en.png",
        ]
        discs = [(i["url"], i["disc_type"]) for i in gallery if i["kind"] == "discart"]
        assert discs[0] == ("https://assets.fanart.tv/dune-bd.png", "bluray")  # Blu-ray d'abord
        assert len(discs) == 2  # le DVD reste dans la galerie
        assert all(i["source"] == "fanart.tv" for i in gallery)

    def test_fanart_preview_is_the_small_version(self) -> None:
        url = "https://assets.fanart.tv/fanart/movies/438631/hdmovielogo/dune.png"
        assert artwork.fanart_preview(url) == (
            "https://assets.fanart.tv/preview/movies/438631/hdmovielogo/dune.png"
        )

    def test_series_keep_characters_and_seasons(self) -> None:
        data = {
            "characterart": [{"url": "https://assets.fanart.tv/c.png", "lang": "en"}],
            "seasonposter": [{"url": "https://assets.fanart.tv/s1.jpg", "season": "1"}],
            "moviedisc": [{"url": "https://assets.fanart.tv/x.png"}],  # pas une rubrique série
        }
        gallery = artwork.parse_fanart_gallery(data, "series")
        assert [(i["kind"], i["season"]) for i in gallery] == [
            ("characterart", ""),
            ("seasonposter", "1"),
        ]

    def test_fanart_gallery_is_capped_per_kind(self) -> None:
        many = {"movieposter": [{"url": f"https://assets.fanart.tv/p{n}.jpg"} for n in range(99)]}
        assert len(artwork.parse_fanart_gallery(many, "movie")) == artwork.FANART_PER_KIND

    def test_tmdb_gallery_logos_posters_backdrops(self) -> None:
        data = {
            **TMDB_OPPENHEIMER_IMAGES,
            "posters": [{"file_path": "/p.jpg", "iso_639_1": "fr", "vote_average": 5}],
            "backdrops": [{"file_path": "/b.jpg", "iso_639_1": None}],
        }
        gallery = artwork.parse_tmdb_gallery(data)
        assert [i["url"] for i in gallery] == [
            "https://image.tmdb.org/t/p/original/opp-fr.png",  # SVG ignoré, français d'abord
            "https://image.tmdb.org/t/p/original/opp-en.png",
            "https://image.tmdb.org/t/p/original/p.jpg",
            "https://image.tmdb.org/t/p/original/b.jpg",
        ]
        assert gallery[2]["preview"] == "https://image.tmdb.org/t/p/w342/p.jpg"
        assert artwork.parse_tmdb_gallery(None) == []

    def test_sort_gallery_removes_duplicates_and_keeps_source_order(self) -> None:
        items = [
            artwork._gallery_item("fanart", "https://a/1.jpg", "local"),
            artwork._gallery_item("clearlogo", "https://a/2.png", "fanart.tv"),
            artwork._gallery_item("fanart", "https://a/3.jpg", "tmdb"),
            artwork._gallery_item("fanart", "https://a/1.jpg", "radarr"),  # doublon
        ]
        assert [i["url"] for i in artwork.sort_gallery(items)] == [
            "https://a/2.png",
            "https://a/1.jpg",
            "https://a/3.jpg",
        ]


# ── Images des dossiers des médias ─────────────────────────────────────────

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def media_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Dossiers des médias sur disque : Radarr « /movies/… », Sonarr « /tv/… »
    traduits vers un dossier temporaire (comme /media → /mnt/user/medias)."""
    root = tmp_path / "medias"

    def fake_map(path: str, _service: str) -> str:
        for prefix in ("/movies", "/tv"):
            if path == prefix or path.startswith(prefix + "/"):
                return str(root) + path
        return path

    monkeypatch.setattr(artwork, "map_folder", fake_map)
    dune = root / "movies" / "Dune (2021)"
    (dune / "extrafanart").mkdir(parents=True)
    for name in ("disc.png", "clearlogo.png", "Dune.2021.2160p-clearart.png"):
        (dune / name).write_bytes(PNG)
    (dune / "poster.jpg").write_bytes(b"jpeg")
    (dune / "extrafanart" / "fanart1.jpg").write_bytes(b"jpeg")
    (dune / "Dune.2021.2160p.mkv").write_bytes(b"")
    (dune / "movie.nfo").write_text("<movie/>")
    (root / "tv" / "The Expanse").mkdir(parents=True)
    (root / "tv" / "The Expanse" / "season01-poster.jpg").write_bytes(b"jpeg")
    (tmp_path / "secret.png").write_bytes(PNG)  # hors des dossiers des médias
    return root


class TestLocalFiles:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("poster.jpg", ("poster", "", 0)),
            ("folder.jpg", ("poster", "", 0)),
            ("fanart.jpg", ("fanart", "", 0)),
            ("clearlogo.png", ("clearlogo", "", 0)),
            ("logo.png", ("clearlogo", "", 0)),
            ("disc.png", ("discart", "", 0)),
            ("discart.png", ("discart", "", 0)),
            ("Dune (2021)-disc.png", ("discart", "", 1)),  # Kodi : <vidéo>-disc
            ("Le Comte de Monte-Cristo-poster.jpg", ("poster", "", 1)),
            ("backdrop2.jpg", ("fanart", "", 1)),  # Jellyfin
            ("img_clearart.png", ("clearart", "", 0)),  # scraper NFO d'ArrMada
            ("landscape.jpg", ("landscape", "", 0)),
            ("season01-poster.jpg", ("seasonposter", "1", 0)),
            ("season-specials-banner.jpg", ("seasonbanner", "specials", 0)),
            ("Dune.mkv", None),
            ("movie.nfo", None),
            ("Spider-Man.jpg", None),  # un tiret ne suffit pas
            ("poster.tbn", None),
        ],
    )
    def test_classify(self, name: str, expected: Any) -> None:
        assert artwork.classify_local(name) == expected

    def test_scan_reads_folder_and_extrafanart_only(self, media_folders: Path) -> None:
        entries = artwork.scan_local_folder(media_folders / "movies" / "Dune (2021)")
        assert sorted((e["kind"], e["name"]) for e in entries) == [
            ("clearart", "Dune.2021.2160p-clearart.png"),
            ("clearlogo", "clearlogo.png"),
            ("discart", "disc.png"),
            ("fanart", "extrafanart/fanart1.jpg"),
            ("poster", "poster.jpg"),
        ]
        assert artwork.scan_local_folder(media_folders / "absent") == []

    def test_signed_url_round_trip(self, media_folders: Path) -> None:
        disc = media_folders / "movies" / "Dune (2021)" / "disc.png"
        url = artwork.local_url(str(disc), 123)
        assert url.startswith("/api/artwork/local/") and url.endswith(".png?v=123")
        signature, name = url.split("?")[0].split("/")[-2:]
        assert artwork.resolve_local(signature, name) == disc.resolve()
        # Signature d'un autre fichier, extension changée, charabia : refusés
        assert artwork.resolve_local("0" * 32, name) is None
        assert artwork.resolve_local(signature, name.replace(".png", ".jpg")) is None
        assert artwork.resolve_local(signature, "pas-du-base64!.png") is None

    def test_signed_file_outside_media_folders_is_refused(
        self, media_folders: Path, tmp_path: Path
    ) -> None:
        # Même avec une signature valide (secret par défaut connu), rien hors des médias
        url = artwork.local_url(str(tmp_path / "secret.png"))
        signature, name = url.split("?")[0].split("/")[-2:]
        assert artwork.resolve_local(signature, name) is None

    async def test_refresh_prefers_folder_images_and_serves_them(
        self,
        client: AsyncClient,
        arr_stack: dict,
        artwork_sources: None,
        media_folders: Path,
    ) -> None:
        resp = await client.post("/api/artwork/movie/1/refresh", headers=arr_stack)
        assert resp.json()["status"] == "ok"

        # Médiathèque et fiche : disque et logo du dossier, devant ceux de fanart.tv
        media = (await client.get("/api/media", headers=arr_stack)).json()["items"]
        dune = next(m for m in media if m["title"] == "Dune")
        assert dune["discart_url"].startswith("/api/artwork/local/")
        assert dune["clearlogo_url"].startswith("/api/artwork/local/")
        assert "disc_type" not in dune  # type inconnu pour un fichier local
        detail = (await client.get("/api/media/movie/1", headers=arr_stack)).json()
        assert detail["images"]["discart"] == dune["discart_url"]

        # Galerie : dossier, puis fanart.tv, puis Radarr ; toutes les variantes
        gallery = (await client.get("/api/artwork/movie/1", headers=arr_stack)).json()
        assert gallery["title"] == "Dune" and gallery["status"] == "ok"
        assert gallery["sources"] == ["local", "fanart.tv"]
        discs = [(i["source"], i["url"]) for i in gallery["images"] if i["kind"] == "discart"]
        assert [s for s, _ in discs] == ["local", "fanart.tv", "fanart.tv"]
        posters = [i["source"] for i in gallery["images"] if i["kind"] == "poster"]
        assert posters == ["local", "radarr"]
        assert any(i["name"] == "extrafanart/fanart1.jpg" for i in gallery["images"])

        # L'image du dossier se charge sans jeton (balise <img>, Kodi)
        image = await client.get(dune["discart_url"])
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.content == PNG
        forged = dune["discart_url"].replace("/local/", "/local/0", 1)
        assert (await client.get(forged)).status_code == 404

        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["stored"]["images"] == len(
            [i for i in gallery["images"] if i["source"] != "radarr"]
        )

    async def test_folder_images_need_the_local_network(
        self, arr_stack: dict, media_folders: Path
    ) -> None:
        from httpx import ASGITransport

        from app.main import app

        url = artwork.local_url(str(media_folders / "movies" / "Dune (2021)" / "disc.png"))
        remote = ASGITransport(app=app, client=("203.0.113.9", 4242))  # adresse publique
        async with AsyncClient(transport=remote, base_url="http://test") as outsider:
            assert (await outsider.get(url)).status_code == 403

    async def test_gallery_of_a_title_never_fetched(
        self, client: AsyncClient, arr_stack: dict
    ) -> None:
        gallery = (await client.get("/api/artwork/movie/1", headers=arr_stack)).json()
        assert gallery["status"] == "never"
        assert {i["source"] for i in gallery["images"]} == {"radarr"}  # l'affiche de Radarr
        assert (await client.get("/api/artwork/movie/999", headers=arr_stack)).status_code == 404
        assert (await client.get("/api/artwork/music/1", headers=arr_stack)).status_code == 400

    async def test_titles_fetched_before_the_gallery_are_asked_again(
        self, client: AsyncClient, arr_stack: dict, artwork_sources: None
    ) -> None:
        await client.post("/api/artwork/refresh", headers=arr_stack)
        await artwork.wait_for_refresh()
        # Simule une ligne de la 1.20.0 : servie « ok » mais sans galerie
        async with artwork.session_factory() as db:
            from sqlalchemy import update

            from app.models.artwork import MediaArtwork

            await db.execute(
                update(MediaArtwork)
                .where(MediaArtwork.key == "movie:438631")
                .values(gallery_count=0)
            )
            await db.commit()
        await client.post("/api/artwork/refresh", headers=arr_stack)
        await artwork.wait_for_refresh()
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["total"] == 1  # Dune seulement, les autres sont à jour


class TestFanartKeys:
    async def test_personal_key_alone_is_enough(
        self, client: AsyncClient, arr_stack: dict, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[dict[str, str]] = []

        def dune(params: dict[str, str], _m: Any) -> Any:
            seen.append(params)
            return FANART_DUNE

        monkeypatch.setattr(settings, "FANART_API_KEY", "")
        monkeypatch.setattr(settings, "FANART_CLIENT_KEY", "perso")
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setitem(fake_arr.ROUTES, "webservice.fanart.tv", [(r"/v3/movies/438631", dune)])
        resp = await client.post("/api/artwork/movie/1/refresh", headers=arr_stack)
        assert resp.json()["images"]["discart"].endswith("dune-bd.png")
        assert seen == [{"client_key": "perso"}]
        status = (await client.get("/api/artwork/status", headers=arr_stack)).json()
        assert status["sources"]["fanart"] is True

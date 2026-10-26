"""Logique de l'écran « Accueil » : mise en forme, modèle d'affichage, cache."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

import home_data

NOW = datetime(2026, 10, 10, 20, 30, tzinfo=timezone.utc)
NB = " "
TB = 1024**4


class TestFormatting:
    @pytest.mark.parametrize(
        ("hour", "expected"),
        [
            (0, "Bonne nuit"),
            (4, "Bonne nuit"),
            (5, "Bonjour"),
            (11, "Bonjour"),
            (12, "Bon après-midi"),
            (17, "Bon après-midi"),
            (18, "Bonsoir"),
            (23, "Bonsoir"),
        ],
    )
    def test_greeting(self, hour: int, expected: str) -> None:
        assert home_data.greeting(hour) == expected

    def test_fmt_int(self) -> None:
        assert home_data.fmt_int(3412) == f"3{NB}412"
        assert home_data.fmt_int(1234567) == f"1{NB}234{NB}567"
        assert home_data.fmt_int(None) == "0"
        assert home_data.fmt_int("abc") == "0"

    def test_plural_french_rule(self) -> None:
        assert home_data.plural(0, "film") == "0 film"
        assert home_data.plural(1, "série") == "1 série"
        assert home_data.plural(2, "série") == "2 séries"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("00:10:00", "10 min"),
            ("01:02:03", "1 h 02"),
            ("1.02:15:00", "26 h 15"),
            ("00:00:30", "< 1 min"),
            ("", ""),
            ("bientôt", "bientôt"),
        ],
    )
    def test_fmt_timeleft(self, raw: str, expected: str) -> None:
        assert home_data.fmt_timeleft(raw) == expected

    def test_age_label(self) -> None:
        iso = lambda delta: (NOW - delta).isoformat()  # noqa: E731
        assert home_data.age_label(iso(timedelta(seconds=20)), NOW) == "à l'instant"
        assert home_data.age_label(iso(timedelta(minutes=5)), NOW) == "il y a 5 min"
        assert home_data.age_label(iso(timedelta(hours=3)), NOW) == "il y a 3 h"
        assert home_data.age_label(iso(timedelta(days=2)), NOW) == "il y a 2 j"
        assert home_data.age_label("pas une date", NOW) == ""


class TestAnimationHelpers:
    def test_parse_size_label(self) -> None:
        assert home_data.parse_size_label("42,1 To") == (42.1, "To")
        assert home_data.parse_size_label(f"980{NB}Go") == (980.0, "Go")
        assert home_data.parse_size_label("—") is None

    def test_ease_out_cubic(self) -> None:
        assert home_data.ease_out_cubic(0) == 0
        assert home_data.ease_out_cubic(1) == 1
        assert home_data.ease_out_cubic(0.5) > 0.5  # rapide au début, lent à la fin

    def test_fmt_decimal(self) -> None:
        assert home_data.fmt_decimal(42.13) == "42,1"


class TestBadges:
    def test_premium_movie(self) -> None:
        item = {
            "resolution": 2160,
            "video_dynamic_range": "DV HDR10",
            "audio_codec": "TrueHD Atmos",
        }
        assert home_data.badges(item) == ["4K", "DV", "Atmos"]

    def test_resolution_variants(self) -> None:
        assert home_data.resolution_badge({"resolution": "3840x2160"}) == "4K"
        assert home_data.resolution_badge({"quality": "Bluray-1080p"}) == "1080p"
        assert home_data.resolution_badge({"resolution": 480}) == "SD"
        assert home_data.resolution_badge({}) == ""

    def test_hdr_and_audio(self) -> None:
        assert home_data.hdr_badge({"video_dynamic_range_type": "HDR10Plus"}) == "HDR10+"
        assert home_data.hdr_badge({"video_dynamic_range": "HDR"}) == "HDR"
        assert home_data.audio_badge({"audio_codec": "DTS-HD MA"}) == "DTS-HD"
        assert home_data.audio_badge({"audio_codec": "EAC3", "audio_channels": 5.1}) == "5.1"
        assert home_data.audio_badge({"audio_codec": "AAC", "audio_channels": 2}) == ""


DASHBOARD = {
    "stats": {
        "movies_count": 3412,
        "series_count": 186,
        "episodes_count": 12044,
        "total_size_human": "42,1 To",
    },
    "disks": [
        # Même disque déclaré par Radarr ET Sonarr : compté une seule fois.
        {"path": "/mnt/user/media", "total_bytes": 60 * TB, "free_bytes": 13 * TB},
        {"path": "/mnt/user/media", "total_bytes": 60 * TB, "free_bytes": 13 * TB},
    ],
    "downloads": [
        {
            "title": f"Release {i}",
            "progress": 10 * i + 0.4,
            "timeleft": "00:12:00",
            "service": "radarr",
        }
        for i in range(1, 5)
    ],
    "downloads_count": 4,
    "services": [
        {"name": "Sonarr", "is_enabled": True},
        {"name": "Jellyseerr", "is_enabled": False},
        {"name": "radarr", "is_enabled": True},
    ],
}

RECENT = [
    {
        "external_id": "1",
        "type": "movie",
        "title": "Dune",
        "year": 2021,
        "resolution": 2160,
        "video_dynamic_range": "DV",
        "audio_codec": "TrueHD Atmos",
        "poster_url": "p.jpg",
        "fanart_url": "f.jpg",
        "clearlogo_url": "l.png",
        "overview": "Arrakis.",
    },
    {
        "external_id": "10",
        "type": "series",
        "title": "The Expanse",
        "year": None,
        "tmdb_id": 280619,
    },
]


class TestBuildModel:
    def test_full_model(self) -> None:
        model = home_data.build_model(DASHBOARD, RECENT, NOW)
        assert model["version"] == home_data.CACHE_VERSION
        assert model["summary"] == (
            f"3{NB}412 films · 186 séries · 42,1 To · 4 téléchargements en cours"
        )
        kpis = model["kpis"]
        assert kpis["movies"] == f"3{NB}412"
        assert kpis["series_hint"] == f"12{NB}044 épisodes"
        assert kpis["storage_pct"] == 78  # (60 - 13) / 60, disque compté une fois
        assert kpis["storage_hint"] == f"78 % · 13,0{NB}To libres"
        assert kpis["downloads"] == "4"
        assert kpis["downloads_hint"] == "téléchargements"
        # Valeurs brutes, animées par la fenêtre (compteurs qui défilent)
        assert model["kpis_raw"] == {
            "movies": 3412,
            "series": 186,
            "downloads": 4,
            "storage": 42.1,
            "storage_unit": "To",
            "storage_pct": 78,
        }

        assert [d["title"] for d in model["downloads"]] == ["Release 1", "Release 2", "Release 3"]
        assert model["downloads"][0]["meta"] == "10 % · 12 min · Radarr"
        assert model["downloads_more"] == 1

        # Services actifs d'abord, puis ordre alphabétique sans tenir compte de la casse.
        assert [s["name"] for s in model["services"]] == ["radarr", "Sonarr", "Jellyseerr"]
        assert model["services_active"] == 2

        dune, expanse = model["recent"]
        assert dune["id"] == "movie:1"
        assert dune["type"] == "movie"
        assert dune["meta"] == "2021 · Film · 4K · DV · Atmos"
        assert dune["badge"] == "4K"
        assert (dune["poster"], dune["fanart"], dune["clearlogo"]) == ("p.jpg", "f.jpg", "l.png")
        assert (dune["tmdb_id"], dune["tvdb_id"]) == ("", "")  # Radarr n'a pas fourni d'ID
        # Série : Sonarr range l'ID TVDB dans « tmdb_id », il doit ressortir en tvdb_id.
        assert (expanse["tmdb_id"], expanse["tvdb_id"]) == ("", "280619")
        assert expanse["id"] == "series:10"
        assert expanse["type"] == "tvshow"
        assert expanse["meta"] == "Série"
        assert expanse["poster"] == ""

    def test_empty_server_answer(self) -> None:
        """Backend vide ou réponse partielle : pas de plantage, valeurs neutres."""
        model = home_data.build_model({}, [], NOW)
        assert model["kpis"]["movies"] == "0"
        assert model["kpis"]["storage"] == "—"
        assert model["kpis"]["storage_hint"] == "médiathèque"
        assert model["kpis"]["downloads_hint"] == "file vide"
        assert model["downloads"] == [] and model["services"] == [] and model["recent"] == []

    def test_single_download_singular(self) -> None:
        model = home_data.build_model({"downloads": [{"title": "x", "progress": 50}]}, [], NOW)
        assert model["kpis"]["downloads_hint"] == "téléchargement"
        assert model["summary"].endswith("1 téléchargement en cours")


class TestLibraryMatch:
    MOVIES = [
        {"movieid": 1, "title": "Dune", "year": 1984},
        {"movieid": 2, "title": "Dune", "year": 2021},
        {"movieid": 3, "title": "Dune : Deuxième partie", "year": 2024},
    ]

    def test_same_title_and_year(self) -> None:
        assert home_data.pick_library_match(self.MOVIES, "Dune", 2021, "movieid") == 2
        assert home_data.pick_library_match(self.MOVIES, "dune", 1984, "movieid") == 1

    def test_one_year_tolerance_and_punctuation(self) -> None:
        assert (
            home_data.pick_library_match(self.MOVIES, "Dune: Deuxième Partie", 2025, "movieid") == 3
        )

    def test_ambiguous_or_missing_returns_none(self) -> None:
        # Deux « Dune » et une année qui ne colle à aucun : on ne devine pas.
        assert home_data.pick_library_match(self.MOVIES, "Dune", 2030, "movieid") is None
        assert home_data.pick_library_match(self.MOVIES, "Interstellar", 2014, "movieid") is None

    def test_unique_id_wins_over_title(self) -> None:
        """Kodi en français, Radarr en anglais : l'ID TMDB fait le lien."""
        movies = [
            {
                "movieid": 9,
                "title": "Dune : Deuxième partie",
                "year": 2024,
                "uniqueid": {"tmdb": "693134"},
            }
        ]
        assert (
            home_data.pick_library_match(
                movies, "Dune: Part Two", 2024, "movieid", "tmdb", "693134"
            )
            == 9
        )
        assert (
            home_data.pick_library_match(movies, "Dune: Part Two", 2024, "movieid", "tmdb", "1")
            is None
        )

    def test_library_filter(self) -> None:
        by_year = home_data.library_filter("Dune", 2021)
        assert [f["value"] for f in by_year["or"]] == ["2020", "2021", "2022"]
        assert home_data.library_filter("Dune", 0) == {
            "field": "title",
            "operator": "contains",
            "value": "Dune",
        }

    def test_single_candidate_without_year(self) -> None:
        shows = [{"tvshowid": 7, "title": "The Expanse", "year": 2015}]
        assert home_data.pick_library_match(shows, "The Expanse", 0, "tvshowid") == 7


class TestCache:
    def test_roundtrip(self, tmp_path) -> None:
        model = home_data.build_model(DASHBOARD, RECENT, NOW)
        home_data.save_cache(str(tmp_path / "cache"), model)
        assert home_data.load_cache(str(tmp_path / "cache")) == model
        # Écriture atomique : aucun fichier temporaire ne traîne.
        assert os.listdir(tmp_path / "cache") == [home_data.CACHE_FILE]

    def test_missing_corrupt_or_old_format(self, tmp_path) -> None:
        assert home_data.load_cache(str(tmp_path)) is None
        cache_file = tmp_path / home_data.CACHE_FILE
        cache_file.write_text("{ tronqué", encoding="utf-8")
        assert home_data.load_cache(str(tmp_path)) is None
        cache_file.write_text(json.dumps({"version": 0}), encoding="utf-8")
        assert home_data.load_cache(str(tmp_path)) is None


class TestDescribeError:
    """Écran d'erreur : « TV refusée » n'est pas « serveur injoignable »."""

    def test_refused_tv_is_not_unreachable(self) -> None:
        for code in (401, 403):
            described = home_data.describe_error(
                {"status": "error", "message": "Not authenticated", "code": code}
            )
            assert described["title"] == "Cette TV n'est pas autorisée"
            assert "Appairer cette TV" in described["action"]
            assert "Appairer cette TV" in described["hint"]

    def test_network_errors_and_server_errors_are_unreachable(self) -> None:
        for response in (
            {"status": "error", "message": "Connexion impossible à http://nas:8420 (refused)."},
            {"status": "error", "message": "Internal Server Error", "code": 500},
            None,
            {},
        ):
            described = home_data.describe_error(response)
            assert described["title"] == "ArrMada est injoignable"
            assert described["short"] == "Serveur injoignable"
            assert "8420" in described["hint"]

    def test_unconfigured_server_is_neither_down_nor_refused(self) -> None:
        """Aucune adresse réglée : on dit quoi faire, pas « injoignable » (1.25.1)."""
        described = home_data.describe_error(
            {"status": "error", "reason": "not_configured", "message": "…"}
        )
        assert described["title"] == "Serveur ArrMada non configuré"
        assert "Trouver le serveur ArrMada" in described["action"]
        assert "8420" in described["hint"]

    def test_texts_use_only_glyphs_of_the_silvo_font(self) -> None:
        """Ces textes s'affichent tels quels : pas de « → » (carré vide, vu sur le banc)."""
        missing = {"→", "★", "✓", "✔", "▶", "⏸", "●"}
        errors = (home_data.ERROR_AUTH, home_data.ERROR_DOWN, home_data.ERROR_UNCONFIGURED)
        for described in errors:
            for text in described.values():
                assert not missing & set(text), text

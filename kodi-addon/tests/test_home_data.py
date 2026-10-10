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
    {"external_id": "10", "type": "series", "title": "The Expanse", "year": None},
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

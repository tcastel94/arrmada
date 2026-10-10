"""Tests des fonctions pures (formatage, normalisation, détection)."""

from __future__ import annotations

import pytest

from app.services.docker_logs import _classify, _demux, _parse_json_object
from app.services.kodi import _resolution_label, _secs, _tech_details
from app.services.media_aggregator import _calc_progress, _normalise_movie, _normalise_series
from app.services.media_detail import _extract_images, _format_file_info, _key_crew
from app.services.trash_profiles import _categorize_cf
from app.utils.helpers import format_bytes, format_duration_ms, normalize_title
from tests import fake_arr


class TestFormatBytes:
    """Unités françaises + virgule décimale, alignées sur l'interface."""

    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (None, "0 o"),
            (0, "0 o"),
            (512, "512,0 o"),
            (1536, "1,5 Ko"),
            (int(3.4 * 1024**4), "3,4 To"),
            (1024**6, "1024,0 Po"),  # plafonné à l'unité la plus grande
        ],
    )
    def test_units(self, size: int | None, expected: str) -> None:
        assert format_bytes(size) == expected


def test_format_duration_ms() -> None:
    assert format_duration_ms(None) == "N/A"
    assert format_duration_ms(250) == "250ms"
    assert format_duration_ms(1500) == "1.5s"


def test_normalize_title() -> None:
    assert normalize_title("  Amélie  Poulain ! ") == "amelie poulain"
    assert normalize_title("Spider-Man: No Way Home") == "spiderman no way home"


class TestNormalisation:
    def test_movie_with_file(self) -> None:
        m = _normalise_movie(fake_arr.MOVIES[0], "Radarr")
        assert m["type"] == "movie"
        assert m["quality"] == "Bluray-2160p"
        assert m["size_bytes"] == fake_arr.MOVIES[0]["movieFile"]["size"]
        assert m["rating"] == 7.8

    def test_movie_without_file(self) -> None:
        m = _normalise_movie(fake_arr.MOVIES[1], "Radarr")
        assert m["quality"] is None
        assert m["has_file"] is False
        assert m["poster_url"] is None

    def test_series_profile_name(self) -> None:
        s = _normalise_series(fake_arr.SERIES[0], "Sonarr", {8: "WEB-1080p"})
        assert s["quality"] == "WEB-1080p"
        assert s["tmdb_id"] == 280619  # Sonarr est indexé sur TVDB
        assert (s["episodes_have"], s["episodes_total"]) == (3, 4)

    def test_series_unknown_profile(self) -> None:
        s = _normalise_series({"id": 1, "qualityProfileId": 99}, "Sonarr", {})
        assert s["quality"] is None
        assert s["has_file"] is False

    @pytest.mark.parametrize(
        ("item", "expected"),
        [({"size": 100, "sizeleft": 25}, 75.0), ({"size": 0, "sizeleft": 0}, 0.0), ({}, 0.0)],
    )
    def test_progress(self, item: dict, expected: float) -> None:
        assert _calc_progress(item) == expected


class TestMediaDetailHelpers:
    def test_key_crew_filters_and_orders(self) -> None:
        crew = [
            {"name": "Compo", "job": "Original Music Composer"},
            {"name": "Grip", "job": "Key Grip"},
            {"name": "Réal", "job": "Director"},
            {"name": "Réal", "job": "Director"},
            {"name": "Ancien", "type": "writer"},  # ancien format sans job
        ]
        names = [p["name"] for p in _key_crew(crew)]
        assert names[0] == "Réal"
        assert names.count("Réal") == 1
        assert "Grip" not in names
        assert "Ancien" in names

    def test_key_crew_is_capped(self) -> None:
        crew = [{"name": f"P{i}", "job": "Writer"} for i in range(30)]
        assert len(_key_crew(crew)) == 10

    def test_extract_images(self) -> None:
        imgs = _extract_images(fake_arr.MOVIES[0])
        assert imgs["poster"] == "https://img.test/dune.jpg"
        assert imgs["fanart"] == "https://img.test/dune-fanart.jpg"
        assert imgs["banner"] is None
        assert imgs["clearlogo"] is None  # pas de logo dans les données de test

    def test_format_file_info(self) -> None:
        info = _format_file_info(fake_arr.MOVIES[0]["movieFile"])
        assert info["quality"] == "Bluray-2160p"
        assert info["video_dynamic_range_type"] == "HDR10"
        assert info["languages"] == ["English"]


class TestKodiHelpers:
    @pytest.mark.parametrize(
        ("w", "h", "label"),
        [
            (3840, 2160, "4K"),
            (3840, 1600, "4K"),  # scope 2.39:1 : la largeur fait foi
            (1920, 1080, "1080p"),
            (1280, 720, "720p"),
            (720, 576, "576p"),
            (640, 360, "SD"),
            (None, None, None),
        ],
    )
    def test_resolution_label(self, w: int | None, h: int | None, label: str | None) -> None:
        assert _resolution_label(w, h) == label

    def test_secs(self) -> None:
        assert _secs({"hours": 1, "minutes": 2, "seconds": 3}) == 3723
        assert _secs(None) == 0

    def test_tech_details(self) -> None:
        details = _tech_details(
            {
                "streamdetails": {
                    "video": [
                        {"width": 3840, "height": 2160, "codec": "hevc", "hdrtype": "dolbyvision"}
                    ],
                    "audio": [{"codec": "truehd", "channels": 8, "language": "eng"}],
                    "subtitle": [{"language": "fre"}, {"language": "eng"}],
                }
            }
        )
        assert details == {
            "resolution": "4K",
            "video_codec": "HEVC",
            "hdr": "dolbyvision",
            "audio_codec": "TRUEHD",
            "audio_channels": 8,
            "audio_language": "eng",
            "subtitle_count": 2,
        }

    def test_tech_details_empty(self) -> None:
        assert _tech_details({})["resolution"] is None


def test_categorize_cf_returns_label() -> None:
    assert isinstance(_categorize_cf("x265 (HD)"), str)
    assert isinstance(_categorize_cf("Unknown Thing"), str)


class TestDockerLogs:
    """Classification et décodage des logs Docker (page Système → Docker)."""

    @pytest.mark.parametrize(
        ("line", "level"),
        [
            ("[Error] Couldn't import episode", "error"),
            ("2026-10-10 12:00:00 CRITICAL disk full", "error"),
            ("[Warn] Indexer is slow", "warning"),
            ("::warning:: deprecated option", "warning"),
            ("[Info] Import complete", "info"),
            ("just some output", "other"),
        ],
    )
    def test_classify(self, line: str, level: str) -> None:
        assert _classify(line) == level

    def test_demux_framed_stream(self) -> None:
        # Trame Docker non-TTY : [stream][0,0,0][taille big-endian][données]
        frame = bytes([1, 0, 0, 0]) + (5).to_bytes(4, "big") + b"hello"
        frame2 = bytes([2, 0, 0, 0]) + (3).to_bytes(4, "big") + b"err"
        assert _demux(frame + frame2) == b"helloerr"

    def test_demux_tty_untouched(self) -> None:
        assert _demux(b"plain tty output\n") == b"plain tty output\n"

    def test_parse_llm_json(self) -> None:
        assert _parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
        assert _parse_json_object('Voici : {"b": [1, 2]} fin') == {"b": [1, 2]}

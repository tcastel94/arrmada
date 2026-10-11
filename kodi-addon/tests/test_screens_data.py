"""Logique des écrans de la phase 2 : fiche média, téléchargements, Salon."""

from __future__ import annotations

import pytest

import screens_data as sd

NB = " "
GB = 1024**3

MOVIE = {
    "id": 1,
    "title": "Dune : Deuxième partie",
    "year": 2024,
    "runtime": 166,
    "certification": "PG-13",
    "genres": ["Science Fiction", "Adventure", "Drama", "Action"],
    "overview": "Paul Atréides s'unit aux Fremen.",
    "has_file": True,
    "tmdb_id": 693134,
    "youtube_trailer_id": "Way9Dexny3w",
    "ratings": {"tmdb": 8.234, "imdb": 8.6, "rotten_tomatoes": 92},
    "images": {"poster": "p.jpg", "fanart": "f.jpg", "clearlogo": "l.png"},
    "file": {
        "quality": "Remux-2160p",
        "resolution": 2160,
        "size_bytes": 64 * GB,
        "video_codec": "HEVC",
        "video_dynamic_range_type": "DV HDR10",
        "audio_codec": "TrueHD Atmos",
        "audio_channels": 7.1,
        "audio_languages": "Français / Anglais",
        "release_group": "FraMeSToR",
    },
    "cast": [
        {"name": "Timothée Chalamet", "character": "Paul Atréides", "photo": "tc.jpg"},
        {"name": "Zendaya", "character": "Chani"},
    ],
    "crew": [
        {"name": "Denis Villeneuve", "job": "Director"},
        {"name": "Denis Villeneuve", "job": "Screenplay"},
        {"name": "Hans Zimmer", "job": "Original Music Composer"},
    ],
    "subtitles": [{"language": "Français"}, {"language": "Anglais"}, {"language": "Français"}],
}

SERIES = {
    "id": 10,
    "title": "Severance",
    "year": 2022,
    "runtime": 55,
    "network": "Apple TV+",
    "genres": ["Drama", "Mystery"],
    "tvdb_id": 371980,
    "episodes_have": 15,
    "total_episodes": 19,
    "ratings": {"value": 8.7},
    "images": {"poster": "s.jpg"},
    "seasons": [
        {"season_number": 0, "episode_count": 2, "episodes_have": 0},
        {"season_number": 1, "episode_count": 9, "episodes_have": 9},
        {"season_number": 2, "episode_count": 10, "episodes_have": 6},
    ],
}


class TestFormatting:
    @pytest.mark.parametrize(
        ("minutes", "expected"),
        [(166, "2 h 46"), (48, "48 min"), (60, "1 h 00"), (0, ""), (None, "")],
    )
    def test_runtime(self, minutes, expected) -> None:
        assert sd.fmt_runtime(minutes) == expected

    @pytest.mark.parametrize(
        ("pct", "expected"),
        [
            (0, "bar-000"),
            (61.7, "bar-062"),
            (99.4, "bar-100"),
            (150, "bar-100"),
            (-3, "bar-000"),
            ("x", "bar-000"),
        ],
    )
    def test_bar_texture(self, pct, expected) -> None:
        assert sd.bar_texture(pct) == expected

    def test_genre_fr(self) -> None:
        assert sd.genre_fr("Science Fiction") == "Science-fiction"
        assert sd.genre_fr("Inconnu") == "Inconnu"

    def test_speed(self) -> None:
        assert sd.fmt_speed(4.4 * 1024**2) == f"4,4{NB}Mo/s"
        assert sd.fmt_speed(0) == ""


class TestDetail:
    def test_movie(self) -> None:
        d = sd.build_detail(MOVIE, "movie")
        assert d["kind"] == "movie"
        assert d["meta"] == "2024 · 2 h 46 · PG-13 · Science-fiction, Aventure, Drame"
        assert d["notes"] == "TMDB 8,2   IMDb 8,6   Rotten Tomatoes 92 %"
        assert d["badges"] == ["4K", "DV", "Atmos", "Remux"]
        assert d["status"] == "Disponible"
        assert d["file_lines"][0] == f"Remux-2160p · 64,0{NB}Go"
        assert d["file_lines"][1] == "Vidéo : HEVC · DV HDR10"
        assert d["file_lines"][2] == "Audio : TrueHD Atmos 7.1 · Français / Anglais"
        assert d["subtitles"] == "Anglais, Français"  # dédoublonnés, triés
        assert d["crew"] == (
            "Réalisation : Denis Villeneuve · Scénario : Denis Villeneuve · Musique : Hans Zimmer"
        )
        assert d["cast"][0] == {
            "name": "Timothée Chalamet",
            "role": "Paul Atréides",
            "photo": "tc.jpg",
        }
        assert (d["tmdb_id"], d["tvdb_id"], d["trailer"]) == ("693134", "", "Way9Dexny3w")
        assert (d["poster"], d["fanart"], d["clearlogo"]) == ("p.jpg", "f.jpg", "l.png")
        assert (d["audio_codec"], d["audio_channels"]) == ("TrueHD Atmos", 7.1)

    def test_series(self) -> None:
        d = sd.build_detail(SERIES, "series")
        assert d["kind"] == "tvshow"
        assert d["meta"] == "2022 · 55 min · Apple TV+ · Drame, Mystère"
        assert d["notes"] == "Note 8,7"
        assert d["status"] == "15/19 épisodes"
        assert d["tvdb_id"] == "371980" and d["tmdb_id"] == ""
        assert [s["label"] for s in d["seasons"]] == ["Épisodes spéciaux", "Saison 1", "Saison 2"]
        assert d["seasons"][2] == {
            "number": 2,  # l'écran Série s'ouvre sur cette saison (ADR-004)
            "label": "Saison 2",
            "progress": "6/10 épisodes",
            "pct": 60,
            "bar": "bar-060",
        }
        # Aucun épisode détaillé : pas de badges, juste le résumé de la série
        assert d["badges"] == [] and d["subtitles"] == "aucun"
        assert d["file_lines"] == ["15 épisodes sur le NAS"]

    def test_series_describes_latest_episode_file(self) -> None:
        """Sonarr n'a pas de « fichier » de série : on résume la série, puis le
        dernier épisode présent (plus haute saison, plus haut épisode)."""

        def ep(number: int, quality: str) -> dict:
            return {
                "episode_number": number,
                "has_file": True,
                "file": {
                    "quality": quality,
                    "resolution": 2160,
                    "size_bytes": 4 * GB,
                    "video_codec": "HEVC",
                    "video_dynamic_range_type": "DV HDR10",
                    "audio_codec": "EAC3 Atmos",
                    "audio_channels": 6,
                    "audio_languages": "Anglais",
                    "release_group": "NTb",
                },
            }

        series = dict(
            SERIES,
            status="continuing",
            size_on_disk=61 * GB,
            seasons=[
                {"season_number": 1, "episodes": [ep(1, "WEBDL-1080p"), ep(2, "WEBDL-1080p")]},
                {
                    "season_number": 2,
                    "episodes": [
                        ep(6, "WEBDL-2160p"),
                        {"episode_number": 7, "has_file": False, "file": None},
                    ],
                },
            ],
        )
        d = sd.build_detail(series, "series")
        assert d["notes"] == "Note 8,7   Série en cours de diffusion"
        assert d["file_lines"] == [
            f"15 épisodes sur le NAS · 61,0{NB}Go",
            f"Dernier : S02E06 · WEBDL-2160p · 4,0{NB}Go",
            "Vidéo : HEVC · DV HDR10",
            "Audio : EAC3 Atmos 5.1 · Anglais",
        ]
        assert d["badges"] == ["4K", "DV", "Atmos", "WEB-DL"]
        # Le préréglage de l'ampli suit l'audio du dernier épisode
        assert (d["audio_codec"], d["audio_channels"]) == ("EAC3 Atmos", 6)

    def test_missing_movie_minimal(self) -> None:
        d = sd.build_detail({"title": "X", "has_file": False}, "movie")
        assert d["status"] == "Manquant"
        assert d["overview"] == "Aucun synopsis."
        assert d["meta"] == "" and d["notes"] == ""


QUEUE = [
    {
        "id": 501,
        "service_type": "radarr",
        "title": "Oppenheimer.2023.1080p.WEB",
        "status": "downloading",
        "tracked_state": "downloading",
        "progress": 60.0,
        "size_bytes": 10 * GB,
        "size_left_bytes": 4 * GB,
        "time_left": "00:10:00",
        "download_client": "SABnzbd",
        "quality": "WEBDL-1080p",
        "indexer": "NZBgeek",
        "movie_id": 2,
    },
    {
        "id": 7,
        "service_type": "sonarr",
        "title": "Silo.S02E05",
        "status": "paused",
        "progress": 2,
        "size_bytes": GB,
        "size_left_bytes": GB,
    },
    {
        "id": 8,
        "service_type": "sonarr",
        "title": "Broken",
        "status": "warning",
        "error": "Import échoué",
        "progress": 100,
    },
]


class TestDownloads:
    def test_first_pass_has_no_speed(self) -> None:
        model, state = sd.build_downloads(QUEUE, {}, now=100.0)
        first = model["rows"][0]
        assert first["key"] == "radarr:501"
        assert first["pct"] == "60 %" and first["bar"] == "bar-060"
        assert first["sizes"] == f"6,0{NB}Go / 10,0{NB}Go"
        assert first["eta"] == "10 min"
        assert first["meta"] == "Radarr · SABnzbd · WEBDL-1080p · NZBgeek"
        assert (first["status"], first["family"]) == ("En cours", "active")
        assert (first["kind"], first["arr_id"]) == ("movie", 2)
        assert first["speed"] == ""
        assert state["radarr:501"] == (100.0, 4 * GB)
        paused, broken = model["rows"][1], model["rows"][2]
        assert (paused["status"], paused["family"], paused["kind"]) == (
            "En pause",
            "paused",
            "tvshow",
        )
        assert (broken["status"], broken["family"], broken["detail"]) == (
            "Erreur",
            "error",
            "Import échoué",
        )
        assert model["summary"] == "3 dans la file · 1 en cours · 1 en pause"

    def test_speed_estimated_from_previous_pass(self) -> None:
        _, state = sd.build_downloads(QUEUE, {}, now=100.0)
        moved = [dict(QUEUE[0], size_left_bytes=4 * GB - 50 * 1024**2)]  # 50 Mo en 10 s
        model, _ = sd.build_downloads(moved, state, now=110.0)
        assert model["rows"][0]["speed"] == f"5,0{NB}Mo/s"
        assert model["summary"] == f"1 dans la file · 1 en cours · 5,0{NB}Mo/s"

    def test_sabnzbd_paused_wins_over_tracked_state(self) -> None:
        """SABnzbd en pause : *arr garde tracked_state « downloading » mais
        status « paused ». La ligne doit dire « En pause », pas « En cours »."""
        item = dict(QUEUE[0], status="paused", tracked_state="downloading")
        model, _ = sd.build_downloads([item, dict(item, id=502)], {}, now=1.0)
        assert {(r["status"], r["family"]) for r in model["rows"]} == {("En pause", "paused")}
        assert model["summary"] == "2 dans la file · 2 en pause"

    def test_import_step_wins_once_downloaded(self) -> None:
        item = dict(QUEUE[0], status="completed", tracked_state="importPending")
        assert sd.download_status(item) == ("Import en attente", "import")
        assert sd.download_status({"status": "queued", "tracked_state": "downloading"}) == (
            "En attente",
            "queued",
        )

    def test_empty(self) -> None:
        model, state = sd.build_downloads([], {}, now=1.0)
        assert model == {"rows": [], "summary": "File vide"} and state == {}


class TestSalon:
    def test_online_amp(self) -> None:
        state = {
            "devices": [
                {
                    "name": "RX-A2080",
                    "online": True,
                    "power": "on",
                    "volume_pct": 42,
                    "actual_db": -32.5,
                    "mute": False,
                    "input": "hdmi1",
                    "sound_program": "surr_decoder",
                }
            ]
        }
        profiles = {"salon": {"name": "Salon"}, "cinema": {"name": "Salle de cinéma"}}
        s = sd.build_salon(state, profiles)
        assert (s["configured"], s["online"], s["is_on"]) == (True, True, True)
        assert (s["power"], s["volume"], s["volume_bar"]) == ("Allumé", "42 %", "bar-042")
        assert s["db"] == "−32,5 dB"
        assert (s["input"], s["program"]) == ("HDMI 1", "Surround Decoder")
        assert [p["name"] for p in s["presets"]] == ["Salon", "Salle de cinéma"]

    def test_no_amp(self) -> None:
        s = sd.build_salon({"devices": []}, {})
        assert s["configured"] is False and s["power"] == "Hors ligne" and s["presets"] == []

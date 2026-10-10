"""Listes natives et widgets (ADR-003 § 2) : conversion des données en entrées."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import catalog_data as cd

PARIS = timezone(timedelta(hours=2))  # heure d'été, pour des tests déterministes
NOW = datetime(2026, 10, 10, 18, 0)  # samedi 10 octobre 2026, 18 h (heure locale)

MOVIE = {
    "external_id": "12",
    "tmdb_id": 693134,
    "title": "Dune : Deuxième partie",
    "type": "movie",
    "year": 2024,
    "genres": ["Science Fiction", "Adventure"],
    "resolution": 2160,
    "video_dynamic_range": "DV HDR10",
    "audio_codec": "TrueHD Atmos",
    "audio_channels": 7.1,
    "poster_url": "p.jpg",
    "fanart_url": "f.jpg",
    "clearlogo_url": "l.png",
    "has_file": True,
    "rating": 8.3,
    "runtime": 166,
    "overview": "Paul s'unit aux Fremen.",
}
SERIES = {
    "external_id": "7",
    "tmdb_id": 371980,
    "title": "Severance",
    "type": "series",
    "year": 2022,
}


class TestDates:
    def test_parse_utc_to_local(self) -> None:
        assert cd.parse_when("2026-10-11T19:00:00Z", PARIS) == datetime(2026, 10, 11, 21, 0)
        # Heure sans fuseau venant du serveur = UTC
        assert cd.parse_when("2026-10-11T19:00:00", PARIS) == datetime(2026, 10, 11, 21, 0)
        assert cd.parse_when("2026-10-12", PARIS) == datetime(2026, 10, 12)
        assert cd.parse_when("", PARIS) is None and cd.parse_when("n'importe quoi") is None

    def test_days(self) -> None:
        today = date(2026, 10, 10)
        assert cd.fmt_day(datetime(2026, 10, 10, 9), today) == "Aujourd'hui"
        assert cd.fmt_day(datetime(2026, 10, 11), today) == "Demain"
        assert cd.fmt_day(datetime(2026, 10, 9), today) == "Hier"
        assert cd.fmt_day(datetime(2026, 10, 15), today) == "jeu. 15 oct."
        assert cd.fmt_when(datetime(2026, 10, 11, 21, 5), today) == "Demain · 21:05"
        assert cd.fmt_when(datetime(2026, 10, 12), today) == "lun. 12 oct."

    def test_ago(self) -> None:
        assert cd.fmt_ago(NOW - timedelta(seconds=20), NOW) == "à l'instant"
        assert cd.fmt_ago(NOW - timedelta(minutes=5), NOW) == "il y a 5 min"
        assert cd.fmt_ago(NOW - timedelta(hours=3), NOW) == "il y a 3 h"
        assert cd.fmt_ago(NOW - timedelta(days=1, hours=1), NOW) == "Hier"


class TestMedia:
    def test_recent_movie(self) -> None:
        (entry,) = cd.entries_media([MOVIE])
        assert entry["label"] == "Dune : Deuxième partie"
        assert entry["label2"] == "2024 · Film · 4K · DV · Atmos"
        assert entry["info"]["mediatype"] == "movie" and entry["info"]["duration"] == 166 * 60
        assert entry["info"]["genres"] == ["Science-fiction", "Aventure"]
        assert entry["ids"] == {"tmdb": "693134"}
        assert entry["art"] == {
            "poster": "p.jpg",
            "thumb": "p.jpg",
            "icon": "p.jpg",
            "fanart": "f.jpg",
            "clearlogo": "l.png",
        }
        assert entry["action"]["action"] == "detail"
        assert (entry["action"]["kind"], entry["action"]["arr_id"]) == ("movie", "12")
        assert entry["context"] == ["play", "detail", "upgrade"]
        assert entry["props"]["badge"] == "4K"

    def test_series_uses_tvdb(self) -> None:
        (entry,) = cd.entries_media([SERIES])
        assert entry["ids"] == {"tvdb": "371980"}
        assert entry["action"]["kind"] == "tvshow" and entry["action"]["tvdb_id"] == "371980"

    def test_missing(self) -> None:
        (entry,) = cd.entries_media([dict(MOVIE, has_file=False)], missing=True)
        assert entry["label2"] == "2024 · Film · manquant"
        assert entry["context"] == ["detail", "upgrade"]  # rien à lire


class TestCalendar:
    PAYLOAD = {
        "items": [
            {
                "type": "movie",
                "title": "Wicked",
                "air_date": "2026-10-15",
                "release_type": "digital",
                "movie_id": 9,
                "poster_url": "w.jpg",
            },
            {
                "type": "episode",
                "title": "Severance",
                "subtitle": "Cold Harbor",
                "label": "S02E10",
                "season": 2,
                "episode": 10,
                "air_date": "2026-10-11T01:00:00Z",
                "series_id": 7,
                "network": "Apple TV+",
            },
            {"type": "episode", "title": "Sans date", "air_date": None},
        ]
    }

    def test_sorted_and_labelled(self) -> None:
        episode, movie = cd.entries_calendar(self.PAYLOAD, NOW, PARIS)
        assert episode["label"] == "Severance · S02E10"
        assert episode["label2"] == "Demain · 03:00 · Cold Harbor · Apple TV+"
        assert episode["info"]["mediatype"] == "episode"
        assert (episode["info"]["season"], episode["info"]["episode"]) == (2, 10)
        assert episode["action"]["kind"] == "tvshow" and episode["action"]["arr_id"] == "7"
        assert movie["label2"] == "jeu. 15 oct. · sortie en numérique"
        assert movie["info"]["premiered"] == "2026-10-15"


class TestDiscover:
    PAYLOAD = {
        "because_you_have": [
            {
                "base_title": "Dune",
                "recommendations": [
                    {
                        "tmdb_id": 1,
                        "title": "Arrival",
                        "type": "movie",
                        "year": "2016",
                        "rating": 7.6,
                    },
                    {"tmdb_id": 2, "title": "Déjà là", "type": "movie", "in_library": True},
                ],
            }
        ],
        "trending_movies": [
            {"tmdb_id": 1, "title": "Arrival", "type": "movie"},  # doublon
            {"tmdb_id": 3, "title": "Oppenheimer", "type": "movie", "in_library": True},
        ],
        "trending_series": [{"tmdb_id": 4, "title": "Shogun", "type": "series", "year": "2024"}],
    }

    def test_for_you_dedupes_and_skips_library(self) -> None:
        entries = cd.entries_foryou(self.PAYLOAD)
        assert [e["label"] for e in entries] == ["Arrival", "Shogun"]
        assert entries[0]["label2"] == "2016 · Film · note 7,6 · parce que tu as Dune"
        assert entries[1]["label2"] == "2024 · Série · tendance de la semaine"
        action = entries[0]["action"]
        assert (action["action"], action["type"], action["in_library"]) == (
            "media_details",
            "movie",
            "0",
        )

    def test_trending_keeps_library_items(self) -> None:
        entries = cd.entries_trending(self.PAYLOAD, "movie")
        assert [e["props"]["in_library"] for e in entries] == ["", "1"]
        assert entries[1]["label2"].endswith("déjà dans la médiathèque")
        assert cd.entries_trending(None, "movie") == []


def test_downloads() -> None:
    payload = {
        "items": [
            {
                "id": 1,
                "service_type": "radarr",
                "title": "Gladiator.II.2160p",
                "status": "downloading",
                "progress": 62,
                "size_bytes": 100,
                "size_left_bytes": 38,
                "time_left": "00:12:00",
                "movie_id": 5,
            }
        ]
    }
    (entry,) = cd.entries_downloads(payload)
    assert entry["label2"] == "62 % · En cours · 12 min"
    assert entry["props"] == {"progress": "62", "family": "active"}
    assert entry["action"]["action"] == "detail" and entry["action"]["arr_id"] == "5"


def test_notifications() -> None:
    payload = {
        "items": [
            {
                "id": 3,
                "title": "Import terminé",
                "message": "Dune a été importé.",
                "is_read": False,
                "service_name": "Radarr",
                "severity": "info",
                "created_at": "2026-10-10T15:55:00",  # UTC → 17:55 à Paris
            }
        ],
        "unread_count": 1,
    }
    (entry,) = cd.entries_notifications(payload, NOW, PARIS)
    assert entry["label2"] == "il y a 5 min · Radarr · non lue"
    assert entry["action"] == {
        "action": "notification",
        "id": "3",
        "title": "Import terminé",
        "message": "Dune a été importé.",
    }
    assert cd.unread_count(payload) == 1 and cd.unread_count(None) == 0

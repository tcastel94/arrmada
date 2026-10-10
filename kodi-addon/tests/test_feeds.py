"""Flux en cache et temps réel (ADR-003 § 1) : logique du service, sans Kodi."""

from __future__ import annotations

from pathlib import Path

import feeds


def test_every_feed_targets_an_api_route() -> None:
    assert set(feeds.FEEDS) == {
        "recent",
        "upcoming",
        "downloads",
        "foryou",
        "missing",
        "notifications",
    }
    for feed in feeds.FEEDS.values():
        assert feed.path.startswith("/api/") and feed.ttl > 0 and feed.label


def test_save_load_and_change_detection(tmp_path: Path) -> None:
    cache = str(tmp_path / "cache")  # dossier créé à la volée
    assert feeds.load(cache, "recent") is None
    assert feeds.save(cache, "recent", [{"title": "Dune"}], now=100.0) is True
    assert feeds.save(cache, "recent", [{"title": "Dune"}], now=200.0) is False  # identique
    assert feeds.save(cache, "recent", [{"title": "Arcane"}], now=300.0) is True
    entry = feeds.load(cache, "recent")
    assert entry == {"fetched_at": 300.0, "data": [{"title": "Arcane"}]}
    assert not list(tmp_path.rglob("*.tmp"))  # écriture atomique : pas de reste


def test_corrupt_cache_is_ignored(tmp_path: Path) -> None:
    (tmp_path / "feed-recent.json").write_text("{pas du json", encoding="utf-8")
    assert feeds.load(str(tmp_path), "recent") is None


def test_staleness() -> None:
    entry = {"fetched_at": 1000.0, "data": []}
    assert feeds.is_stale(None, 60, 1000.0)
    assert not feeds.is_stale(entry, 60, 1059.0)
    assert feeds.is_stale(entry, 60, 1060.0)
    assert feeds.is_usable(entry, 1000.0 + feeds.MAX_AGE - 1)
    assert not feeds.is_usable(entry, 1000.0 + feeds.MAX_AGE)
    assert feeds.is_error({"status": "error", "message": "x"})
    assert not feeds.is_error([{"status": "error"}])  # une liste n'est pas une erreur


def test_events_refresh_the_right_feeds() -> None:
    assert feeds.feeds_for_event("new_import", {}) >= {"recent", "missing", "downloads"}
    assert feeds.feeds_for_event("download_update", {}) == {"downloads"}
    assert feeds.feeds_for_event("cache_invalidated", {"patterns": ["media"]}) == {
        "recent",
        "missing",
    }
    assert feeds.feeds_for_event("cache_invalidated", {"patterns": ["dashboard"]}) == set()
    assert feeds.feeds_for_event("kodi_scrobble", {}) == set()


def test_osd_messages() -> None:
    assert feeds.osd_message("new_import", {"title": "Dune", "quality": "Remux-2160p"}) == (
        "Importé sur le NAS",
        "Dune · Remux-2160p",
    )
    assert feeds.osd_message("download_grab", {"title": "Arcane S02E01"}) == (
        "Téléchargement lancé",
        "Arcane S02E01",
    )
    assert feeds.osd_message("download_update", {"title": "x"}) is None
    assert feeds.osd_message("new_import", {}) is None  # sans titre : rien à dire


def test_sse_parser() -> None:
    stream = [
        "event: connected\n",
        'data: {"clients": 1}\n',
        "\n",
        ": commentaire de maintien de connexion\n",
        "id: 42\n",
        "event: new_import\n",
        'data: {"title": "Dune",\n',
        'data:  "quality": "Remux-2160p"}\n',
        "\n",
        "data: pas du json\n",
        "\n",
        "\n",
    ]
    events = list(feeds.parse_stream(iter(stream)))
    assert events[0] == ("connected", {"clients": 1}, "")
    assert events[1] == ("new_import", {"title": "Dune", "quality": "Remux-2160p"}, "42")
    assert events[2][0] == "message" and events[2][1] == {"raw": "pas du json"}
    assert len(events) == 3

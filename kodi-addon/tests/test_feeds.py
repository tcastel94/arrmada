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


def test_next_feed_one_at_a_time() -> None:
    """Un seul flux par tour : d'abord ceux réclamés par un événement."""
    now = 10_000.0
    fresh = {name: now for name in feeds.FEEDS}  # tout vient d'être téléchargé
    assert feeds.next_feed(set(), fresh, {}, now) is None
    assert feeds.next_feed({"missing", "recent"}, fresh, {}, now) == "recent"  # ordre de FEEDS

    stale = dict(fresh, downloads=now - feeds.FEEDS["downloads"].ttl)
    assert feeds.next_feed(set(), stale, {}, now) == "downloads"
    # En attente après une erreur : on ne réessaie pas avant l'heure…
    assert feeds.next_feed(set(), stale, {"downloads": now + 60}, now) is None
    # … sauf si un événement le réclame
    assert feeds.next_feed({"downloads"}, stale, {"downloads": now + 60}, now) == "downloads"
    # Jamais téléchargé : à faire tout de suite
    assert feeds.next_feed(set(), {}, {}, now) == "recent"


def _recent(*events, boot="b1", last_id=None) -> dict:
    payload = {
        "events": [{"id": str(i), "type": t, "data": d, "timestamp": 0} for i, t, d in events],
        "clients": 0,
        "boot_id": boot,
    }
    if last_id is not None:
        payload["last_id"] = last_id
    return payload


def test_event_cursor_baseline_then_new_events() -> None:
    cursor = feeds.EventCursor()
    # 1er relevé : on note la position, aucune notification pour le passé
    assert cursor.accept(_recent((7, "new_import", {"title": "Dune"}), last_id=9)) == []
    assert cursor.last_id == 9

    fresh = cursor.accept(
        _recent((11, "download_grab", {"title": "Arcane"}), (10, "new_import", {"title": "Flow"}))
    )
    assert [(i, t) for i, t, _ in fresh] == [(10, "new_import"), (11, "download_grab")]
    assert cursor.last_id == 11
    assert cursor.accept(_recent((11, "download_grab", {}))) == []  # déjà traité


def test_event_cursor_server_restart() -> None:
    cursor = feeds.EventCursor()
    cursor.accept(_recent(last_id=40))
    # Le serveur a redémarré : nouvel identifiant, numérotation repartie de 1
    assert cursor.accept(_recent(boot="b2", last_id=2)) is None
    assert cursor.last_id == 0
    fresh = cursor.accept(
        _recent((1, "new_import", {"title": "Wicked"}), (2, "cache_invalidated", {}), boot="b2")
    )
    assert [i for i, _, _ in fresh] == [1, 2] and cursor.last_id == 2


def test_event_cursor_tolerates_bad_payloads() -> None:
    cursor = feeds.EventCursor()
    cursor.accept({"events": []})  # ancien serveur : ni boot_id ni last_id
    noisy = {"events": [{"id": "x"}, "texte", {"id": 3, "type": "new_import", "data": "?"}]}
    assert cursor.accept(noisy) == [(3, "new_import", {})]
    assert cursor.accept(None) == [] and cursor.accept([1, 2]) == []

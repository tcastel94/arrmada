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


DUNE = {
    "event": "Download",
    "title": "Dune",
    "quality": "Remux-2160p",
    "poster": "https://image.tmdb.org/t/p/w500/dune.jpg",
    "size": 64 * 1024**3,
    "year": 2021,
}


def test_import_notification_carries_the_poster() -> None:
    bubble = feeds.osd_notification("new_import", DUNE)
    assert bubble == {
        "heading": "Importé sur le NAS",
        "message": "Dune · Remux-2160p · 64 Go",
        "icon": "https://image.tmdb.org/t/p/w500/dune.jpg",
        "title": "Dune",
    }
    upgrade = feeds.osd_notification("new_import", dict(DUNE, upgrade=True))
    assert upgrade["heading"] == "Mise à niveau sur le NAS"


def test_other_notifications() -> None:
    episode = feeds.osd_notification(
        "download_grab",
        {"title": "Severance S02E10", "episode_title": "Cold Harbor", "size": 7.5 * 1024**3},
    )
    assert episode["heading"] == "Téléchargement lancé"
    assert episode["message"] == "Severance S02E10 · Cold Harbor · 7,5 Go"
    assert episode["icon"] == ""  # pas d'affiche : l'icône de l'add-on

    added = feeds.osd_notification(
        "new_import", {"event": "MovieAdded", "title": "Wicked", "year": 2024}
    )
    assert (added["heading"], added["message"]) == ("Nouveau titre suivi", "Wicked (2024) · Radarr")

    blocked = feeds.osd_notification("import_blocked", {"title": "Flow", "service": "radarr"})
    assert blocked["message"] == "Flow : à régler dans Radarr (web app)"

    assert feeds.osd_notification("health_alert", {"title": "Disque plein"})["message"] == (
        "Disque plein"
    )
    # Serveur d'avant la phase 3 : bulle plus sobre, mais bulle quand même
    assert feeds.osd_notification("new_import", {"title": "Dune"})["message"] == "Dune"
    assert feeds.osd_notification("download_update", {"title": "x"}) is None
    assert feeds.osd_notification("new_import", {}) is None  # sans titre : rien à dire
    # Adresse d'affiche douteuse : ignorée
    assert feeds.osd_notification("new_import", dict(DUNE, poster="/local.jpg"))["icon"] == ""


def test_merge_notifications() -> None:
    one = feeds.osd_notification("new_import", DUNE)
    two = feeds.osd_notification("download_grab", {"title": "Arcane S02E01"})
    assert feeds.merge_notifications([]) == []
    assert feeds.merge_notifications([one, two]) == [one, two]  # peu : telles quelles

    many = [one, two] + [
        feeds.osd_notification("new_import", {"title": f"Film {n}"}) for n in range(3)
    ]
    (summary,) = feeds.merge_notifications(many)
    assert summary["heading"] == "5 nouveautés ArrMada"
    assert summary["message"] == "Dune, Arcane S02E01, Film 0 et 2 autre(s)"
    assert summary["icon"] == DUNE["poster"]  # la dernière affiche connue

    (after_movie,) = feeds.merge_notifications([one], heading="Pendant ta séance")
    assert after_movie["heading"] == "Pendant ta séance · Importé sur le NAS"
    assert after_movie["message"] == "Dune · Remux-2160p · 64 Go"
    assert after_movie["icon"] == DUNE["poster"]
    (several,) = feeds.merge_notifications([one, two], heading="Pendant ta séance")
    assert several["message"] == "2 nouveauté(s) : Dune, Arcane S02E01"


def test_notification_texts_use_only_silvo_glyphs() -> None:
    missing = {"→", "★", "✓", "✔", "▶", "⏸", "●"}
    samples = [
        feeds.osd_notification("new_import", DUNE),
        feeds.osd_notification("import_blocked", {"title": "Flow"}),
        feeds.merge_notifications([feeds.osd_notification("new_import", DUNE)] * 3)[0],
    ]
    for bubble in samples:
        assert not missing & set(bubble["heading"] + bubble["message"])


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


class TestAbsoluteUrls:
    """Images des dossiers des médias (1.20.1) : adresse relative du serveur."""

    def test_local_images_get_the_server_address(self) -> None:
        data = {
            "items": [
                {"discart_url": "/api/artwork/local/abc/ZGlzYw.png?v=1", "title": "/api/media"},
                {"poster_url": "https://image.tmdb.org/t/p/original/p.jpg"},
            ],
            "images": {"clearlogo": "/api/artwork/local/def/bG9nbw.png"},
            "count": 2,
            "empty": None,
        }
        out = feeds.absolute_urls(data, "http://192.168.2.3:8420/")
        assert out["items"][0]["discart_url"] == (
            "http://192.168.2.3:8420/api/artwork/local/abc/ZGlzYw.png?v=1"
        )
        assert out["items"][0]["title"] == "/api/media"  # pas une image locale
        assert out["items"][1]["poster_url"].startswith("https://image.tmdb.org/")
        assert out["images"]["clearlogo"].startswith("http://192.168.2.3:8420/api/artwork/")
        assert out["count"] == 2 and out["empty"] is None

"""Vu / reprise partagés entre les TV (lib/sync_data.py)."""

from __future__ import annotations

import json

import sync_data as sd

SHOW_IDS = {"tvdb": "371980", "tmdb": "95396", "imdb": "tt11280740"}
EPISODE = {
    "episodeid": 12,
    "tvshowid": 3,
    "season": 1,
    "episode": 4,
    "showtitle": "Severance",
    "title": "The You You Are",
    "playcount": 0,
    "resume": {"position": 1500.4, "total": 2700.0},
    "runtime": 2700,
    "lastplayed": "2026-10-11 21:42:05",
}
MOVIE = {
    "movieid": 7,
    "title": "Dune",
    "uniqueid": {"tmdb": "438631", "imdb": "tt1160419"},
    "playcount": 1,
    "resume": {"position": 0, "total": 0},
    "runtime": 9300,
    "lastplayed": "2026-10-10 20:00:00",
}


def test_ids_and_keys():
    assert sd.pick_id("episode", SHOW_IDS) == ("tvdb", "371980")
    assert sd.pick_id("episode", {"tmdb": "95396"}) == ("tmdb", "95396")
    assert sd.pick_id("movie", MOVIE["uniqueid"]) == ("tmdb", "438631")
    assert sd.pick_id("movie", {"tmdb": "", "imdb": "tt1"}) == ("imdb", "tt1")
    assert sd.pick_id("movie", {"tmdb": "0"}) is None  # identifiant vide ou nul
    assert sd.index_keys(SHOW_IDS) == ["tmdb:95396", "tvdb:371980", "imdb:tt11280740"]


def test_local_state():
    state = sd.local_state("episode", EPISODE, SHOW_IDS)
    assert state == {
        "media_type": "episode",
        "id_type": "tvdb",
        "id": "371980",
        "title": "Severance",
        "watched": False,
        "position": 1500,
        "total": 2700,
        "last_played": "2026-10-11 21:42:05",
        "season": 1,
        "episode": 4,
    }
    assert sd.state_key(state) == "episode:tvdb:371980:1:4"
    movie = sd.local_state("movie", MOVIE)
    assert movie["watched"] is True and movie["total"] == 9300  # durée annoncée
    assert sd.state_key(movie) == "movie:tmdb:438631"
    # Sans identifiant public : rien à partager
    assert sd.local_state("episode", EPISODE, {}) is None
    assert sd.local_state("musicvideo", MOVIE) is None
    assert sd.describe(state) == "Severance S01E04 (reprise 25:00)"
    assert sd.describe(movie) == "Dune (vu)"


def test_plan_latest_wins():
    # Vu sur l'autre TV
    remote = {"watched": True, "position": 0, "total": 2700, "last_played": "2026-10-12 20:00:00"}
    assert sd.plan(EPISODE, remote) == {
        "playcount": 1,
        "resume": {"position": 0, "total": 2700},
        "lastplayed": "2026-10-12 20:00:00",
    }
    # Non vu sur l'autre TV (geste le plus récent) : on décoche ici
    assert sd.plan(MOVIE, {"watched": False, "position": 0}) == {"playcount": 0}
    # Reprise ailleurs, 10 s près : déjà à jour
    assert sd.plan(EPISODE, {"watched": False, "position": 1505}) is None
    assert sd.plan(EPISODE, {"watched": False, "position": 1800})["resume"]["position"] == 1800
    # Date plus ancienne que celle d'ici : pas recopiée
    old = {"watched": False, "position": 1800, "last_played": "2026-01-01 10:00:00"}
    assert "lastplayed" not in sd.plan(EPISODE, old)


def test_plan_first_pass_only_adds():
    # Premier passage : on ne décoche jamais, on n'écrase pas une reprise d'ici
    assert sd.plan(MOVIE, {"watched": False, "position": 0}, prudent=True) is None
    assert sd.plan(EPISODE, {"watched": False, "position": 600}, prudent=True) is None
    # … mais on ajoute un « vu » (la reprise d'ici n'a plus lieu d'être)
    assert sd.plan(EPISODE, {"watched": True, "position": 0}, prudent=True) == {
        "playcount": 1,
        "resume": {"position": 0, "total": 2700},
    }
    # … et une reprise là où il n'y en a pas
    fresh = dict(EPISODE, resume={"position": 0, "total": 0})
    assert sd.plan(fresh, {"watched": False, "position": 600}, prudent=True) == {
        "resume": {"position": 600, "total": 2700}
    }


def test_same_and_memory():
    a = {"watched": True, "position": 0}
    assert sd.same(a, {"watched": True, "position": 7})
    assert not sd.same(a, {"watched": False, "position": 0})
    assert not sd.same(None, a)
    assert sd.load_memory("") == {"cursor": "", "uploaded": False}
    assert sd.load_memory("pas du json") == {"cursor": "", "uploaded": False}
    memory = sd.load_memory(sd.dump_memory("2026-10-11T19:00:00+00:00", True))
    assert memory == {"cursor": "2026-10-11T19:00:00+00:00", "uploaded": True}
    assert sd.is_first_pass({"cursor": "", "uploaded": False})
    assert not sd.is_first_pass(memory)
    assert [len(b) for b in sd.batches(list(range(450)))] == [200, 200, 50]


def test_library_update_notifications():
    """Seuls les changements de « vu » partent : pas les scans de médiathèque."""
    seen = json.dumps({"item": {"id": 12, "type": "episode"}, "playcount": 1})
    assert sd.library_update("VideoLibrary.OnUpdate", seen) == ("episode", 12)
    assert sd.library_update("VideoLibrary.OnUpdate", {"item": {"id": 7, "type": "movie"},
                                                       "playcount": 0}) == ("movie", 7)  # fmt: skip
    added = json.dumps({"item": {"id": 13, "type": "episode"}, "added": True, "playcount": 0})
    assert sd.library_update("VideoLibrary.OnUpdate", added) is None
    refresh = json.dumps({"item": {"id": 12, "type": "episode"}})
    assert sd.library_update("VideoLibrary.OnUpdate", refresh) is None
    assert sd.library_update("VideoLibrary.OnScanFinished", seen) is None
    assert sd.library_update("VideoLibrary.OnUpdate", "{cassé") is None
    song = json.dumps({"item": {"id": 3, "type": "song"}, "playcount": 1})
    assert sd.library_update("VideoLibrary.OnUpdate", song) is None

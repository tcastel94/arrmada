"""Vu, en cours, à suivre (lib/watch_data.py, ADR-004 phase 4.1).

Les données imitent les réponses JSON-RPC de Kodi 20/21 relevées sur le banc
(VideoLibrary.GetEpisodes, GetMovies, filtre « inprogress »).
"""

from __future__ import annotations

import watch_data as wd


def ep(eid, season, episode, playcount=0, position=0.0, total=90.0, lastplayed="", **extra):
    item = {
        "episodeid": eid,
        "season": season,
        "episode": episode,
        "title": f"Titre {season}x{episode}",
        "playcount": playcount,
        "resume": {"position": position, "total": total if position else 0.0},
        "runtime": 3120,
        "lastplayed": lastplayed,
        "firstaired": "2022-02-18",
        "art": {"thumb": f"image://thumb-{eid}/", "tvshow.poster": "image://poster/"},
        "tvshowid": 1,
        "showtitle": "Severance",
    }
    item.update(extra)
    return item


SHOW = [
    ep(1, 1, 1, playcount=1, lastplayed="2026-10-10 21:00:00"),
    ep(2, 1, 2, playcount=1, lastplayed="2026-10-10 21:50:00"),
    ep(3, 1, 3),
    ep(10, 2, 1),
    ep(11, 2, 2),
    ep(20, 0, 1),  # épisode spécial
]


# ── Formats ─────────────────────────────────────────────────────────────────


def test_clock_and_durations():
    assert wd.clock(754) == "12:34"
    assert wd.clock(3723) == "1:02:03"
    assert wd.clock(None) == "0:00"
    assert wd.duration_label(3120) == "52 min"
    assert wd.duration_label(9300) == "2 h 35"
    assert wd.duration_label(7200) == "2 h"
    assert wd.duration_label(0) == ""


def test_bar_name_uses_the_two_percent_textures():
    assert wd.bar_name(30, 90) == "bar-034"  # 33 % → barre la plus proche (pas de 2)
    assert wd.bar_name(90, 90) == "bar-100"
    assert wd.bar_name(0, 90) == ""
    assert wd.bar_name(30, 0) == ""


def test_aired_and_codes():
    assert wd.aired_label("2022-02-18") == "18 février 2022"
    assert wd.aired_label("") == ""
    assert wd.episode_code(1, 4) == "S01E04"
    assert wd.season_label(0) == "Épisodes spéciaux"
    assert wd.season_label(2) == "Saison 2"


def test_resume_ignores_tiny_or_finished_positions():
    assert wd.resume_of({"resume": {"position": 30.0, "total": 90.0}}) == (30, 90)
    assert wd.resume_of({"resume": {"position": 4.0, "total": 90.0}})[0] == 0
    assert wd.resume_of({"resume": {"position": 90.0, "total": 90.0}})[0] == 0
    # Kodi donne parfois total = 0 : on prend la durée annoncée
    assert wd.resume_of({"resume": {"position": 30.0, "total": 0.0}, "runtime": 3120}) == (30, 3120)


# ── Épisode suivant, enchaînement ───────────────────────────────────────────


def test_next_is_first_unwatched_after_last_watched():
    assert wd.next_episode(SHOW)["episodeid"] == 3


def test_next_skips_an_episode_skipped_earlier():
    # E02 non vu mais E03 vu : on ne revient pas en arrière
    show = [ep(1, 1, 1, playcount=1), ep(2, 1, 2), ep(3, 1, 3, playcount=1), ep(4, 1, 4)]
    assert wd.next_episode(show)["episodeid"] == 4


def test_started_episode_wins():
    show = [ep(1, 1, 1, playcount=1), ep(2, 1, 2), ep(3, 1, 3, position=30.0, lastplayed="x")]
    assert wd.next_episode(show)["episodeid"] == 3


def test_nothing_watched_starts_at_the_beginning_not_the_specials():
    show = [ep(20, 0, 1), ep(2, 1, 2), ep(1, 1, 1)]
    assert wd.next_episode(show)["episodeid"] == 1


def test_all_watched_means_no_next():
    assert wd.next_episode([ep(1, 1, 1, playcount=1), ep(2, 1, 2, playcount=1)]) is None


def test_chain_follows_the_show_across_seasons_without_specials():
    assert wd.chain_after(SHOW, 3) == [10, 11]
    assert wd.chain_after(SHOW, 11) == []
    assert wd.chain_after(SHOW, 20) == []  # depuis un spécial : rien
    assert wd.chain_after(SHOW, 999) == []
    assert wd.chain_after(SHOW, 1, limit=2) == [2, 3]


# ── Écran Série ─────────────────────────────────────────────────────────────


def test_seasons_put_specials_last_with_progress():
    seasons = wd.season_models(wd.sort_episodes(SHOW))
    assert [s["label"] for s in seasons] == ["Saison 1", "Saison 2", "Épisodes spéciaux"]
    assert seasons[0]["progress"] == "2 / 3 vus"
    assert seasons[0]["bar"] == "bar-066"
    full = wd.season_models([ep(1, 1, 1, playcount=1)])
    assert full[0]["progress"] == "Vue"


def test_build_show_starts_on_the_next_episode():
    model = wd.build_show({"title": "Severance", "year": 2022, "art": {"fanart": "f"}}, SHOW)
    assert model["meta"] == "2022 · 2 saisons · 5 épisodes · 2 vus"
    assert model["next_id"] == 3
    assert model["play_label"] == "Lire S01E03"
    assert (model["start_season"], model["start_episode"]) == (0, 2)
    first = model["episodes"][1][0]
    assert first["code"] == "S01E01" and first["status"] == "Vu"
    assert first["label"] == "1. Titre 1x1"
    assert first["duration"] == "52 min"


def test_build_show_resume_and_rewatch_labels():
    started = [ep(1, 1, 1, playcount=1), ep(2, 1, 2, position=754.0, total=3120.0, lastplayed="x")]
    model = wd.build_show({"title": "S"}, started)
    assert model["play_label"] == "Reprendre S01E02"
    second = model["episodes"][1][1]
    assert second["status"] == "Reprendre à 12:34"
    assert second["bar"] == "bar-024"
    done = wd.build_show({"title": "S", "year": 1970}, [ep(1, 1, 1, playcount=1)])
    assert done["play_label"] == "Revoir depuis le début"
    assert done["meta"] == "1 saison · 1 épisode · tout vu"  # 1970 = année inconnue


# ── Rangée « Reprendre » ────────────────────────────────────────────────────


def test_continue_feed_merges_and_sorts_by_last_played():
    movies = [
        {
            "movieid": 1,
            "title": "Dune",
            "year": 2021,
            "resume": {"position": 40.0, "total": 9300.0},
            "lastplayed": "2026-10-09 20:00:00",
            "art": {"poster": "p", "fanart": "f"},
            "uniqueid": {"tmdb": "438631"},
        }
    ]
    in_progress = [ep(4, 1, 4, position=30.0, lastplayed="2026-10-10 22:00:00")]
    show = {"tvshowid": 2, "title": "The Bear", "lastplayed": "2026-10-08 19:00:00", "art": {}}
    next_up = ep(30, 1, 2, tvshowid=2, showtitle="The Bear")
    rows = wd.continue_feed(movies, in_progress, [(show, next_up)])
    assert [(r["kind"], r["dbid"]) for r in rows] == [("episode", 4), ("movie", 1), ("episode", 30)]
    assert rows[0]["status"] == "Reprendre à 0:30 · reste 1 min"
    assert rows[0]["subtitle"] == "S01E04 · Titre 1x4"
    assert rows[1]["status"].startswith("Reprendre à 0:40 · reste 2 h 34")
    assert rows[2]["status"] == "Épisode suivant"


def test_continue_feed_shows_a_series_once():
    in_progress = [ep(4, 1, 4, position=30.0, lastplayed="2026-10-10 22:00:00")]
    show = {"tvshowid": 1, "title": "Severance", "lastplayed": "2026-10-10 22:00:00"}
    rows = wd.continue_feed([], in_progress, [(show, ep(5, 1, 5))])
    assert [r["dbid"] for r in rows] == [4]


def test_continue_feed_ignores_items_without_real_resume():
    movies = [{"movieid": 1, "title": "X", "resume": {"position": 3.0, "total": 90.0}}]
    assert wd.continue_feed(movies, [], []) == []


# ── État dans les listes ArrMada ────────────────────────────────────────────


def test_annotate_marks_watched_movies_and_shows():
    entries = [
        {"ids": {"tmdb": "438631"}, "info": {}, "props": {}, "context": ["play", "detail"]},
        {"ids": {"tmdb": "1"}, "info": {}, "props": {}, "context": ["play"]},
        {"ids": {"tvdb": "371980"}, "info": {}, "props": {}, "context": ["play"]},
        {"ids": {"tmdb": "404"}, "info": {}, "props": {}, "context": ["detail"]},
    ]
    movies = wd.library_index(
        [
            {"movieid": 1, "playcount": 1, "uniqueid": {"tmdb": "438631"}},
            {
                "movieid": 2,
                "resume": {"position": 754.0, "total": 9300.0},
                "uniqueid": {"tmdb": "1"},
            },
        ],
        "tmdb",
    )
    shows = wd.library_index(
        [{"tvshowid": 1, "episode": 14, "watchedepisodes": 4, "uniqueid": {"tvdb": "371980"}}],
        "tvdb",
    )
    wd.annotate(entries, movies, shows)
    assert entries[0]["info"]["playcount"] == 1
    assert entries[0]["context"] == ["play", "detail", "unseen"]
    assert entries[1]["info"]["resume"] == (754, 9300)
    assert entries[1]["props"]["kodi_status"] == "Reprendre à 12:34"
    assert entries[1]["context"] == ["play", "seen"]
    assert entries[2]["props"]["UnWatchedEpisodes"] == 10
    assert entries[2]["props"]["bar"] == "bar-028"  # 4 épisodes vus sur 14
    assert (entries[0]["props"]["watched"], entries[0]["props"]["bar"]) == ("1", "")
    assert entries[1]["props"]["bar"] == "bar-008"
    assert entries[2]["props"]["kodi_status"] == "4 / 14 épisodes vus"
    assert "playcount" not in entries[3]["info"]  # absent de la médiathèque Kodi


def test_show_state_labels():
    assert wd.show_state({"episode": 3, "watchedepisodes": 3})["status"] == "Tout vu"
    assert wd.show_state({"episode": 3, "watchedepisodes": 0})["status"] == ""


def test_continue_entries_play_through_arrmada():
    rows = wd.continue_feed(
        [
            {
                "movieid": 7,
                "title": "Dune",
                "year": 2021,
                "resume": {"position": 754.0, "total": 9300.0},
                "lastplayed": "2026-10-09 20:00:00",
                "art": {"poster": "p", "fanart": "f"},
                "plot": "Paul part sur Arrakis.",
            }
        ],
        [ep(4, 1, 4, position=30.0, lastplayed="2026-10-10 22:00:00")],
        [],
    )
    episode, movie = wd.continue_entries(rows)
    # Libellé gardé tel quel dans les listes (masque « %L », lib/listing.py)
    assert episode["label"] == "Severance · S01E04"
    assert episode["info"]["plot"] == "Reprendre à 0:30 · reste 1 min"  # pas de résumé
    assert episode["label2"] == "S01E04 · Titre 1x4 · Reprendre à 0:30 · reste 1 min"
    assert episode["action"] == {
        "action": "resume_play",
        "type": "episode",
        "id": "4",
        "tvshowid": "1",
    }
    assert episode["context"] == ["restart", "seen", "series"]
    assert episode["info"]["tvshowtitle"] == "Severance"
    assert (episode["info"]["season"], episode["info"]["episode"]) == (1, 4)
    assert episode["info"]["resume"] == (30, 90)
    assert episode["art"]["tvshow.poster"] == "image://poster/"
    assert movie["action"] == {"action": "resume_play", "type": "movie", "id": "7"}
    assert movie["context"] == ["restart", "seen"]
    assert movie["info"]["mediatype"] == "movie"
    assert movie["label"] == "Dune"
    assert movie["info"]["plot"] == "Reprendre à 12:34 · reste 2 h 22[CR]Paul part sur Arrakis."
    assert movie["folder"] is False


def test_continue_entries_next_episode_has_no_restart():
    show = {"tvshowid": 2, "title": "The Bear", "lastplayed": "2026-10-08 19:00:00"}
    rows = wd.continue_feed([], [], [(show, ep(30, 1, 2, tvshowid=2, showtitle="The Bear"))])
    (entry,) = wd.continue_entries(rows)
    assert entry["context"] == ["seen", "series"]
    assert "resume" not in entry["info"]
    assert entry["label2"].endswith("Épisode suivant")


def test_annotate_again_after_a_change_offers_only_the_other_choice():
    entry = {"ids": {"tmdb": "1"}, "info": {}, "props": {}, "context": ["play", "seen"]}
    wd.annotate(
        [entry], wd.library_index([{"playcount": 1, "uniqueid": {"tmdb": "1"}}], "tmdb"), {}
    )
    assert entry["context"] == ["play", "unseen"]

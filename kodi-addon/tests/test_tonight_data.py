"""« Ce soir » : ce qui tient avant l'heure choisie (lib/tonight_data.py)."""

from __future__ import annotations

from datetime import datetime

import tonight_data as td

NOW = datetime(2026, 10, 11, 20, 47, 5)


def test_tv_now_reads_the_tv_clock():
    today = datetime(2026, 10, 11, 18, 0, 0, 123)
    assert td.tv_now("21:47", today) == datetime(2026, 10, 11, 21, 47)
    assert td.tv_now("21:47:05", today) == datetime(2026, 10, 11, 21, 47, 5)
    assert td.tv_now("", today) == datetime(2026, 10, 11, 18, 0, 0)  # illisible : secours
    # Région en 12 h (Kodi ignore « HH ») : on convertit
    assert td.tv_now("05:43:58 PM", today) == datetime(2026, 10, 11, 17, 43, 58)
    assert td.tv_now("9:05 pm", today) == datetime(2026, 10, 11, 21, 5)
    assert td.tv_now("12:05:00 AM", today) == datetime(2026, 10, 11, 0, 5)
    assert td.tv_now("12:30:00 PM", today) == datetime(2026, 10, 11, 12, 30)
    assert td.tv_now("midi", today) == datetime(2026, 10, 11, 18, 0, 0)


def test_deadlines_every_half_hour_after_45_minutes():
    tabs = td.deadlines(NOW)
    assert [label for _, label, _ in tabs] == [
        "Avant 22:00",
        "Avant 22:30",
        "Avant 23:00",
        "Avant 23:30",
        "Avant minuit",
        "Sans limite",
    ]
    assert tabs[-1] == (td.ANY, "Sans limite", None)
    assert tabs[4][2] == datetime(2026, 10, 12, 0, 0)  # le lendemain
    # Pile sur la demi-heure : 21:15 + 45 min = 22:00, gardé tel quel
    assert td.deadlines(datetime(2026, 10, 11, 21, 15))[0][1] == "Avant 22:00"


def test_default_tab_leaves_two_hours():
    tabs = td.deadlines(NOW)
    assert tabs[td.default_tab(tabs, NOW)][1] == "Avant 23:00"
    late = datetime(2026, 10, 11, 23, 50)
    late_tabs = td.deadlines(late)
    assert late_tabs[td.default_tab(late_tabs, late)][1] == "Avant 02:00"
    assert td.default_tab([(td.ANY, "Sans limite", None)], NOW) == 0


def movie(movieid, title, runtime, playcount=0, position=0, year=2024):
    return {
        "movieid": movieid,
        "title": title,
        "year": year,
        "runtime": runtime,
        "playcount": playcount,
        "resume": {"position": position, "total": runtime if position else 0},
        "art": {"poster": f"p{movieid}.jpg"},
        "uniqueid": {"tmdb": str(1000 + movieid)},
    }


RESUMED = {  # film commencé, tel que la rangée « Reprendre » le donne
    "kind": "movie",
    "dbid": 1,
    "title": "Dune",
    "subtitle": "2021",
    "resume": 2530,
    "total": 9300,
    "bar": "bar-27",
    "poster": "p1.jpg",
}
NEXT_UP = {
    "kind": "episode",
    "dbid": 50,
    "tvshowid": 6,
    "season": 2,
    "episode": 5,
    "episode_title": "Trojan's Horse",
    "title": "Severance",
    "subtitle": "S02E05 · Trojan's Horse",
    "resume": 0,
    "total": 3000,
    "bar": "",
}


def test_candidates_order_and_no_duplicates():
    rows = td.candidates(
        [NEXT_UP, RESUMED],
        [
            movie(1, "Dune", 9300, position=2530),  # commencé : déjà dans « Reprendre »
            movie(2, "Wicked", 9600),
            movie(3, "Vu", 6000, playcount=1),  # déjà vu : écarté
            movie(4, "Flow", 5100),
        ],
    )
    assert [row["title"] for row in rows] == ["Dune", "Severance", "Wicked", "Flow"]
    assert [td.group_of(row) for row in rows] == ["resume", "next", "fresh", "fresh"]


def test_tonight_rows_keep_what_ends_before_the_deadline():
    rows = td.candidates([NEXT_UP, RESUMED], [movie(2, "Wicked", 9600), movie(4, "Flow", 5100)])
    deadline = datetime(2026, 10, 11, 22, 30)
    kept = td.tonight_rows(rows, NOW, deadline)
    # Dune : 1 h 53 restantes → 22:40, trop tard ; Severance 50 min → 21:37 ;
    # Flow 1 h 25 → 22:12 ; Wicked 2 h 40 → 23:27
    assert [row["title"] for row in kept] == ["Severance", "Flow"]
    assert kept[0]["status"] == "Épisode suivant · reste 50 min · fini vers 21:37"
    assert kept[1]["status"] == "1 h 25 · fini vers 22:12"
    assert kept[1]["finish"] == "22:12"
    everything = td.tonight_rows(rows, NOW, None)
    assert [row["title"] for row in everything] == ["Dune", "Severance", "Wicked", "Flow"]
    assert everything[0]["status"] == "Reprise à 42:10 · reste 1 h 53 · fini vers 22:40"


def test_unknown_duration_only_without_limit():
    rows = td.candidates([], [movie(7, "Sans durée", 0)])
    assert td.tonight_rows(rows, NOW, datetime(2026, 10, 12, 3, 0)) == []
    shown = td.tonight_rows(rows, NOW, None)
    assert shown[0]["status"] == "durée inconnue" and shown[0]["finish"] == ""


def test_entries_show_end_time_and_play_like_continue():
    rows = td.tonight_rows(td.candidates([RESUMED, NEXT_UP], []), NOW, None)
    entries = td.tonight_entries(rows)
    first, second = entries
    assert first["action"] == {"action": "resume_play", "type": "movie", "id": "1"}
    assert first["label2"] == "2021"
    assert first["props"]["kodi_status"].endswith("fini vers 22:40")
    assert first["props"]["bar"] == "bar-27"
    assert second["label"] == "Severance · S02E05"
    assert second["action"]["tvshowid"] == "6"
    assert "series" in second["context"]


def test_empty_message():
    assert td.empty_message("Avant 22:00") == (
        "Rien ne se termine avant 22:00 : essaie un horaire plus tard."
    )
    assert "médiathèque" in td.empty_message("Sans limite")

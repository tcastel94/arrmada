"""Feuille « Télécharger » (ADR-005, lot 2) : logique sans Kodi."""

from __future__ import annotations

import download_data as dd

SEASONS = [
    {"number": 1, "episodes": 8, "aired": 8, "have": 8},
    {"number": 2, "episodes": 10, "aired": 10, "have": 3},
    {"number": 3, "episodes": 6, "aired": 0, "have": 0},
]


def test_entry_from_plugin_params() -> None:
    entry = dd.entry_from_params(
        {"type": "series", "title": "The Bear", "tmdb_id": "136315", "tvdb_id": "",
         "arr_id": "0", "in_library": "0", "overview": "Un chef…", "poster_url": "http://p"}
    )  # fmt: skip
    assert entry["kind"] == "series" and entry["tmdb_id"] == 136315
    assert entry["tvdb_id"] is None and entry["arr_id"] is None  # « 0 » = inconnu
    assert entry["poster"] == "http://p" and not entry["in_library"]
    assert dd.entry_from_params({"kind": "tvshow"})["kind"] == "series"
    assert dd.entry_from_params({})["kind"] == "movie"


def test_scope_row() -> None:
    items = dd.scope_items("season", SEASONS)
    assert [i["key"] for i in items] == ["series", "season", "episode"]
    assert [i["selected"] for i in items] == ["", "1", ""]
    assert items[0]["label2"] == "3 saisons · 24 épisodes"
    assert dd.scope_items("series", [])[0]["label2"] == "tout ce qui existe"


def test_season_chips_say_what_is_on_the_nas() -> None:
    chips = dd.season_items(SEASONS, 2)
    assert [(c["label"], c["label2"], c["selected"]) for c in chips] == [
        ("Saison 1", "complète", ""),
        ("Saison 2", "3/10 sur le NAS", "1"),
        ("Saison 3", "6 épisodes", ""),
    ]
    assert dd.season_items([{"number": 4}], None)[0]["label2"] == ""  # nombre inconnu


def test_episode_rows() -> None:
    episodes = [
        {"season": 2, "number": 1, "title": "Beef", "has_file": True, "aired": True},
        {"season": 2, "number": 4, "title": "Honeydew", "aired": True, "runtime": 34},
        {"season": 2, "number": 9, "title": "", "aired": False, "air_date": "2026-11-03"},
    ]
    undated = dd.episode_items([{"season": 3, "number": 1, "aired": False}], set())
    assert undated[0]["note"] == "À venir"
    rows = dd.episode_items(episodes, {4})
    assert [(r["code"], r["label"], r["state"], r["note"], r["picked"]) for r in rows] == [
        ("S02E01", "Beef", "have", "Déjà sur le NAS", ""),
        ("S02E04", "Honeydew", "", "34 min", "1"),
        ("S02E09", "Épisode 9", "future", "Sortie le 3 nov. 2026", ""),
    ]


def test_pick_and_unpick() -> None:
    picked = dd.toggle_pick(set(), 4)
    assert picked == {4}
    assert dd.toggle_pick(dd.toggle_pick(picked, 5), 4) == {5}


def test_button_says_what_leaves() -> None:
    assert dd.button_label("movie", "season", None, set()) == "Télécharger le film"
    assert dd.button_label("series", "series", None, set()) == "Télécharger toute la série"
    assert dd.button_label("series", "season", None, set()) == "Choisis une saison"
    assert dd.button_label("series", "season", 2, set()) == "Télécharger la saison 2"
    assert dd.button_label("series", "episode", 2, set()) == "Coche un épisode"
    assert dd.button_label("series", "episode", 2, {4}) == "Télécharger S02E04"
    assert dd.button_label("series", "episode", 2, {4, 5, 6}) == "Télécharger 3 épisodes"


def test_ready() -> None:
    assert dd.ready("movie", "season", None, set())
    assert dd.ready("series", "series", None, set())
    assert not dd.ready("series", "season", None, set())
    assert dd.ready("series", "season", 1, set())
    assert not dd.ready("series", "episode", 1, set())
    assert dd.ready("series", "episode", 1, {2})


def test_payload() -> None:
    movie = {"kind": "movie", "title": "Dune", "tmdb_id": 438631, "tvdb_id": None}
    assert dd.payload(movie, "season", None, set(), True) == {
        "type": "movie",
        "title": "Dune",
        "priority": True,
        "tmdb_id": 438631,
    }
    series = {"kind": "series", "title": "The Bear", "tvdb_id": 403245, "arr_id": 12}
    assert dd.payload(series, "episode", 2, {5, 4}, False) == {
        "type": "series",
        "title": "The Bear",
        "priority": False,
        "tvdb_id": 403245,
        "arr_id": 12,
        "scope": "episode",
        "season": 2,
        "episodes": [4, 5],
    }
    whole = dd.payload(series, "series", 2, {4}, True)
    assert whole["scope"] == "series" and "season" not in whole and "episodes" not in whole


def test_texts() -> None:
    assert dd.summary("series", SEASONS) == "3 saisons · 24 épisodes · 11 déjà sur le NAS"
    assert dd.summary("series", []) == "Saisons en cours de chargement…"
    assert "sous-titres" in dd.summary("movie", [])
    assert dd.tonight_hint(True).startswith("Passe devant")
    assert dd.episodes_note("sonarr", []).startswith("Épisodes connus une fois")
    assert dd.episodes_note("tmdb", [{"number": 1}]) == ""
    assert dd.french_date("2026-02-01") == "1 févr. 2026" and dd.french_date("bof") == ""


def test_result_message() -> None:
    ok = dd.result_message(
        {"status": "ok", "title": "Dune", "message": "Dune · film : c'est parti"}
    )
    assert ok["ok"] and ok["message"].endswith("c'est parti")
    already = dd.result_message({"status": "error", "code": "available", "message": "déjà"})
    assert not already["ok"] and already["available"]
    assert dd.result_message(None)["message"] == "Serveur injoignable"


def test_no_glyph_missing_from_the_tv_font() -> None:
    """Les textes fabriqués ici s'affichent avec les polices du skin : pas de ✓ ▶ →…"""
    texts = [dd.summary("series", SEASONS), dd.tonight_hint(False), dd.tonight_hint(True)]
    texts += [i["label2"] for i in dd.scope_items("season", SEASONS)]
    texts += [dd.button_label("series", s, 2, {1}) for s in ("series", "season", "episode")]
    assert not any(ch in t for t in texts for ch in "→★✓✔▶⏸●")

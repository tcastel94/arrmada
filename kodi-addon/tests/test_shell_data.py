"""Coquille ArrMada : accueil média, grille, retour automatique (lib/shell_data.py)."""

from __future__ import annotations

import shell_data as sd


def test_menu_and_rows_are_stable():
    assert [key for key, _ in sd.MENU][:3] == ["home", "movies", "series"]
    assert "board" in dict(sd.MENU)  # l'ancien Accueil reste joignable
    assert [key for key, _ in sd.ROWS] == ["continue", "recent", "foryou", "upcoming"]
    assert sd.QUIT_CHOICES[0][0] == "stay"  # Retour par erreur : rien ne se passe
    assert "kodi" in dict(sd.QUIT_CHOICES)  # toujours une porte de sortie


def test_rows_are_limited_and_first_non_empty_row_wins():
    rows = sd.limit_rows({"continue": [], "recent": list(range(50)), "upcoming": [1]})
    assert len(rows["recent"]) == sd.ROW_LIMIT
    assert rows["foryou"] == []
    assert sd.first_row(rows) == "recent"
    assert sd.first_row({"continue": [1], "recent": [2]}) == "continue"
    assert sd.first_row({}) is None


def test_hero_separates_status_from_plot():
    entry = {
        "label": "Severance · S01E04",
        "label2": "S01E04 · The You You Are · Reprendre à 0:30",
        "info": {"plot": "Reprendre à 0:30[CR]Mark découvre un secret."},
        "art": {"thumb": "t", "fanart": ""},
        "props": {"status": "Reprendre à 0:30"},
    }
    hero = sd.hero(entry)
    assert hero["title"] == "Severance · S01E04"
    assert hero["meta"] == "S01E04 · The You You Are"  # l'état n'est pas répété
    assert hero["status"] == "Reprendre à 0:30"
    assert hero["plot"] == "Mark découvre un secret."
    assert hero["fanart"] == "t"  # pas de fond : la vignette
    film = sd.hero(
        {
            "label": "Dune",
            "info": {"plot": "Paul part sur Arrakis."},
            "art": {"fanart": "f", "clearlogo": "l"},
            "props": {"kodi_status": "Vu"},
        }
    )
    assert (film["status"], film["plot"], film["clearlogo"]) == (
        "Vu",
        "Paul part sur Arrakis.",
        "l",
    )
    assert sd.hero(None)["title"] == ""


def test_next_page_is_loaded_two_rows_ahead():
    # 100 chargés, 7 par ligne : à partir du 86e (index 86) on charge la suite
    assert not sd.need_more(85, 100, 1, 3)
    assert sd.need_more(86, 100, 1, 3)
    assert not sd.need_more(99, 100, 3, 3)  # dernière page
    assert not sd.need_more(0, 0, 0, 1)  # rien encore


def test_grid_status_and_tabs():
    assert sd.grid_status(100, 2431, False) == "100 / 2 431 titres"
    assert sd.grid_status(12, 12, False) == "12 titres"
    assert sd.grid_status(1, 0, False) == "1 titre"
    assert sd.grid_status(0, 0, True) == "Chargement…"
    assert sd.tab_index(sd.DISCOVER_TABS, "tvshows") == 2
    assert sd.tab_index(sd.DISCOVER_TABS, "inconnu") == 0


BASE = {
    "enabled": True,
    "safe_mode": False,
    "suspended": False,
    "home_active": True,
    "modal": False,
    "playing": False,
    "shell_open": False,
    "opening_age": None,
}


def test_shell_reopens_only_on_kodi_home():
    assert sd.should_open_shell(BASE)
    for key, value in (
        ("enabled", False),  # réglage décoché
        ("safe_mode", True),  # disjoncteur : Kodi s'est fermé au démarrage
        ("suspended", True),  # « Interface Kodi » choisi dans le menu Quitter
        ("home_active", False),  # un autre écran de Kodi (YouTube, réglages…)
        ("modal", True),  # une boîte de dialogue par-dessus
        ("playing", True),  # une vidéo en cours
        ("shell_open", True),  # déjà ouvert
    ):
        assert not sd.should_open_shell(dict(BASE, **{key: value})), key


def test_shell_open_retry_and_loop_protection():
    assert not sd.should_open_shell(dict(BASE, opening_age=2.0))
    assert sd.should_open_shell(dict(BASE, opening_age=sd.OPEN_RETRY))
    assert sd.opens_too_often([100.0, 110.0, 120.0], now=125.0)
    assert not sd.opens_too_often([10.0, 110.0, 120.0], now=125.0)

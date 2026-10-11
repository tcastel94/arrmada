"""Encart « Épisode suivant » (lib/upnext_data.py)."""

from __future__ import annotations

import upnext_data as up

NEXT = {
    "title": "Half Loop",
    "season": 1,
    "episode": 2,
    "showtitle": "Severance",
    "art": {"thumb": "/vignettes/s01e02.jpg", "fanart": "/fond.jpg"},
}


def test_setting_values():
    assert up.seconds_setting("30") == 30
    assert up.seconds_setting("0") == 0  # désactivé
    assert up.seconds_setting("") == up.DEFAULT_SECONDS
    assert up.seconds_setting("17") == up.DEFAULT_SECONDS  # valeur inconnue
    assert up.seconds_setting(None) == up.DEFAULT_SECONDS


def test_offer_once_near_the_end_of_an_episode():
    assert up.should_offer(18, 2700, 20, already=False, is_episode=True)
    assert not up.should_offer(25, 2700, 20, already=False, is_episode=True)  # trop tôt
    assert not up.should_offer(18, 2700, 20, already=True, is_episode=True)  # déjà proposé
    assert not up.should_offer(18, 2700, 20, already=False, is_episode=False)  # un film
    assert not up.should_offer(18, 2700, 0, already=False, is_episode=True)  # réglage : jamais
    assert not up.should_offer(18, 40, 20, already=False, is_episode=True)  # extrait court
    assert not up.should_offer(0, 2700, 20, already=False, is_episode=True)  # déjà fini


def test_next_item_and_texts():
    items = [{"title": "Good News"}, NEXT]
    assert up.next_in_playlist(items, 0) is NEXT
    assert up.next_in_playlist(items, 1) is None  # dernier de la file
    assert up.next_in_playlist(items, -1) is None  # lecture hors liste
    params = up.popup_params(NEXT)
    assert params == {
        "action": "upnext",
        "show": "Severance",
        "code": "S01E02",
        "title": "Half Loop",
        "line": "S01E02 · Half Loop",
        "thumb": "/vignettes/s01e02.jpg",
    }
    # Fichier sans numéro d'épisode : le titre seul
    assert up.popup_params({"label": "Bonus", "season": -1, "episode": -1})["line"] == "Bonus"


def test_countdown_and_bar():
    assert up.countdown_label(17.6) == "Dans 18 s"
    assert up.countdown_label(0.2) == "Maintenant"
    assert up.bar(20, 20) == "bar-100"
    assert up.bar(10, 20) == "bar-050"
    assert up.bar(0.1, 20) == "bar-000"
    assert up.bar(30, 20) == "bar-100"  # jamais au-delà de la texture pleine
    assert up.bar(5, 0) == "bar-000"


def test_cancel_removes_from_the_end():
    # File : [en cours (2), 3, 4, 5] → on retire 5, puis 4, puis 3
    assert up.positions_to_remove(6, 2) == [5, 4, 3]
    assert up.positions_to_remove(3, 2) == []  # rien après
    assert up.positions_to_remove(4, -1) == []  # lecture hors liste

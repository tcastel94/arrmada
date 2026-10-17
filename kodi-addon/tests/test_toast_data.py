"""Bulles ArrMada dans les écrans ArrMada (appli 1.24.1) : logique sans Kodi."""

from __future__ import annotations

import json

import toast_data as td


def test_clean_drops_glyphs_missing_from_the_tv_font() -> None:
    # Constaté sur la TV : « 📥 » affiché comme un carré vide devant le texte
    assert td.clean("📥 Téléchargement terminé : Game.of.Thrones.S03") == (
        "Téléchargement terminé : Game.of.Thrones.S03"
    )
    assert td.clean("✅ Prêt · 4K ▶ Lire ⚠️") == "Prêt · 4K Lire"
    assert td.clean("  Accents é à ç…  ") == "Accents é à ç…"
    # Flèche de chemin : « › » (dans la police), pas un carré ni un trou
    assert td.clean("Accueil → Réglages → Appairer") == "Accueil › Réglages › Appairer"
    assert td.clean(None) == ""


def test_bubble_bounds_duration_and_heading() -> None:
    item = td.bubble("", "msg", ms=60_000)
    assert item["heading"] == "ArrMada" and item["ms"] == td.MAX_MS
    assert td.bubble("A", "b", ms=100)["ms"] == td.MIN_MS
    assert td.bubble("A", "b", ms="x")["ms"] == td.DEFAULT_MS
    assert td.bubble("A", "b", error=True)["error"] is True


def test_alive() -> None:
    assert td.alive("1000", 1005.0)
    assert not td.alive("1000", 1000.0 + td.BEAT_STALE)
    assert not td.alive("", 1000.0) and not td.alive(None, 1.0)


def test_enqueue_keeps_order_skips_repeats_and_caps() -> None:
    raw = ""
    for index in range(6):
        raw = td.enqueue(raw, td.bubble("H", f"m{index}"))
    raw = td.enqueue(raw, td.bubble("H", "m5"))  # même bulle deux fois de suite
    assert [i["message"] for i in td.decode(raw)] == ["m2", "m3", "m4", "m5"]
    assert td.decode("pas du json") == [] and td.decode(json.dumps({"a": 1})) == []


def test_step_shows_then_clears_then_shows_the_next() -> None:
    queue = td.enqueue(td.enqueue("", td.bubble("A", "1")), td.bubble("B", "2"))
    action, item, queue = td.step(queue, "", 100.0, on_screen=True)
    assert action == "show" and item["heading"] == "A"
    # Affichée jusqu'à 105 : rien à faire avant
    assert td.step(queue, "105", 104.0, True)[0] == "idle"
    # Échue : effacée (un tour vide, pour que l'animation rejoue)
    action, item, queue = td.step(queue, "105", 105.0, True)
    assert action == "clear" and item is None
    action, item, queue = td.step(queue, "", 106.0, True)
    assert action == "show" and item["heading"] == "B" and queue == ""
    assert td.step("", "", 107.0, True) == ("idle", None, "")


def test_step_falls_back_to_kodi_when_the_arrmada_screen_is_left() -> None:
    queue = td.enqueue(td.enqueue("", td.bubble("A", "1")), td.bubble("B", "2"))
    # Bulle affichée, puis on quitte ArrMada (film lancé) : elle disparaît
    assert td.step(queue, "200", 150.0, on_screen=False)[0] == "clear"
    # Les suivantes partent dans la bulle Kodi
    action, item, queue = td.step(queue, "", 151.0, on_screen=False)
    assert action == "fallback" and item["heading"] == "A"


def test_on_screen_condition_names_every_window() -> None:
    assert td.ON_SCREEN.count("Window.IsActive(") == len(td.WINDOWS)
    assert "script-arrmada-pair.xml" not in td.WINDOWS

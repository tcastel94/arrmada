"""Disjoncteur de démarrage du service (incident 1.7.0) : logique pure."""

from __future__ import annotations

from pathlib import Path

import startup_guard as guard


def test_trips_after_two_unfinished_starts(tmp_path: Path) -> None:
    path = guard.state_path(str(tmp_path / "profil"))  # dossier créé à la volée
    tripped = []
    for _ in range(3):  # trois démarrages, Kodi plante à chaque fois avant 2 min
        state, trip = guard.on_start(guard.load(path))
        guard.save(path, state)
        tripped.append(trip)
    assert tripped == [False, False, True]
    # Après le passage en mode minimal, le compteur repart de zéro
    assert guard.load(path)["unfinished_starts"] == 0


def test_healthy_run_resets_the_counter(tmp_path: Path) -> None:
    path = guard.state_path(str(tmp_path))
    state, _ = guard.on_start({})
    guard.save(path, state)
    guard.save(path, guard.healthy())  # 2 min sans souci, ou arrêt propre de Kodi
    for _ in range(2):
        state, trip = guard.on_start(guard.load(path))
        guard.save(path, state)
        assert not trip
    assert not list(tmp_path.rglob("*.tmp"))  # écriture atomique : pas de reste


def test_unreadable_state_starts_from_scratch(tmp_path: Path) -> None:
    path = tmp_path / guard.STATE_FILE
    path.write_text("{pas du json", encoding="utf-8")
    assert guard.load(str(path)) == {}
    assert guard.on_start({"unfinished_starts": "n'importe quoi"}) == (
        {"unfinished_starts": 1},
        False,
    )

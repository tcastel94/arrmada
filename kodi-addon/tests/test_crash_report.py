"""Journal de plantage de Kodi envoyé au serveur (1.21.1) : logique pure."""

from __future__ import annotations

from pathlib import Path

import crash_report as cr

CRASHED = (
    "2026-10-16 18:29:26.555 T:3294 debug <general>: CAddonMgr::UnloadAddon: script.arrmada\n"
    "2026-10-16 18:29:26.572 T:3294 debug <general>: Unpacking zip://...script.arrmada-1.21.1.zip\n"
)
CLEAN = CRASHED + "2026-10-16 18:30:00.000 T:3030 info <general>: Exiting the application...\n"


def test_only_an_abrupt_end_is_sent() -> None:
    assert cr.should_send(CRASHED, "100:1", "")
    assert not cr.should_send(CLEAN, "100:1", "")  # arrêt normal de Kodi
    assert not cr.should_send("", "100:1", "")  # journal vide
    assert not cr.should_send("   \n", "100:1", "")


def test_same_log_is_sent_once() -> None:
    # Le service relancé (mise à jour de l'add-on) relit le même kodi.old.log
    assert not cr.should_send(CRASHED, "100:1", "100:1")
    assert cr.should_send(CRASHED, "200:2", "100:1")


def test_clean_exit_looked_for_at_the_end_only() -> None:
    # La ligne citée plus haut dans le journal (ex. collée dans un message) ne compte pas
    early = "Exiting the application...\n" + "x" * (cr.END_BYTES + 10) + "\n"
    assert cr.should_send(early, "1:1", "")


def test_read_tail_keeps_whole_lines(tmp_path: Path) -> None:
    log = tmp_path / "kodi.old.log"
    lines = [f"ligne {i:04d} " + "é" * 20 for i in range(500)]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tail = cr.read_tail(str(log), max_bytes=1000)
    assert tail.endswith(lines[-1] + "\n")
    assert len(tail.encode("utf-8")) <= 1000
    first = tail.split("\n", 1)[0]
    assert first in lines  # pas de début de ligne coupé (ni de caractère coupé en deux)
    # Petit fichier : rendu en entier
    small = tmp_path / "petit.log"
    small.write_text("a\nb\n", encoding="utf-8")
    assert cr.read_tail(str(small)) == "a\nb\n"


def test_payload_and_state(tmp_path: Path) -> None:
    data = cr.payload(CRASHED, 4242, "21.2 (21.2.0)", "1.21.1")
    assert data == {
        "log": CRASHED,
        "size": 4242,
        "source": "kodi.old.log",
        "kodi_version": "21.2 (21.2.0)",
        "addon_version": "1.21.1",
    }
    path = str(tmp_path / "profil" / cr.STATE_FILE)
    assert cr.load_state(path) == {}
    cr.save_state(path, {"last_sent": cr.fingerprint(4242, 1760000000.7)})
    assert cr.load_state(path) == {"last_sent": "4242:1760000000"}
    Path(path).write_text("{abîmé", encoding="utf-8")
    assert cr.load_state(path) == {}

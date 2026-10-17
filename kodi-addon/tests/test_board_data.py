"""Écran Téléchargements (ADR-005, lot 3) : logique sans Kodi."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import board_data as bd
import screens_data as sd

NOW = datetime(2026, 10, 17, 20, 41, 10)


def _iso(minutes_ago: int) -> str:
    """Instant UTC vu depuis l'heure locale du poste de test (comme le serveur l'envoie)."""
    local = NOW - timedelta(minutes=minutes_ago)
    return local.astimezone(timezone.utc).isoformat()


CARD = {
    "id": 7, "title": "Dune : Deuxième partie", "status": "open", "phase": "downloading",
    "progress": 62.0, "time_left_seconds": 15 * 60, "device_name": "Salon TV",
    "requested_at": _iso(4), "quality": "Bluray-2160p", "size_bytes": 21.4 * 1024**3,
    "mine": True, "can_cancel": True, "arr_id": 12, "service_type": "radarr",
    "poster_url": "http://p", "protocol": "usenet",
}  # fmt: skip


def test_ready_at_rounds_up_and_adds_the_import() -> None:
    assert bd.ready_at(15 * 60, NOW) == "20:59"  # 20:41:10 + 15 min + 2 min → 20:58:10 ↑
    assert bd.ready_at(0, datetime(2026, 1, 1, 9, 0, 0)) == "09:02"  # minute pile : gardée
    assert bd.ready_at(None, NOW) == ""


def test_ago() -> None:
    assert bd.ago(_iso(0), NOW) == "à l'instant"
    assert bd.ago(_iso(4), NOW) == "il y a 4 min"
    assert bd.ago(_iso(130), NOW) == "il y a 2 h"
    assert bd.ago(_iso(9 * 60), NOW) == "à 11:41"
    assert bd.ago("", NOW) == "" and bd.ago("hier", NOW) == ""


def test_downloading_card() -> None:
    model = bd.card_model(CARD, NOW)
    assert model["headline"] == "Prêt vers 20:59"
    assert model["who"] == "Salon TV · il y a 4 min · Bluray-2160p · 21,4 Go"
    assert model["detail"] == "62 %" and model["bar"] == "bar-062"
    assert [model[f"s{i}_state"] for i in range(1, 5)] == ["done", "now", "", ""]
    assert [model[f"s{i}"] for i in range(1, 5)] == ["Trouvé", "Téléchargement", "Import", "Prêt"]
    assert model["hint"] == "OK : Fiche · Annuler"
    torrent = bd.card_model(dict(CARD, protocol="torrent"), NOW)
    assert torrent["detail"].endswith("torrent : pas de priorité possible")


def test_other_phases() -> None:
    searching = bd.card_model(dict(CARD, phase="searching", time_left_seconds=None), NOW)
    assert searching["headline"] == "Recherche d'une version…"
    assert [searching[f"s{i}_state"] for i in range(1, 5)] == ["now", "", "", ""]
    assert "Rechercher" in searching["hint"]
    ready = bd.card_model(dict(CARD, phase="ready", status="done", can_cancel=False), NOW)
    assert ready["headline"] == "Prêt à regarder" and ready["hint"] == "OK : Fiche"
    assert {ready[f"s{i}_state"] for i in range(1, 5)} == {"done"}
    blocked = dict(CARD, phase="blocked", error="Unable to parse episode",
                   blocked_download={"service_type": "radarr", "download_id": "n"})  # fmt: skip
    model = bd.card_model(blocked, NOW)
    assert model["headline"] == "Bloqué" and model["detail"] == "Unable to parse episode"
    assert [model[f"s{i}_state"] for i in range(1, 5)] == ["done", "err", "", ""]
    assert bd.card_actions(blocked)[0] == ("unstick", "Débloquer")
    at_import = bd.card_model(dict(blocked, progress=100.0), NOW)
    assert [at_import[f"s{i}_state"] for i in range(1, 5)] == ["done", "done", "err", ""]
    notfound = bd.card_model(dict(CARD, phase="notfound", status="expired"), NOW)
    assert notfound["headline"] == "Introuvable pour l'instant"
    assert [notfound[f"s{i}_state"] for i in range(1, 5)] == ["err", "", "", ""]


def test_cancel_only_for_my_running_request() -> None:
    assert ("cancel", "Annuler ma demande") in bd.card_actions(CARD)
    assert ("cancel", "Annuler ma demande") not in bd.card_actions(dict(CARD, can_cancel=False))


QUEUE = [
    {"id": 1, "service_type": "radarr", "title": "Past Lives", "status": "downloading",
     "tracked_state": "downloading", "progress": 10, "size_bytes": 10, "size_left_bytes": 9,
     "movie_id": 3, "download_id": "SABnzbd_nzo_a", "protocol": "usenet",
     "poster_url": "http://p"},
    {"id": 2, "service_type": "sonarr", "title": "Show.S01", "status": "paused",
     "tracked_state": "downloading", "series_id": 4, "download_id": "SABnzbd_nzo_b",
     "protocol": "usenet"},
    {"id": 3, "service_type": "sonarr", "title": "Shogun.S01E07", "status": "completed",
     "tracked_state": "importBlocked", "detail": "Unable to parse", "series_id": 5,
     "download_id": "HASH", "protocol": "torrent"},
    {"id": 4, "service_type": "radarr", "title": "Film.torrent", "status": "downloading",
     "tracked_state": "downloading", "movie_id": 6, "download_id": "HASH2",
     "protocol": "torrent"},
]  # fmt: skip


def test_row_actions() -> None:
    model, _ = sd.build_downloads(QUEUE, {}, 0.0)
    rows = model["rows"]
    bd.decorate_rows(rows, QUEUE)
    ops = [[op for op, _ in row["actions"]] for row in rows]
    assert ops == [
        ["top", "pause", "detail"],
        ["top", "resume", "detail"],
        ["unstick", "detail"],
        ["detail"],  # torrent : SABnzbd n'y peut rien
    ]
    assert rows[0]["hint"] == "OK : En tête · Pause · Fiche"
    assert rows[0]["eta_speed"] == "" and rows[2]["eta_speed"] == ""
    assert rows[0]["download_id"] == "SABnzbd_nzo_a" and rows[0]["poster"] == "http://p"


def test_summary() -> None:
    cards = [CARD, dict(CARD, status="done", phase="ready")]
    sab = {"kbpersec": 49356.8, "paused": True}
    assert bd.summary(cards, [{}] * 7, sab) == (
        "1 pour ce soir · 7 en file · 48,2 Mo/s · SABnzbd en pause (sauf ce soir)"
    )
    assert bd.summary([], [], None) == "file vide"


def test_unstick_model() -> None:
    steps = [
        {"state": "ok", "text": "Téléchargé en entier", "detail": "x" * 200},
        {"state": "err", "text": "Radarr n'importe pas tout seul", "detail": ""},
    ]
    diag = {"status": "ok", "action": "Importer", "can_fix": True, "steps": steps}
    model = bd.unstick_model(diag)
    assert model["action"] == "Importer" and model["can_fix"]
    assert model["steps"][0][2].endswith("…") and len(model["steps"][0][2]) == 90
    broken = bd.unstick_model({"status": "error", "message": "Sonarr injoignable"})
    assert broken["steps"] == [("err", "Diagnostic impossible", "Sonarr injoignable")]
    assert not broken["can_fix"]


def test_no_glyph_missing_from_the_tv_font() -> None:
    texts = [bd.card_model(dict(CARD, phase=p), NOW)["headline"] for p in bd._STEP_STATES]
    texts += list(bd.ACTION_LABELS.values()) + list(bd.STEPS)
    assert not any(ch in t for t in texts for ch in "→★✓✔▶⏸●")

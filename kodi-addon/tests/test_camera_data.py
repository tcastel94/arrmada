"""Alertes des caméras Eufy sur la TV (lib/camera_data.py)."""

from __future__ import annotations

from datetime import timedelta, timezone

import camera_data as cam

PARIS_SUMMER = timezone(timedelta(hours=2))
EVENT = {
    "camera": "Entrée",
    "serial": "T8210",
    "detection": "person",
    "label": "Personne détectée",
    "snapshot_id": 4,
    "at": "2026-10-11T19:42:05+00:00",
}


def test_popup_texts_in_local_time():
    texts = cam.popup(EVENT, PARIS_SUMMER)
    assert texts == {
        "title": "Personne détectée",
        "camera": "Entrée",
        "time": "21:42",
        "subtitle": "Entrée · 21:42",
    }
    # Heure illisible ou absente : la caméra seule
    assert cam.popup({"label": "Détection"}, PARIS_SUMMER)["subtitle"] == "Caméra"
    assert cam.clock("pas une date") == ""
    assert cam.clock("2026-10-11T19:42:05Z", PARIS_SUMMER) == "21:42"
    # L'heure donnée par Kodi passe avant (fuseau de Python incertain sur Android)
    assert cam.popup(EVENT, PARIS_SUMMER, local_time="21:43")["subtitle"] == "Entrée · 21:43"


def test_bubble_and_snapshot_ids():
    bubble = cam.bubble(EVENT, "/cache/photo.jpg", PARIS_SUMMER)
    assert bubble == {
        "heading": "Personne détectée",
        "message": "Entrée · 21:42",
        "icon": "/cache/photo.jpg",
    }
    assert cam.snapshot_id(EVENT) == 4
    assert cam.snapshot_id({"snapshot_id": "7"}) == 7  # relevé du faux serveur : texte
    assert cam.snapshot_id({"snapshot_id": None}) == 0
    assert cam.file_name(4, 1791700000) == "arrmada-camera-4-1791700000.jpg"


def test_popup_only_during_playback_and_one_at_a_time():
    assert cam.wants_popup(watching=True, enabled=True, popup_open=False) == "popup"
    assert cam.wants_popup(watching=True, enabled=True, popup_open=True) == "bubble"
    assert cam.wants_popup(watching=False, enabled=True, popup_open=False) == "bubble"
    assert cam.wants_popup(watching=True, enabled=False, popup_open=False) == ""

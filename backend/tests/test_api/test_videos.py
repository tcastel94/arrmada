"""Écran « Vidéos » : dossiers hors médiathèque (mangas Kai, vidéos perso)."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import video_files, watch_sync
from app.services.devices import device_may_call, pairings


async def _pair(client: AsyncClient, admin: dict[str, str]) -> dict[str, str]:
    pairings.clear()
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "ArrMada Android TV"})
    ).json()
    body = {"user_code": start["user_code"], "name": "Shield", "room": "salon"}
    assert (await client.post("/api/devices/pair/confirm", json=body, headers=admin)).is_success
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return {"X-Device-Token": poll["token"]}


@pytest.fixture
def nas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Faux partage : /medias/Kai (épisodes, sous-titres) et un secret à côté."""
    medias = tmp_path / "medias"
    kai = medias / "Kai" / "Dragon Ball Kai"
    kai.mkdir(parents=True)
    for n in (10, 2, 1):
        (kai / f"DBK - Ep {n}.mkv").write_bytes(b"0123456789" * 10)
    (kai / "DBK - Ep 1.fr.srt").write_bytes(
        "1\n00:00:01,000 --> 00:00:02,000\nÉté à Namek\n".encode("cp1252")
    )
    (kai / "DBK - Ep 1.forced.fr.ass").write_text("[Script Info]\n", encoding="utf-8")
    (kai / "notes.txt").write_text("pas une vidéo")
    (kai / ".cache").mkdir()
    (kai / "@eaDir").mkdir()
    (medias / "Kai" / "Bonus").mkdir()
    (tmp_path / "secret.mkv").write_bytes(b"secret")
    (kai / "fuite").symlink_to(tmp_path)  # lien qui sort du dossier racine
    monkeypatch.setattr(settings, "VIDEO_ALLOWED_BASE", str(medias))
    return medias


def test_token_roundtrip_and_rejects() -> None:
    token = video_files.encode_token(3, "Kai/Ep 1.mkv")
    assert video_files.decode_token(token) == (3, "Kai/Ep 1.mkv")
    for bad in ("", "a/b", "../x", base64.urlsafe_b64encode(b"x/y").decode().rstrip("=")):
        with pytest.raises(video_files.NotFound):
            video_files.decode_token(bad)


def test_natural_sort_and_subtitle_labels() -> None:
    names = ["Ep 10.mkv", "Ep 2.mkv", "Ep 1.mkv"]
    assert sorted(names, key=video_files.natural_key) == ["Ep 1.mkv", "Ep 2.mkv", "Ep 10.mkv"]
    assert video_files.subtitle_label("Ep 1", "Ep 1.fr.srt") == ("Français", "fr")
    assert video_files.subtitle_label("Ep 1", "Ep 1.forced.fre.ass") == ("Français (forcés)", "fr")
    assert video_files.subtitle_label("Ep 1", "Ep 1.srt") == ("Externe", "")


def test_root_path_must_be_under_allowed_base(nas: Path) -> None:
    assert video_files.check_root_path(str(nas / "Kai")) == str((nas / "Kai").resolve())
    with pytest.raises(ValueError, match="sous"):
        video_files.check_root_path(str(nas.parent))
    with pytest.raises(ValueError, match="absolu"):
        video_files.check_root_path("medias/Kai")
    with pytest.raises(ValueError, match="introuvable"):
        video_files.check_root_path(str(nas / "absent"))


def test_watch_state_accepts_files() -> None:
    state = watch_sync.normalize(
        {
            "media_type": "file",
            "id_type": "sha1",
            "id": "a" * 40,
            "title": "DBK - Ep 1",
            "position": 120,
            "total": 1400,
        }
    )
    assert state is not None and state["key"].startswith("file:sha1:")


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/videos/browse", True),
        ("GET", "/api/videos/play/MS9LYWk", True),
        ("GET", "/api/videos/stream/MS9LYWk", True),
        ("GET", "/api/videos/subtitle/MS9LYWk", True),
        ("GET", "/api/videos/stream/../../etc", False),
        ("GET", "/api/videos/roots", False),
        ("POST", "/api/videos/roots", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_browse_play_stream_from_a_tv(
    client: AsyncClient, auth_headers: dict[str, str], nas: Path
) -> None:
    # La web app déclare le dossier
    created = await client.post(
        "/api/videos/roots",
        json={"name": "Mangas Kai", "path": str(nas / "Kai")},
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["available"] is True
    dup = await client.post(
        "/api/videos/roots", json={"name": "Encore", "path": str(nas / "Kai")}, headers=auth_headers
    )
    assert dup.status_code == 409
    outside = await client.post(
        "/api/videos/roots", json={"name": "Tout", "path": str(nas.parent)}, headers=auth_headers
    )
    assert outside.status_code == 422

    tv = await _pair(client, auth_headers)
    assert (await client.post("/api/videos/roots", json={}, headers=tv)).status_code == 403

    top = (await client.get("/api/videos/browse", headers=tv)).json()
    assert [f["name"] for f in top["folders"]] == ["Mangas Kai"]
    kai = (
        await client.get(
            "/api/videos/browse", params={"path": top["folders"][0]["token"]}, headers=tv
        )
    ).json()
    assert [f["name"] for f in kai["folders"]] == [
        "Bonus",
        "Dragon Ball Kai",
    ]  # ni .cache ni @eaDir
    dbk_token = kai["folders"][1]["token"]
    dbk = (await client.get("/api/videos/browse", params={"path": dbk_token}, headers=tv)).json()
    assert [f["title"] for f in dbk["files"]] == ["DBK - Ep 1", "DBK - Ep 2", "DBK - Ep 10"]
    assert [f["name"] for f in dbk["folders"]] == ["fuite"]  # listé, mais impossible à ouvrir
    assert [c["name"] for c in dbk["crumbs"]] == ["Mangas Kai", "Dragon Ball Kai"]
    assert dbk["parent"] == top["folders"][0]["token"]
    ep1 = dbk["files"][0]
    assert ep1["subtitles"] == 2 and len(ep1["watch_id"]) == 40

    # Le lien symbolique qui sort du dossier : refusé
    escaped = await client.get(
        "/api/videos/browse", params={"path": dbk["folders"][0]["token"]}, headers=tv
    )
    assert escaped.status_code == 404
    # « ../ » dans un jeton fabriqué à la main : refusé
    forged = video_files.encode_token(created.json()["id"], "../secret.mkv")
    assert (await client.get(f"/api/videos/stream/{forged}", headers=tv)).status_code == 404

    # Infos de lecture : même format que /api/tv/play, sous-titres à côté
    info = (await client.get(f"/api/videos/play/{ep1['token']}", headers=tv)).json()
    assert info["status"] == "ok" and info["title"] == "DBK - Ep 1"
    assert info["watch_id"] == ep1["watch_id"]
    assert [(s["label"], s["mime"]) for s in info["subtitles"]] == [
        ("Français (forcés)", "text/x-ssa"),
        ("Français", "application/x-subrip"),
    ]

    # Flux avec Range (avance rapide du lecteur)
    part = await client.get(info["stream"], headers={**tv, "Range": "bytes=10-19"})
    assert part.status_code == 206
    assert part.content == b"0123456789"
    assert part.headers["content-type"] == "video/x-matroska"

    # Sous-titre Windows-1252 servi en UTF-8
    srt = next(s for s in info["subtitles"] if s["label"] == "Français")
    sub = await client.get(srt["url"], headers=tv)
    assert sub.status_code == 200 and "Été à Namek" in sub.text
    assert "charset=utf-8" in sub.headers["content-type"]
    # Un fichier qui n'est ni vidéo ni sous-titre n'est jamais servi
    notes = video_files.encode_token(created.json()["id"], "Dragon Ball Kai/notes.txt")
    assert (await client.get(f"/api/videos/stream/{notes}", headers=tv)).status_code == 404
    assert (await client.get(f"/api/videos/subtitle/{notes}", headers=tv)).status_code == 404

    # Vu / reprise de la vidéo, enregistré comme pour un film
    saved = await client.post(
        "/api/kodi/watch-state",
        json={
            "states": [
                {
                    "media_type": "file",
                    "id_type": "sha1",
                    "id": ep1["watch_id"],
                    "title": "DBK - Ep 1",
                    "watched": False,
                    "position": 300,
                    "total": 1400,
                    "last_played": "2026-10-21 20:00:00",
                }
            ]
        },
        headers=tv,
    )
    assert saved.status_code == 200, saved.text
    states = (await client.get("/api/kodi/watch-state", headers=tv)).json()["states"]
    assert any(s["media_type"] == "file" and s["position"] == 300 for s in states)

    # Retirer le dossier : plus rien n'est accessible (le disque n'est pas touché)
    root_id = created.json()["id"]
    renamed = await client.patch(
        f"/api/videos/roots/{root_id}", json={"name": "Kai"}, headers=auth_headers
    )
    assert renamed.json()["name"] == "Kai"
    assert (await client.delete(f"/api/videos/roots/{root_id}", headers=auth_headers)).is_success
    assert (await client.get(info["stream"], headers=tv)).status_code == 404
    assert (nas / "Kai" / "Dragon Ball Kai" / "DBK - Ep 1.mkv").exists()

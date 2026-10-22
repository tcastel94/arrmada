"""Séries maison (Naruto Kai, One Pace…) : un dossier vidéo vu comme une série."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.api import local_series as api
from app.config import settings
from app.services import local_series as scanner
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
def kai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """/medias/Mangas/Naruto Kai : deux arcs, un NFO d'épisode, une vignette, une affiche."""
    medias = tmp_path / "medias"
    show = medias / "Mangas" / "Naruto Kai"
    arc1 = show / "Arc 01 - Pays des Vagues"
    arc2 = show / "Arc 02 - Examen Chunin"
    arc1.mkdir(parents=True)
    arc2.mkdir()
    (arc1 / "[Kaizoku] Naruto Kai - 002 - Le ninja copieur [1080p].mkv").write_bytes(b"v")
    (arc1 / "[Kaizoku] Naruto Kai - 001 - Uzumaki Naruto [1080p].mkv").write_bytes(b"v")
    (arc1 / "[Kaizoku] Naruto Kai - 001 - Uzumaki Naruto [1080p]-thumb.jpg").write_bytes(
        b"\xff\xd8"
    )
    (arc2 / "Naruto Kai - 015.mkv").write_bytes(b"v")
    (arc2 / "Naruto Kai - 015.nfo").write_text(
        "<episodedetails><title>L'examen commence</title><plot>Les genins arrivent.</plot>"
        "<episode>15</episode></episodedetails>",
        encoding="utf-8",
    )
    (arc2 / "Naruto Kai - 016.mkv").write_bytes(b"v")
    (show / "poster.jpg").write_bytes(b"\xff\xd8poster")
    (show / "tvshow.nfo").write_text(
        "<tvshow><plot>Naruto sans remplissage.</plot><year>2002</year></tvshow>"
    )
    (show / "Bonus").mkdir()  # sans vidéo : pas une saison
    monkeypatch.setattr(settings, "VIDEO_ALLOWED_BASE", str(medias))
    monkeypatch.setattr(settings, "TMDB_API_KEY", "")
    api._scans.clear()
    return medias


@pytest.mark.parametrize(
    ("stem", "number", "title"),
    [
        ("[Kaizoku] Naruto Kai - 015 - Le Pays des Vagues [1080p]", 15, "Le Pays des Vagues"),
        ("Naruto Shippuden Kai S02E07 - Retour", 7, "Retour"),
        ("One Pace - Episode 3 - Romance Dawn", 3, "Romance Dawn"),
        ("Naruto Kai 22 Le combat", 22, "Le combat"),
        ("Naruto Kai - 004 (2002) x265", 4, "Épisode 4"),
        ("Épisode 9", 9, "Épisode 9"),
    ],
)
def test_episode_names(stem: str, number: int, title: str) -> None:
    assert scanner.episode_number(stem, "Naruto Kai") == number
    assert scanner.clean_title(stem, "Naruto Kai", number) == title


def test_season_numbers() -> None:
    assert [
        scanner.season_number(n) for n in ("Saison 2", "Arc 03 - Vagues", "S04", "05 - Chunin")
    ] == [2, 3, 4, 5]
    assert scanner.season_number("Bonus") is None


def test_scan_reads_arcs_nfo_and_images(kai: Path) -> None:
    root = scanner.Root(1, "Mangas", str(kai / "Mangas"))
    result = scanner.scan(root, kai / "Mangas" / "Naruto Kai", "Naruto Kai", "Naruto Kai")
    assert [(s.number, s.name) for s in result.seasons] == [
        (1, "Arc 01 - Pays des Vagues"),
        (2, "Arc 02 - Examen Chunin"),
    ]
    arc1, arc2 = result.seasons
    assert [(e.number, e.title) for e in arc1.episodes] == [
        (1, "Uzumaki Naruto"),
        (2, "Le ninja copieur"),
    ]
    assert arc1.episodes[0].image and not arc1.episodes[1].image
    assert [(e.number, e.title, e.overview) for e in arc2.episodes] == [
        (15, "L'examen commence", "Les genins arrivent."),
        (16, "Épisode 16", None),
    ]
    assert result.overview == "Naruto sans remplissage." and result.year == 2002
    assert result.poster and result.fanart is None


def test_ambiguous_numbers_fall_back_to_order(tmp_path: Path) -> None:
    show = tmp_path / "Kai"
    show.mkdir()
    for name in ("Partie B.mkv", "Partie A.mkv", "Partie C.mkv"):
        (show / name).write_bytes(b"v")
    result = scanner.scan(scanner.Root(1, "x", str(tmp_path)), show, "Kai", "Kai")
    assert [(e.number, e.title) for e in result.seasons[0].episodes] == [
        (1, "Partie A"),
        (2, "Partie B"),
        (3, "Partie C"),
    ]
    assert result.seasons[0].name == "Saison 1"


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/videos/series", True),
        ("GET", "/api/videos/series/index", True),
        ("GET", "/api/videos/series/3", True),
        ("GET", "/api/videos/image/MS9LYWk", True),
        ("GET", "/api/videos/series/tmdb/search", False),
        ("POST", "/api/videos/series", False),
        ("DELETE", "/api/videos/series/3", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_local_series_end_to_end(
    client: AsyncClient, auth_headers: dict[str, str], kai: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = (
        await client.post(
            "/api/videos/roots",
            json={"name": "Mangas", "path": str(kai / "Mangas")},
            headers=auth_headers,
        )
    ).json()

    # Série officielle pour l'affiche (TMDB simulé)
    async def fake_tmdb(endpoint: str, params: dict | None = None) -> dict:
        assert endpoint == "/tv/46260"
        return {
            "poster_path": "/naruto.jpg",
            "backdrop_path": "/fond.jpg",
            "overview": "Ninja.",
            "first_air_date": "2002-10-03",
        }

    monkeypatch.setattr(api, "_tmdb", fake_tmdb)
    body = {"root_id": root["id"], "path": "Naruto Kai", "title": "Naruto Kai", "tmdb_id": 46260}
    created = await client.post("/api/videos/series", json=body, headers=auth_headers)
    assert created.status_code == 200, created.text
    series = created.json()
    assert series["episodes"] == 4 and series["seasons"] == 2 and series["badge"] == "Kai"
    assert series["poster_url"].startswith("/api/videos/image/")  # poster.jpg du dossier d'abord
    assert series["fanart_url"] == "https://image.tmdb.org/t/p/w1280/fond.jpg"  # sinon TMDB
    assert series["year"] == 2002

    assert (
        await client.post("/api/videos/series", json=body, headers=auth_headers)
    ).status_code == 409
    bad = {**body, "path": "../../etc"}
    assert (
        await client.post("/api/videos/series", json=bad, headers=auth_headers)
    ).status_code == 422

    tv = await _pair(client, auth_headers)
    assert (await client.post("/api/videos/series", json=body, headers=tv)).status_code == 403
    grid = (await client.get("/api/videos/series", headers=tv)).json()["items"]
    assert [s["title"] for s in grid] == ["Naruto Kai"]

    detail = (await client.get(f"/api/videos/series/{series['id']}", headers=tv)).json()
    assert [s["name"] for s in detail["seasons"]] == [
        "Arc 01 - Pays des Vagues",
        "Arc 02 - Examen Chunin",
    ]
    first = detail["seasons"][0]["episodes"][0]
    assert first["title"] == "Uzumaki Naruto" and first["image"].startswith("/api/videos/image/")

    # Même vu que l'écran Vidéos (même empreinte), même lecture
    play = (await client.get(f"/api/videos/play/{first['token']}", headers=tv)).json()
    assert play["watch_id"] == first["watch_id"]
    index = (await client.get("/api/videos/series/index", headers=tv)).json()["items"]
    assert {(i["season"], i["episode"]) for i in index} == {(1, 1), (1, 2), (2, 15), (2, 16)}

    # Web app : vu / reprise par épisode (même clé que l'écran Vidéos et la TV)
    state = {"media_type": "file", "id_type": "sha1", "id": first["watch_id"], "title": "Ep 1",
             "watched": False, "position": 420, "total": 1400, "last_played": "2026-10-22 20:00:00"}  # fmt: skip
    saved = await client.post("/api/kodi/watch-state", json={"states": [state]}, headers=tv)
    assert saved.status_code == 200, saved.text
    with_states = (
        await client.get(f"/api/videos/series/{series['id']}?states=true", headers=auth_headers)
    ).json()
    eps = [ep for season in with_states["seasons"] for ep in season["episodes"]]
    assert eps[0]["state"] == {"watched": False, "position": 420, "total": 1400}
    assert eps[1]["state"] is None
    assert "state" not in detail["seasons"][0]["episodes"][0]  # sans ?states : inchangé

    # « Sur la TV » depuis la web app : la TV reçoit le jeton du fichier et la reprise
    tv_id = (await client.get("/api/devices/me", headers=tv)).json()["id"]
    sent = await client.post(
        "/api/kodi/play-on-device",
        json={"media_type": "file", "id_type": "sha1", "id": first["watch_id"], "title": "Naruto Kai",
              "season": 1, "episode": 1, "file": first["token"], "local_series": series["id"],
              "start": 420, "device_id": tv_id},
        headers=auth_headers,
    )  # fmt: skip
    assert sent.status_code == 200, sent.text
    events = (await client.get("/api/events/recent?since_id=0", headers=tv)).json()
    request = next(e["data"] for e in events["events"] if e["type"] == "play_request")
    assert (request["media_type"], request["file"], request["local_series"], request["start"]) == (
        "file", first["token"], series["id"], 420,
    )  # fmt: skip
    forged = {"media_type": "file", "id_type": "sha1", "id": first["watch_id"], "file": "../etc",
              "device_id": tv_id}  # fmt: skip
    assert (
        await client.post("/api/kodi/play-on-device", json=forged, headers=auth_headers)
    ).status_code == 422

    thumb = await client.get(first["image"], headers=tv)
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    video_as_image = f"/api/videos/image/{first['token']}"
    assert (
        await client.get(video_as_image, headers=tv)
    ).status_code == 404  # une vidéo n'est pas une image

    # Renommer, puis retirer le dossier racine : la série disparaît, le disque est intact
    renamed = await client.patch(
        f"/api/videos/series/{series['id']}",
        json={"title": "Naruto (Kai)", "badge": "Fan edit"},
        headers=auth_headers,
    )
    assert renamed.json()["title"] == "Naruto (Kai)" and renamed.json()["badge"] == "Fan edit"
    assert (await client.delete(f"/api/videos/roots/{root['id']}", headers=auth_headers)).is_success
    assert (await client.get("/api/videos/series", headers=tv)).json()["items"] == []
    assert (kai / "Mangas" / "Naruto Kai" / "poster.jpg").exists()


async def test_tmdb_search_needs_key(
    client: AsyncClient, auth_headers: dict[str, str], kai: Path
) -> None:
    response = await client.get(
        "/api/videos/series/tmdb/search", params={"q": "naruto"}, headers=auth_headers
    )
    assert response.status_code == 400

"""Apple TV comme cible d'envoi (services/appletv.py) : liens signés, appairage,
aiguillage du cast et de « Sur la TV ». pyatv n'est jamais appelé : ses
fonctions sont remplacées, comme le réseau dans les autres tests."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote, urlsplit

import pytest
from httpx import AsyncClient

from app.database import get_db
from app.main import app
from app.models.cast import CastDevice
from app.services import appletv, jellyfin, tv_playback

ITEM = "fe336042c1c2ef4cecf823f092655c5f"
CREDS = {"airplay": "a:b:c:d", "companion": "e:f:g:h"}


@contextlib.asynccontextmanager
async def TestSessionFactory() -> AsyncIterator[Any]:  # noqa: N802 (même nom que conftest)
    """Session sur la base de test, celle que l'API utilise (conftest.py)."""
    sessions = app.dependency_overrides[get_db]()
    try:
        yield await sessions.__anext__()
    finally:
        await sessions.aclose()


async def _apple_tv(paired: bool = True, name: str = "Chambre") -> int:
    async with TestSessionFactory() as db:
        device = CastDevice(
            uuid="A3D51893-5EAB-47A3-883D-F667F48A45AD",
            name=name,
            ip="192.168.2.235",
            port=7000,
            model="Apple TV 4K (gen 3)",
            kind=appletv.KIND,
            credentials=appletv.dump_credentials(CREDS) if paired else None,
        )
        db.add(device)
        await db.commit()
        return device.id


@pytest.fixture
def played(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Jellyfin et l'Apple TV simulés ; rend ce qui a été demandé à l'Apple TV."""
    seen: dict[str, Any] = {"result": {"status": "casting", "player_state": "PLAYING"}}

    async def movie(_db: Any, tmdb_id: int) -> dict[str, Any] | None:
        if tmdb_id != 136400:
            return None
        return {
            "url": "http://jf/x",
            "content_type": "video/mp4",
            "title": "2 Guns",
            "item_id": ITEM,
        }

    async def episode(_db: Any, tvdb_id: int, season: int, number: int) -> dict[str, Any]:
        title = f"The Expanse · S{season:02d}E{number:02d} · Dulcinea"
        return {"url": "http://jf/y", "content_type": "video/mp4", "title": title, "item_id": ITEM}

    async def suffix(_db: Any, _item_id: str) -> str:
        return ".mkv"

    async def play(ip: str, credentials: dict[str, str], url: str) -> dict[str, Any]:
        seen.update(ip=ip, credentials=credentials, url=url)
        return seen["result"]

    def track(device_id: int, _ip: str, _creds: dict, media: dict, name: str) -> None:
        seen.update(tracked=media, tracked_on=name, tracked_id=device_id)

    monkeypatch.setattr(jellyfin, "build_movie_stream", movie)
    monkeypatch.setattr(jellyfin, "build_episode_stream", episode)
    monkeypatch.setattr(tv_playback, "file_suffix", suffix)
    monkeypatch.setattr(appletv, "play", play)
    monkeypatch.setattr(appletv, "start_tracking", track)
    return seen


# ── Fonctions pures ──────────────────────────────────────────────────────────


def test_target_ids_never_collide_with_paired_tvs() -> None:
    assert appletv.target_id(3) == 1_000_003
    assert appletv.from_target_id(1_000_003) == 3
    assert appletv.from_target_id(3) is None  # une TV appairée garde son numéro


def test_file_name_is_what_vlc_shows_as_title() -> None:
    assert appletv.file_name("Amélie Poulain : le film ?", ".MKV") == "Amelie Poulain le film.mkv"
    assert (
        appletv.file_name("The Expanse · S01E01 · Dulcinea", ".mp4")
        == "The Expanse S01E01 Dulcinea.mp4"
    )
    assert appletv.file_name(None) == "video.mkv"
    assert appletv.file_name("x", "../../etc") == "x.mkv"  # extension douteuse : ignorée


def test_signed_link_is_checked_and_expires() -> None:
    path = appletv.file_path(ITEM, "2 Guns", ".mkv", now=1_000)
    _, _, _, _, expires, signature, item_id, name = path.split("/")
    assert item_id == ITEM and unquote(name) == "2 Guns.mkv"
    assert int(expires) == 1_000 + appletv.LINK_TTL
    assert appletv.check_link(ITEM, int(expires), signature, now=2_000)
    assert not appletv.check_link(ITEM, int(expires), signature, now=int(expires) + 1)  # expiré
    assert not appletv.check_link("0" * 32, int(expires), signature, now=2_000)  # autre fichier
    assert not appletv.check_link(ITEM, int(expires) + 60, signature, now=2_000)  # durée rallongée
    assert not appletv.check_link("../etc/passwd", int(expires), signature, now=2_000)


def test_vlc_link_carries_the_whole_url_encoded() -> None:
    link = appletv.vlc_link("http://192.168.2.3:3420/api/cast/file/1/ab/cd/2%20Guns.mkv")
    assert link.startswith(
        "vlc-x-callback://x-callback-url/stream?url=http%3A%2F%2F192.168.2.3%3A3420"
    )
    assert "%2520Guns" in link  # déjà encodé une fois, ré-encodé pour tenir dans le lien


def test_player_state_uses_the_chromecast_words() -> None:
    assert appletv.player_state("Playing") == "PLAYING"
    assert appletv.player_state("Paused") == "PAUSED"
    assert appletv.player_state("Loading") == "BUFFERING"
    assert appletv.player_state("Stopped") == appletv.player_state("Idle") == "IDLE"


def test_watch_state_marks_watched_at_90_percent() -> None:
    media = {"media_type": "movie", "id_type": "tmdb", "id": "136400", "title": "2 Guns"}
    now = datetime(2026, 11, 22, 19, 0, tzinfo=UTC)
    resume = appletv.watch_state(media, 600, 6549, now)
    assert (resume["watched"], resume["position"], resume["total"]) == (False, 600, 6549)
    assert resume["last_played"] == "2026-11-22 19:00:00"
    done = appletv.watch_state(media, 6000, 6549, now)
    assert (done["watched"], done["position"]) == (True, 0)  # vu : plus de reprise


def test_credentials_are_encrypted_and_need_both_protocols() -> None:
    stored = appletv.dump_credentials(CREDS)
    assert stored and "a:b:c:d" not in stored
    assert appletv.load_credentials(stored) == CREDS and appletv.is_paired(stored)
    half = appletv.dump_credentials({"airplay": "a:b:c:d"})
    assert not appletv.is_paired(half) and not appletv.is_paired(None)
    assert appletv.load_credentials("pas-du-fernet") == {}  # valeur abîmée : à ré-appairer


# ── Bouton « Caster » de la web app ──────────────────────────────────────────


async def test_devices_list_tells_kind_and_pairing(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _apple_tv(paired=False)
    (device,) = (await client.get("/api/cast/devices", headers=auth_headers)).json()
    assert (device["kind"], device["paired"], device["video_capable"]) == ("appletv", False, True)
    assert "credentials" not in device


async def test_cast_play_opens_the_original_file_in_vlc(
    client: AsyncClient, auth_headers: dict[str, str], played: dict[str, Any]
) -> None:
    device_id = await _apple_tv()
    body = {"device_id": device_id, "tmdb_id": 136400, "title": "2 Guns"}
    result = (await client.post("/api/cast/play", json=body, headers=auth_headers)).json()
    assert result["status"] == "casting"
    assert played["ip"] == "192.168.2.235" and played["credentials"] == CREDS

    # Le lien pointe sur le serveur (jamais sur Jellyfin ni sa clé) et il est signé
    url = urlsplit(played["url"])
    assert url.netloc == "test:3420" and "jf" not in played["url"]
    _, _, _, _, expires, signature, item_id, name = url.path.split("/")
    assert appletv.check_link(item_id, int(expires), signature) and unquote(name) == "2 Guns.mkv"
    # La reprise sera partagée sous la même clé que les TV (TMDB du film)
    assert played["tracked"] == {
        "media_type": "movie", "id_type": "tmdb", "id": "136400",
        "season": None, "episode": None, "title": "2 Guns",
    }  # fmt: skip
    assert played["tracked_on"] == "Chambre"


async def test_cast_play_refuses_an_unpaired_apple_tv(
    client: AsyncClient, auth_headers: dict[str, str], played: dict[str, Any]
) -> None:
    device_id = await _apple_tv(paired=False)
    body = {"device_id": device_id, "tmdb_id": 136400}
    result = (await client.post("/api/cast/play", json=body, headers=auth_headers)).json()
    assert result["status"] == "error" and "appairée" in result["detail"]
    assert "url" not in played  # rien n'a été envoyé à l'Apple TV


async def test_stop_saves_the_exact_position(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    device_id = await _apple_tv()
    finished: list[tuple[Any, ...]] = []

    async def control(_ip: str, _creds: dict, action: str, _value: Any = None) -> dict[str, Any]:
        return {"status": "ok", "action": action, "current_time": 615, "duration": 6549}

    async def finish(dev: int, position: Any, total: Any) -> None:
        finished.append((dev, position, total))

    monkeypatch.setattr(appletv, "control", control)
    monkeypatch.setattr(appletv, "finish_tracking", finish)
    body = {"device_id": device_id, "action": "pause"}
    assert (await client.post("/api/cast/control", json=body, headers=auth_headers)).json()[
        "status"
    ] == "ok"
    assert finished == []  # une pause ne termine pas le suivi
    body["action"] = "stop"
    await client.post("/api/cast/control", json=body, headers=auth_headers)
    assert finished == [(device_id, 615, 6549)]


# ── Appairage ────────────────────────────────────────────────────────────────


async def test_pairing_stores_credentials_once_both_codes_are_in(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    device_id = await _apple_tv(paired=False)
    answers = [
        {"status": "pin", "protocol": "companion", "step": 2, "steps": 2},
        {"status": "paired", "credentials": dict(CREDS)},
    ]

    async def start(_device_id: int, _ip: str) -> dict[str, Any]:
        return {"status": "pin", "protocol": "airplay", "step": 1, "steps": 2}

    async def pin(_device_id: int, _ip: str, code: str) -> dict[str, Any]:
        assert code == "0236"  # zéro de tête conservé
        return answers.pop(0)

    monkeypatch.setattr(appletv, "pair_start", start)
    monkeypatch.setattr(appletv, "pair_pin", pin)
    base = f"/api/cast/appletv/{device_id}"
    assert (await client.post(f"{base}/pair", headers=auth_headers)).json()["step"] == 1
    second = (await client.post(f"{base}/pin", json={"pin": " 0236 "}, headers=auth_headers)).json()
    assert second["status"] == "pin" and second["step"] == 2
    (device,) = (await client.get("/api/cast/devices", headers=auth_headers)).json()
    assert device["paired"] is False  # un seul code : pas encore utilisable
    done = (await client.post(f"{base}/pin", json={"pin": "0236"}, headers=auth_headers)).json()
    assert done == {"status": "paired"}  # les identifiants ne sortent pas du serveur
    (device,) = (await client.get("/api/cast/devices", headers=auth_headers)).json()
    assert device["paired"] is True


async def test_pairing_a_chromecast_is_refused(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    async with TestSessionFactory() as db:
        cast = CastDevice(
            uuid="11111111-2222-3333-4444-555555555555", name="Salon", ip="192.168.2.9"
        )
        db.add(cast)
        await db.commit()
    result = (await client.post(f"/api/cast/appletv/{cast.id}/pair", headers=auth_headers)).json()
    assert result["status"] == "error"


async def test_pin_without_a_pairing_in_progress_is_an_error() -> None:
    result = await appletv.pair_pin(999, "192.168.2.235", "1234")
    assert result["status"] == "error" and "expiré" in result["detail"]


# ── « Sur la TV » du téléphone ───────────────────────────────────────────────


async def test_phone_sees_paired_apple_tvs_and_plays_on_them(
    client: AsyncClient, auth_headers: dict[str, str], played: dict[str, Any]
) -> None:
    device_id = await _apple_tv()
    await _unpaired_twin()
    targets = (await client.get("/api/tv/targets", headers=auth_headers)).json()["items"]
    assert targets == [
        {
            "id": 1_000_000 + device_id,
            "name": "Chambre",
            "room": "",
            "online": True,
            "kind": "appletv",
        }
    ]  # la jumelle non appairée n'est pas proposée

    body = {
        "media_type": "episode",
        "id": "280619",
        "season": 1,
        "episode": 1,
        "title": "The Expanse",
    }
    sent = await client.post(
        f"/api/tv/targets/{targets[0]['id']}/play", json=body, headers=auth_headers
    )
    assert sent.status_code == 200, sent.text
    assert sent.json() == {
        "status": "ok",
        "online": True,
        "message": "Lecture lancée sur Chambre (VLC)",
    }
    assert unquote(played["url"]).endswith("/The Expanse S01E01 Dulcinea.mkv")
    assert played["tracked"]["id_type"] == "tvdb" and played["tracked"]["season"] == 1


async def _unpaired_twin() -> None:
    async with TestSessionFactory() as db:
        db.add(
            CastDevice(
                uuid="B3D51893-5EAB-47A3-883D-F667F48A45AD",
                name="Bureau",
                ip="192.168.2.236",
                kind=appletv.KIND,
            )
        )
        await db.commit()


async def test_phone_gets_the_reason_when_playback_fails(
    client: AsyncClient, auth_headers: dict[str, str], played: dict[str, Any]
) -> None:
    device_id = await _apple_tv()
    played["result"] = {"status": "error", "detail": "VLC n'est pas installé sur cette Apple TV."}
    target = f"/api/tv/targets/{1_000_000 + device_id}/play"
    failed = await client.post(
        target, json={"media_type": "movie", "id": "136400"}, headers=auth_headers
    )
    assert failed.status_code == 502 and "VLC" in failed.json()["detail"]
    missing = await client.post(
        target, json={"media_type": "movie", "id": "1"}, headers=auth_headers
    )
    assert missing.status_code == 404  # absent de Jellyfin
    invalid = await client.post(
        target, json={"media_type": "file", "id": "x"}, headers=auth_headers
    )
    assert invalid.status_code == 422


# ── Lien signé lu par VLC (sans session) ─────────────────────────────────────


async def test_signed_file_is_served_without_a_session_but_only_if_signed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[Any, ...]] = []

    async def open_stream(_db: Any, item_id: str, range_header: str | None, warm: bool = True):
        opened.append((item_id, range_header, warm))

        async def body():
            yield b"film"

        return 206, {"content-range": "bytes 0-3/4"}, body()

    monkeypatch.setattr(tv_playback, "open_stream", open_stream)
    path = appletv.file_path(ITEM, "2 Guns")
    served = await client.get(path, headers={"Range": "bytes=0-3"})
    assert served.status_code == 206 and served.content == b"film"
    assert opened == [(ITEM, "bytes=0-3", False)]  # pas de préparation 1080p pour VLC

    parts = path.split("/")
    parts[5] = "0" * 32  # signature falsifiée
    assert (await client.get("/".join(parts))).status_code == 403
    assert len(opened) == 1


# ── Scan du réseau ───────────────────────────────────────────────────────────


async def test_rescan_updates_a_known_apple_tv_and_keeps_its_pairing(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import cast as cast_service

    device_id = await _apple_tv()
    found = {
        "uuid": "A3D51893-5EAB-47A3-883D-F667F48A45AD",
        "name": "Chambre Parentale",
        "ip": "192.168.2.240",  # adresse changée (DHCP)
        "port": 7000,
        "model": "Apple TV 4K (gen 3) · tvOS 27.2.1",
        "video_capable": True,
        "kind": appletv.KIND,
    }

    async def no_subnets(_db: Any) -> set[str]:
        return set()

    async def apple_tvs(_db: Any) -> list[dict[str, Any]]:
        return [dict(found)]

    monkeypatch.setattr(cast_service, "_subnets", no_subnets)
    monkeypatch.setattr(cast_service, "_discover_apple_tvs", apple_tvs)
    for _ in range(2):  # le second passage retrouve une ligne existante
        scan = await client.post("/api/cast/discover", headers=auth_headers)
        assert scan.status_code == 200, scan.text
    (device,) = scan.json()
    assert (device["id"], device["name"], device["ip"]) == (
        device_id,
        "Chambre Parentale",
        "192.168.2.240",
    )
    assert device["paired"] is True

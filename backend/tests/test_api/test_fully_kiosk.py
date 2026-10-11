"""Tablette du salon en mode kiosk pendant un média (Fully Kiosk Remote Admin)."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from httpx import AsyncClient

from app.services import fully_kiosk
from app.services.devices import pairings
from app.services.fully_kiosk import KioskController, KioskTarget
from app.services.now_playing import now_playing

TABLET = KioskTarget(1, "Pixel Tablet", "192.168.1.50", 2323, "secret")
_ASYNC_CLIENT = httpx.AsyncClient  # gardé : un test remplace httpx.AsyncClient


class FakeFully:
    """Faux Fully Kiosk : note les commandes reçues, répond comme la vraie API."""

    def __init__(self, password: str = "secret", down: bool = False) -> None:
        self.password = password
        self.down = down
        self.commands: list[str] = []
        self.hosts: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("injoignable", request=request)
        self.hosts.append(f"{request.url.host}:{request.url.port}")
        if request.url.params.get("password") != self.password:
            return httpx.Response(200, json={"status": "Error", "statustext": "Please login"})
        command = request.url.params.get("cmd", "")
        self.commands.append(command)
        if command == "deviceInfo":
            return httpx.Response(200, json={"deviceName": "Pixel Tablet", "kioskMode": True})
        return httpx.Response(200, json={"status": "OK", "statustext": f"{command} done"})

    def client(self) -> httpx.AsyncClient:
        return _ASYNC_CLIENT(transport=httpx.MockTransport(self.handler))


@pytest.fixture(autouse=True)
def _clean():
    pairings.clear()
    now_playing.clear()
    yield
    pairings.clear()
    now_playing.clear()


def _controller(fully: FakeFully, targets=None, **kwargs) -> KioskController:
    async def load(room: str) -> list[KioskTarget]:
        return list(targets if targets is not None else [TABLET]) if room == "salon" else []

    return KioskController(load, client_factory=fully.client, **kwargs)


# ── Pilotage ──────────────────────────────────────────────────


async def test_play_locks_once_and_stop_releases_after_grace() -> None:
    fully = FakeFully()
    ctl = _controller(fully, stop_grace=0.05, watch_every=60)
    await ctl.on_playback("salon", "play")
    assert fully.commands == ["screenOn", "toForeground", "loadStartURL", "lockKiosk"]
    assert ctl.is_locked("salon")
    await ctl.on_playback("salon", "progress")  # déjà verrouillée : rien de plus
    assert len(fully.commands) == 4
    await ctl.on_playback("salon", "stop")
    assert ctl.is_locked("salon")  # pas tout de suite : épisode suivant possible
    await asyncio.sleep(0.15)
    assert fully.commands[-2:] == ["unlockKiosk", "toBackground"]
    assert not ctl.is_locked("salon")
    await ctl.shutdown()


async def test_next_episode_within_grace_keeps_the_tablet_locked() -> None:
    fully = FakeFully()
    ctl = _controller(fully, stop_grace=0.1, watch_every=60)
    await ctl.on_playback("salon", "play")
    await ctl.on_playback("salon", "stop")  # fin de l'épisode…
    await ctl.on_playback("salon", "play")  # … le suivant démarre
    await asyncio.sleep(0.2)
    assert "unlockKiosk" not in fully.commands and ctl.is_locked("salon")
    await ctl.shutdown()


async def test_watcher_releases_when_the_tv_goes_silent() -> None:
    fully = FakeFully()
    ctl = _controller(fully, watch_every=0.05)
    await ctl.on_playback("salon", "play")  # rien dans now_playing : TV muette
    await asyncio.sleep(0.15)
    assert fully.commands[-2:] == ["unlockKiosk", "toBackground"]
    assert not ctl.is_locked("salon")
    await ctl.shutdown()


async def test_watcher_keeps_lock_while_playing() -> None:
    fully = FakeFully()
    ctl = _controller(fully, watch_every=0.05)
    now_playing.record("salon", {"event": "play", "title": "Dune"}, time.time())
    await ctl.on_playback("salon", "play")
    await asyncio.sleep(0.15)
    assert "unlockKiosk" not in fully.commands
    await ctl.shutdown()


async def test_rooms_without_tablet_and_failures_never_raise() -> None:
    fully = FakeFully(down=True)
    ctl = _controller(fully, watch_every=60)
    await ctl.on_playback("cinema", "play")  # pas de tablette dans cette pièce
    await ctl.on_playback("salon", "play")  # tablette injoignable : journal, pas d'erreur
    assert not ctl.is_locked("salon")
    fully.down = False
    await ctl.on_playback("salon", "progress")  # pas d'acharnement (RETRY_AFTER)
    assert fully.commands == []
    await ctl.lock("salon")  # à la main (web app) : réessaie tout de suite
    assert ctl.is_locked("salon")
    await ctl.shutdown()


async def test_wrong_password_is_reported() -> None:
    fully = FakeFully(password="autre")
    async with fully.client() as client:
        ok, message, _ = await fully_kiosk.send(client, TABLET, "lockKiosk")
    assert not ok and message == "Please login"


@pytest.mark.parametrize(
    ("host", "valid"),
    [
        ("192.168.1.50", True),
        ("10.0.0.7", True),
        ("pixel-tablet.lan", True),
        ("fd00::12", True),
        ("8.8.8.8", False),  # Internet : refusé (le serveur ne relaie pas de mot de passe)
        ("192.168.1.50/x", False),
        ("user@192.168.1.50", False),
        ("", False),
    ],
)
def test_check_host(host: str, valid: bool) -> None:
    if valid:
        assert fully_kiosk.check_host(host)
    else:
        with pytest.raises(ValueError):
            fully_kiosk.check_host(host)


def test_base_url() -> None:
    assert fully_kiosk.base_url("192.168.1.50", 2323) == "http://192.168.1.50:2323/"
    assert fully_kiosk.base_url("fd00::12", 0) == "http://[fd00::12]:2323/"


# ── Web app : réglages et actions ─────────────────────────────


async def _pair_screen(client: AsyncClient, auth_headers: dict) -> dict:
    start = (
        await client.post(
            "/api/devices/pair/start", json={"platform": "Fully Kiosk", "kind": "screen"}
        )
    ).json()
    body = {"user_code": start["user_code"], "name": "Tablette", "room": "salon"}
    resp = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["device"]


async def test_kiosk_settings_password_never_leaves(
    client: AsyncClient, auth_headers: dict
) -> None:
    device = await _pair_screen(client, auth_headers)
    assert device["kiosk_control"] is False and device["kiosk_password_set"] is False
    resp = await client.patch(
        f"/api/devices/{device['id']}",
        json={"kiosk_control": True, "kiosk_host": "192.168.1.50", "kiosk_password": "secret"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["kiosk_control"] is True and data["kiosk_host"] == "192.168.1.50"
    assert data["kiosk_password_set"] is True and data["kiosk_port"] == 2323
    assert "secret" not in resp.text  # ni en clair, ni chiffré
    listing = await client.get("/api/devices", headers=auth_headers)
    assert "secret" not in listing.text
    # Adresse publique refusée ; mot de passe effacé avec ""
    bad = await client.patch(
        f"/api/devices/{device['id']}", json={"kiosk_host": "8.8.8.8"}, headers=auth_headers
    )
    assert bad.status_code == 422
    cleared = await client.patch(
        f"/api/devices/{device['id']}", json={"kiosk_password": ""}, headers=auth_headers
    )
    assert cleared.json()["kiosk_password_set"] is False


async def test_kiosk_settings_refused_for_a_tv(client: AsyncClient, auth_headers: dict) -> None:
    start = (await client.post("/api/devices/pair/start", json={"platform": "Kodi"})).json()
    body = {"user_code": start["user_code"], "name": "Kodi", "room": "salon"}
    tv = (await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)).json()
    resp = await client.patch(
        f"/api/devices/{tv['device']['id']}", json={"kiosk_control": True}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_kiosk_actions_and_scrobble_hook(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    fully = FakeFully()
    monkeypatch.setattr(fully_kiosk.httpx, "AsyncClient", lambda **_: fully.client())
    ctl = KioskController(fully_kiosk.targets_for_room, client_factory=fully.client)
    monkeypatch.setattr(fully_kiosk, "kiosk", ctl)
    monkeypatch.setattr("app.api.kodi.kiosk", ctl)
    device = await _pair_screen(client, auth_headers)
    url = f"/api/devices/{device['id']}"
    # Sans mot de passe : action impossible, message clair
    resp = await client.post(f"{url}/kiosk/test", headers=auth_headers)
    assert resp.status_code == 422
    await client.patch(
        url,
        json={"kiosk_control": True, "kiosk_host": "192.168.1.50", "kiosk_password": "secret"},
        headers=auth_headers,
    )
    test = (await client.post(f"{url}/kiosk/test", headers=auth_headers)).json()
    assert test["ok"] and test["device"]["deviceName"] == "Pixel Tablet"
    assert fully.hosts[-1] == "192.168.1.50:2323"
    # La TV de la pièce lance un film : la tablette passe en kiosk
    await client.post(
        "/api/kodi/scrobble",
        json={"event": "play", "title": "Dune", "room": "salon"},
        headers=auth_headers,
    )
    for _ in range(50):
        if "lockKiosk" in fully.commands:
            break
        await asyncio.sleep(0.02)
    assert "lockKiosk" in fully.commands and ctl.is_locked("salon")
    # Issue de secours depuis la web app
    release = (await client.post(f"{url}/kiosk/release", headers=auth_headers)).json()
    assert release["ok"] and fully.commands[-1] == "toBackground"
    assert (await client.post(f"{url}/kiosk/oops", headers=auth_headers)).status_code == 404
    await ctl.shutdown()


def test_kiosk_columns_are_added_to_old_databases() -> None:
    from sqlalchemy import create_engine, inspect, text

    from app.database import add_missing_columns

    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE devices (id INTEGER PRIMARY KEY, name VARCHAR(100))"))
        added = add_missing_columns(conn)
        columns = {col["name"] for col in inspect(conn).get_columns("devices")}
    assert {"devices.kiosk_control", "devices.kiosk_password"} <= set(added)
    assert {"kiosk_control", "kiosk_host", "kiosk_port", "kiosk_password"} <= columns

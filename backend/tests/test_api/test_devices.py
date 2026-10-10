"""Appairage des TV (ADR-003 § 4) : parcours complet, périmètre, réseau local."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.yamaha import _target_avr
from app.main import app
from app.services import devices as devices_service
from app.services.devices import pairings


@pytest.fixture(autouse=True)
def _clear_pairings():
    pairings.clear()
    yield
    pairings.clear()


async def _pair(client: AsyncClient, auth_headers: dict, **confirm) -> tuple[str, dict]:
    """Appairage complet : renvoie (jeton, appareil)."""
    start = (
        await client.post("/api/devices/pair/start", json={"platform": "Kodi 21 · Android"})
    ).json()
    body = {"user_code": start["user_code"], "name": "Kodi Salon", "room": "salon", **confirm}
    resp = await client.post("/api/devices/pair/confirm", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    assert poll["status"] == "ok"
    return poll["token"], poll["device"]


# ── Parcours complet ──────────────────────────────────────────


async def test_pairing_flow(client: AsyncClient, auth_headers: dict) -> None:
    start = await client.post("/api/devices/pair/start", json={"platform": "Kodi 21 · Android"})
    assert start.status_code == 200
    data = start.json()
    assert len(data["user_code"]) == devices_service.USER_CODE_LENGTH
    assert data["verification_url"].endswith(f"/settings/kodi?pair={data['user_code']}")
    assert data["interval"] == 3 and data["expires_in"] == 600

    # Pas encore validé dans la web app
    poll = await client.post("/api/devices/pair/poll", json={"device_code": data["device_code"]})
    assert poll.json()["status"] == "pending"

    # Validation (le code est accepté en minuscules, avec un tiret)
    code = data["user_code"].lower()
    confirm = await client.post(
        "/api/devices/pair/confirm",
        json={"user_code": f"{code[:3]}-{code[3:]}", "name": "Kodi Cinéma", "room": "cinema"},
        headers=auth_headers,
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["device"]["room"] == "cinema"

    # Kodi reçoit son jeton… une seule fois
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": data["device_code"]})
    ).json()
    assert poll["status"] == "ok" and len(poll["token"]) > 30
    again = await client.post("/api/devices/pair/poll", json={"device_code": data["device_code"]})
    assert again.status_code == 410

    # « Qui suis-je ? » avec le jeton
    me = await client.get("/api/devices/me", headers={"X-Device-Token": poll["token"]})
    assert me.status_code == 200
    assert (me.json()["name"], me.json()["room"], me.json()["paired"]) == (
        "Kodi Cinéma",
        "cinema",
        True,
    )
    assert me.json()["platform"] == "Kodi 21 · Android"

    # La web app le voit, avec sa dernière activité
    listed = (await client.get("/api/devices", headers=auth_headers)).json()
    assert [d["name"] for d in listed] == ["Kodi Cinéma"]
    assert listed[0]["last_seen_at"] is not None


async def test_token_is_stored_hashed(client: AsyncClient, auth_headers: dict) -> None:
    token, device = await _pair(client, auth_headers)
    from sqlalchemy import select

    from app.database import get_db
    from app.models.device import Device

    # Session de test (celle que conftest branche à la place de la vraie base).
    # Ne pas importer tests.conftest : pytest l'a déjà chargé sous un autre
    # nom, le réimporter créerait une 2e base vide pour les tests suivants.
    sessions = app.dependency_overrides[get_db]()
    session = await anext(sessions)
    row = (await session.execute(select(Device))).scalar_one()
    await sessions.aclose()
    assert row.token_hash == devices_service.hash_token(token)
    assert token not in row.token_hash


async def test_confirm_rejects_bad_code_and_room(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/devices/pair/confirm",
        json={"user_code": "ZZZZZZ", "name": "X", "room": "salon"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
    start = (await client.post("/api/devices/pair/start", json={})).json()
    resp = await client.post(
        "/api/devices/pair/confirm",
        json={"user_code": start["user_code"], "name": "X", "room": "cuisine"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_confirm_requires_web_app_login(client: AsyncClient) -> None:
    start = (await client.post("/api/devices/pair/start", json={})).json()
    resp = await client.post(
        "/api/devices/pair/confirm",
        json={"user_code": start["user_code"], "name": "X", "room": "salon"},
    )
    assert resp.status_code == 401


async def test_qr_code_png(client: AsyncClient) -> None:
    start = (await client.post("/api/devices/pair/start", json={})).json()
    resp = await client.get(start["qr_url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(b"\x89PNG")
    head = await client.head(start["qr_url"])  # Kodi interroge d'abord en HEAD
    assert head.status_code == 200 and head.headers["content-type"] == "image/png"
    assert start["qr_url"].endswith(".png")
    assert (await client.get("/api/devices/pair/qr/ZZZZZZ.png")).status_code == 404


# ── Périmètre « TV » ──────────────────────────────────────────


async def test_device_scope(client: AsyncClient, auth_headers: dict) -> None:
    token, device = await _pair(client, auth_headers)
    tv = {"X-Device-Token": token}

    # Autorisé : lecture de la file, état de l'ampli
    assert (await client.get("/api/downloads", headers=tv)).status_code == 200
    assert (await client.get("/api/yamaha/state", headers=tv)).status_code == 200

    # Refusé : suppression, nettoyage, configuration, gestion des appareils
    for method, path in (
        ("POST", "/api/kodi/downloads/radarr/1/remove"),
        ("POST", "/api/downloads/queue/radarr/1/remove"),
        ("POST", "/api/kodi/maintenance/clean-orphans"),
        ("POST", "/api/kodi/clean"),
        ("GET", "/api/services"),
        ("GET", "/api/devices"),
        ("DELETE", f"/api/devices/{device['id']}"),
    ):
        resp = await client.request(method, path, headers=tv)
        assert resp.status_code == 403, (method, path, resp.status_code)


async def test_revoked_device_is_refused(client: AsyncClient, auth_headers: dict) -> None:
    token, device = await _pair(client, auth_headers)
    resp = await client.delete(f"/api/devices/{device['id']}", headers=auth_headers)
    assert resp.status_code == 200
    me = await client.get("/api/devices/me", headers={"X-Device-Token": token})
    assert me.status_code == 401


async def test_update_device(client: AsyncClient, auth_headers: dict) -> None:
    _, device = await _pair(client, auth_headers)
    resp = await client.patch(
        f"/api/devices/{device['id']}",
        json={"name": "Shield Cinéma", "room": "cinema"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert (resp.json()["name"], resp.json()["room"]) == ("Shield Cinéma", "cinema")
    # Un ampli qui n'existe pas est refusé
    resp = await client.patch(
        f"/api/devices/{device['id']}", json={"avr_service_id": 999}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_web_app_session_is_not_paired(client: AsyncClient, auth_headers: dict) -> None:
    assert (await client.get("/api/devices/me", headers=auth_headers)).json() == {"paired": False}


# ── Réseau local uniquement ───────────────────────────────────


@pytest_asyncio.fixture
async def internet_client() -> AsyncGenerator[AsyncClient, None]:
    """Client qui se présente avec une adresse publique."""
    transport = ASGITransport(app=app, client=("203.0.113.7", 4242))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_pairing_refused_from_internet(internet_client: AsyncClient) -> None:
    resp = await internet_client.post("/api/devices/pair/start", json={})
    assert resp.status_code == 403


async def test_device_token_refused_from_internet(
    client: AsyncClient, internet_client: AsyncClient, auth_headers: dict
) -> None:
    token, _ = await _pair(client, auth_headers)
    resp = await internet_client.get("/api/devices/me", headers={"X-Device-Token": token})
    assert resp.status_code == 403
    # Même en local, un proxy qui relaie une adresse publique est refusé
    resp = await client.get(
        "/api/devices/me", headers={"X-Device-Token": token, "X-Forwarded-For": "203.0.113.7"}
    )
    assert resp.status_code == 403


@pytest.mark.parametrize(
    ("host", "forwarded", "expected"),
    [
        ("192.168.2.40", None, True),
        ("10.0.0.5", "192.168.1.2", True),
        ("172.18.0.3", None, True),  # passerelle Docker
        ("127.0.0.1", None, True),
        ("::ffff:192.168.2.40", None, True),
        ("fd00::12", None, True),
        ("203.0.113.7", None, False),
        ("192.168.2.40", "203.0.113.7", False),
        ("192.168.2.40", "192.168.1.2, 8.8.8.8", False),
        (None, None, False),
        ("pas-une-ip", None, False),
    ],
)
def test_is_lan_request(host, forwarded, expected) -> None:
    assert devices_service.is_lan_request(host, forwarded) is expected


# ── Outils ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/kodi/dashboard", True),
        ("GET", "/api/media/movie/12", True),
        ("POST", "/api/kodi/downloads/sonarr/7/pause", True),
        ("POST", "/api/yamaha/control", True),
        ("POST", "/api/kodi/downloads/sonarr/7/remove", False),
        ("DELETE", "/api/media/movie/12", False),
        ("POST", "/api/yamaha/profiles", False),
        ("GET", "/api/settings", False),
    ],
)
def test_device_may_call(method, path, allowed) -> None:
    assert devices_service.device_may_call(method, path) is allowed


def test_user_code_alphabet_is_tv_friendly() -> None:
    codes = {pairings.start("", "127.0.0.1").user_code for _ in range(15)}
    assert all(not set(c) & set("01OIL58B2SZ") for c in codes)
    assert devices_service.normalize_user_code(" k7p-4qx ") == "K7P4QX"


def test_pending_limit() -> None:
    for _ in range(devices_service.MAX_PENDING):
        pairings.start("", "127.0.0.1")
    with pytest.raises(OverflowError):
        pairings.start("", "127.0.0.1")


def test_target_avr() -> None:
    tv = {"role": "device", "avr_service_id": 4}
    assert _target_avr(tv, None) == 4
    assert _target_avr(tv, 9) == 4  # une TV ne pilote que l'ampli de sa pièce
    assert _target_avr({"role": "device", "avr_service_id": None}, 9) == 9
    assert _target_avr({"sub": "arrmada_user"}, 9) == 9
    assert _target_avr({"sub": "arrmada_user"}, None) is None


def test_web_base_url() -> None:
    from starlette.requests import Request

    from app.api.devices import web_base_url

    def request_for(host: str) -> Request:
        return Request(
            {
                "type": "http",
                "scheme": "http",
                "server": (host, 8420),
                "path": "/",
                "headers": [(b"host", f"{host}:8420".encode())],
                "query_string": b"",
            }
        )

    assert web_base_url(request_for("192.168.2.3")) == "http://192.168.2.3:3420"

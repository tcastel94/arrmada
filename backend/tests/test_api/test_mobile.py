"""Téléphone / tablette (ADR-007 phase 4) : VPN accepté, « Sur la TV »."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import devices
from app.services.devices import device_may_call, pairings
from app.utils.event_bus import event_bus


async def _pair(
    client: AsyncClient, admin: dict[str, str], name: str, platform: str = "ArrMada Android TV"
) -> tuple[int, dict[str, str]]:
    pairings.clear()
    start = (await client.post("/api/devices/pair/start", json={"platform": platform})).json()
    body = {"user_code": start["user_code"], "name": name, "room": "salon"}
    confirmed = await client.post("/api/devices/pair/confirm", json=body, headers=admin)
    assert confirmed.status_code == 200
    poll = (
        await client.post("/api/devices/pair/poll", json={"device_code": start["device_code"]})
    ).json()
    return confirmed.json()["device"]["id"], {"X-Device-Token": poll["token"]}


def test_vpn_networks_accepted_only_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not devices.is_lan_request("100.101.102.103", None)  # Tailscale, pas déclaré
    monkeypatch.setattr(settings, "DEVICE_TRUSTED_NETWORKS", "100.64.0.0/10, pas-un-réseau")
    assert devices.is_lan_request("100.101.102.103", None)
    assert not devices.is_lan_request("8.8.8.8", None)
    assert devices.is_lan_request("192.168.1.20", "100.101.102.103")


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    [
        ("GET", "/api/tv/targets", True),
        ("POST", "/api/tv/targets/3/play", True),
        ("POST", "/api/kodi/play-on-device", False),
    ],
)
def test_device_scope(method: str, path: str, allowed: bool) -> None:
    assert device_may_call(method, path) is allowed


async def test_phone_sends_a_title_to_a_tv(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    tv_id, _tv = await _pair(client, auth_headers, "Shield Salon")
    _phone_id, phone = await _pair(
        client, auth_headers, "Pixel de Thomas", "ArrMada Android (téléphone) · Google Pixel 8"
    )
    tablet_id, _tablet = await _pair(
        client, auth_headers, "Tablette", "ArrMada Android (tablette) · Samsung SM-X710"
    )

    targets = (await client.get("/api/tv/targets", headers=phone)).json()["items"]
    assert [t["name"] for t in targets] == ["Shield Salon"]  # ni soi-même, ni la tablette

    before = event_bus.last_id
    body = {"media_type": "movie", "id": 438631, "title": "Dune", "resume": True}
    sent = await client.post(f"/api/tv/targets/{tv_id}/play", json=body, headers=phone)
    assert sent.status_code == 200, sent.text
    assert sent.json()["message"] == "Envoyé sur Shield Salon"
    events = [e for e in event_bus.get_recent_events(before) if e.type == "play_request"]
    assert events and events[-1].data["device_id"] == tv_id and events[-1].data["id"] == "438631"

    for other in (_phone_id, tablet_id):
        assert (
            await client.post(f"/api/tv/targets/{other}/play", json=body, headers=phone)
        ).status_code == 404
    bad = await client.post(
        f"/api/tv/targets/{tv_id}/play", json={"media_type": "x"}, headers=phone
    )
    assert bad.status_code == 422

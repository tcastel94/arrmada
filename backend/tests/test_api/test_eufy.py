"""Caméras Eufy : abonnement à eufy-security-ws, photos, route de la TV."""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient

from app.services import eufy
from app.services.devices import device_may_call
from app.services.eufy import EufyBridge, SnapshotStore, parse_kinds, picture_bytes
from app.utils.event_bus import event_bus

JPEG = bytes([255, 216, 255, 224, 0, 16]) + b"photo" + bytes([255, 217])


def picture_event(serial: str = "T8210", data: bytes = JPEG) -> dict:
    """Propriété « picture » telle que eufy-security-ws l'écrit (Buffer Node.js)."""
    return {
        "source": "device",
        "event": "property changed",
        "serialNumber": serial,
        "name": "picture",
        "value": {
            "data": {"type": "Buffer", "data": list(data)},
            "type": {"ext": "jpg", "mime": "image/jpeg"},
        },
    }


def person(serial: str = "T8210", state: bool = True) -> dict:
    return {"source": "device", "event": "person detected", "serialNumber": serial, "state": state}


class FakeEufyServer:
    """Faux eufy-security-ws : salue, répond aux commandes, pousse des événements."""

    def __init__(self, devices: list) -> None:
        self.devices = devices
        self.out: asyncio.Queue = asyncio.Queue()
        self.received: list[dict] = []
        self.out.put_nowait(json.dumps({"type": "version", "maxSchemaVersion": 19}))

    # Interface d'une connexion websockets (contexte, recv, send, itération)
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def recv(self) -> str:
        return await self.out.get()

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        message = await self.out.get()
        if message is None:
            raise StopAsyncIteration
        return message

    async def send(self, text: str) -> None:
        message = json.loads(text)
        self.received.append(message)
        result: dict = {}
        if message["command"] == "start_listening":
            result = {"state": {"driver": {}, "stations": [], "devices": self.devices}}
        elif message["command"] == "device.get_properties":
            names = {"T8210": "Entrée", "T8113": "Jardin"}
            result = {"properties": {"name": names.get(message["serialNumber"], "?")}}
        reply = {"type": "result", "messageId": message["messageId"], "success": True}
        await self.out.put(json.dumps({**reply, "result": result}))

    async def event(self, event: dict) -> None:
        await self.out.put(json.dumps({"type": "event", "event": event}))

    async def close(self) -> None:
        await self.out.put(None)


async def _start(server: FakeEufyServer, **kwargs) -> tuple[EufyBridge, list, asyncio.Task]:
    published: list = []

    async def publish(event_type: str, data: dict) -> None:
        published.append((event_type, data))

    bridge = EufyBridge(
        "ws://eufy:3000", kwargs.pop("kinds", {"person"}), publish,
        connect=lambda url: server, **kwargs,
    )  # fmt: skip
    task = asyncio.create_task(bridge._session())
    for _ in range(100):
        if bridge.names:
            break
        await asyncio.sleep(0.01)
    return bridge, published, task


async def _wait_for(published: list, count: int = 1) -> None:
    for _ in range(200):
        if len(published) >= count:
            return
        await asyncio.sleep(0.01)


async def test_person_detected_with_its_picture() -> None:
    server = FakeEufyServer(["T8210", "T8113"])
    bridge, published, task = await _start(server)
    assert bridge.connected and bridge.names == {"T8210": "Entrée", "T8113": "Jardin"}
    commands = [m["command"] for m in server.received]
    assert commands[:2] == ["set_api_schema", "start_listening"]
    assert server.received[0]["schemaVersion"] == 19  # ce que le serveur sait faire
    await server.event(person())
    await asyncio.sleep(0.05)
    await server.event(picture_event())  # la photo arrive après la détection
    await _wait_for(published)
    event_type, data = published[0]
    assert event_type == "camera"
    assert data["camera"] == "Entrée" and data["label"] == "Personne détectée"
    assert data["detection"] == "person" and data["snapshot_id"]
    assert bridge.snapshots.get(data["snapshot_id"]) == (JPEG, "image/jpeg")
    await server.close()
    await task


async def test_filters_cooldown_and_missing_picture() -> None:
    server = FakeEufyServer([{"serialNumber": "T8210", "name": "Entrée"}])  # ancien schéma
    bridge, published, task = await _start(server, picture_wait=0.05)
    assert bridge.names == {"T8210": "Entrée"}
    motion = {"source": "device", "event": "motion detected", "serialNumber": "T8210"}
    await server.event(motion)  # non choisie (EUFY_DETECTIONS=person)
    await server.event(person(state=False))  # fin de détection : ignorée
    await server.event(person())
    await _wait_for(published)
    assert len(published) == 1 and published[0][1]["snapshot_id"] is None  # pas de photo à temps
    await server.event(person())  # moins d'une minute après : pas de rafale
    await asyncio.sleep(0.15)
    assert len(published) == 1
    await server.close()
    await task


async def test_picture_just_before_the_detection_counts() -> None:
    server = FakeEufyServer(["T8210"])
    bridge, published, task = await _start(server, picture_wait=5)
    await server.event(picture_event())
    await server.event(person())
    await _wait_for(published)
    assert published and published[0][1]["snapshot_id"]  # sans attendre 5 s
    await server.close()
    await task


def test_helpers() -> None:
    assert parse_kinds("person, RING, inconnu") == {"person", "ring"}
    assert parse_kinds("") == set()
    assert picture_bytes({"type": "Buffer", "data": [1, 2]}) == (b"\x01\x02", "image/jpeg")
    assert picture_bytes({"data": {"type": "Buffer", "data": []}}) is None
    assert picture_bytes("pas un dict") is None
    store = SnapshotStore(keep=2, ttl=10)
    first = store.add(b"a", "image/jpeg", now=0)
    store.add(b"b", "image/jpeg", now=0)
    store.add(b"c", "image/jpeg", now=0)
    assert store.get(first, now=1) is None  # sorti (2 gardées)
    late = store.add(b"d", "image/jpeg", now=0)
    assert store.get(late, now=11) is None  # expirée


# ── Routes ────────────────────────────────────────────────────


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> EufyBridge:
    async def publish(event_type: str, data: dict) -> None:
        await event_bus.publish(event_type=event_type, data=data)

    instance = EufyBridge("ws://eufy:3000", {"person"}, publish)
    instance.names = {"T8210": "Entrée"}
    monkeypatch.setattr(eufy, "bridge", instance)
    return instance


async def test_snapshot_route(client: AsyncClient, auth_headers: dict, bridge: EufyBridge) -> None:
    snapshot_id = bridge.snapshots.add(JPEG, "image/jpeg")
    resp = await client.get(f"/api/cameras/snapshot/{snapshot_id}", headers=auth_headers)
    assert resp.status_code == 200
    import base64

    assert base64.b64decode(resp.json()["image"]) == JPEG
    missing = await client.get("/api/cameras/snapshot/999", headers=auth_headers)
    assert missing.status_code == 404
    # Une TV appairée peut lire la photo, pas le reste
    assert device_may_call("GET", f"/api/cameras/snapshot/{snapshot_id}")
    assert not device_may_call("POST", "/api/cameras/test")
    assert not device_may_call("GET", "/api/cameras/snapshot/1", kind="screen")


async def test_status_and_test_event(
    client: AsyncClient, auth_headers: dict, bridge: EufyBridge
) -> None:
    status = (await client.get("/api/cameras/status", headers=auth_headers)).json()
    assert status["cameras"] == ["Entrée"] and status["detections"] == ["person"]
    resp = await client.post("/api/cameras/test", headers=auth_headers)
    assert resp.status_code == 200
    last = event_bus.get_recent_events(0)[-1]
    assert last.type == "camera" and last.data["label"] == "Personne détectée (test)"
    assert (await client.post("/api/cameras/test")).status_code == 401  # web app seulement

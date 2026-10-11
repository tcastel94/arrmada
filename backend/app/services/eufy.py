"""Caméras Eufy : une détection devient une pop-up sur la TV pendant un média.

Eufy n'a pas d'API locale officielle. On passe par **eufy-security-ws**
(conteneur Docker `bropat/eufy-security-ws`, sur l'Unraid) : il se connecte
au cloud Eufy avec un compte secondaire et publie les événements des
caméras sur une WebSocket du réseau local. ArrMada s'y abonne :

    eufy-security-ws ──(WebSocket, événements)──► ArrMada ──(/api/events)──► TV

  1. connexion, choix du schéma de l'API, `start_listening` ;
  2. noms des caméras (`device.get_properties`) ;
  3. « person detected » (ou autre détection choisie, EUFY_DETECTIONS) :
     on attend quelques secondes la photo de l'événement (propriété
     « picture » de la caméra), on la garde en mémoire, puis on publie un
     événement « camera » ; la TV le relève, télécharge la photo
     (`/api/cameras/snapshot/{id}`) et affiche la pop-up.

Garde-fous : une même caméra ne déclenche pas plus d'une alerte par minute ;
connexion perdue → nouvel essai avec une attente croissante (5 s → 5 min) ;
rien n'est écrit sur disque (photos en mémoire, les 20 dernières, 1 h).

Analogie : un `tail -f` sur le journal d'événements des caméras, filtré par
un `grep "person detected"`, qui pousse vers la TV.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.utils.logger import get_logger

# Journal du projet (comme les autres services) : un logger Python nu
# n'affiche rien sous WARNING, les messages d'information étaient perdus.
logger = get_logger(__name__)

MAX_SCHEMA = 21  # schéma de l'API eufy-security-ws visé (le serveur peut en offrir moins)
PICTURE_WAIT = 6.0  # s d'attente de la photo d'un événement
PICTURE_FRESH = 15.0  # s : une photo arrivée juste AVANT la détection compte aussi
COOLDOWN = 60.0  # s entre deux alertes d'une même caméra
SNAPSHOT_KEEP = 20
SNAPSHOT_TTL = 3600.0
RETRY_MIN, RETRY_MAX = 5.0, 300.0

# Événement eufy-security-ws → (clé courte, libellé affiché sur la TV)
DETECTIONS: dict[str, tuple[str, str]] = {
    "person detected": ("person", "Personne détectée"),
    "motion detected": ("motion", "Mouvement détecté"),
    "rings": ("ring", "On sonne à la porte"),
    "pet detected": ("pet", "Animal détecté"),
    "vehicle detected": ("vehicle", "Véhicule détecté"),
    "package delivered": ("package", "Colis livré"),
}


def parse_kinds(value: str) -> set[str]:
    """« person, ring » → {"person", "ring"} (clés inconnues ignorées)."""
    known = {key for key, _ in DETECTIONS.values()}
    return {part.strip().lower() for part in (value or "").split(",")} & known


def picture_bytes(value: Any) -> tuple[bytes, str] | None:
    """Photo d'une propriété « picture » : (octets, type MIME) ou None.

    eufy-security-ws la transmet en JSON sous la forme d'un Buffer Node.js :
    {"data": {"type": "Buffer", "data": [255, 216, …]}, "type": {"mime": …}}
    (ou directement {"type": "Buffer", "data": […]} selon les versions).
    """
    if not isinstance(value, dict):
        return None
    mime = "image/jpeg"
    data: Any = value
    if isinstance(value.get("data"), dict):
        data = value["data"]
        kind = value.get("type")
        if isinstance(kind, dict) and kind.get("mime"):
            mime = str(kind["mime"])
    raw = data.get("data") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        return None
    try:
        return bytes(raw), mime
    except (TypeError, ValueError):
        return None


class SnapshotStore:
    """Photos des dernières détections, en mémoire (les plus anciennes sortent)."""

    def __init__(self, keep: int = SNAPSHOT_KEEP, ttl: float = SNAPSHOT_TTL) -> None:
        self._items: OrderedDict[int, tuple[bytes, str, float]] = OrderedDict()
        self._ids = itertools.count(1)
        self.keep, self.ttl = keep, ttl

    def add(self, data: bytes, mime: str, now: float | None = None) -> int:
        snapshot_id = next(self._ids)
        self._items[snapshot_id] = (data, mime, now if now is not None else time.time())
        while len(self._items) > self.keep:
            self._items.popitem(last=False)
        return snapshot_id

    def get(self, snapshot_id: int, now: float | None = None) -> tuple[bytes, str] | None:
        item = self._items.get(snapshot_id)
        if item is None:
            return None
        data, mime, created = item
        if (now if now is not None else time.time()) - created > self.ttl:
            self._items.pop(snapshot_id, None)
            return None
        return data, mime

    def as_json(self, snapshot_id: int) -> dict[str, str] | None:
        found = self.get(snapshot_id)
        if found is None:
            return None
        data, mime = found
        return {"mime": mime, "image": base64.b64encode(data).decode()}


Publisher = Callable[[str, dict[str, Any]], Awaitable[None]]


class EufyBridge:
    """Abonnement à eufy-security-ws : détections → événements « camera »."""

    def __init__(
        self,
        url: str,
        kinds: set[str],
        publish: Publisher,
        snapshots: SnapshotStore | None = None,
        connect: Callable[..., Any] | None = None,
        picture_wait: float = PICTURE_WAIT,
        cooldown: float = COOLDOWN,
    ) -> None:
        self.url = url
        self.kinds = kinds
        self._publish = publish
        self.snapshots = snapshots or SnapshotStore()
        self._connect = connect
        self.picture_wait = picture_wait
        self.cooldown = cooldown
        self.connected = False
        self.names: dict[str, str] = {}  # numéro de série → nom de la caméra
        self.last_event: dict[str, Any] | None = None
        self._pictures: dict[str, tuple[bytes, str, float]] = {}  # dernière photo par caméra
        self._waiters: dict[str, asyncio.Event] = {}
        self._last_alert: dict[str, float] = {}
        self._requests: dict[str, asyncio.Future] = {}
        self._ids = itertools.count(1)
        self._ws: Any = None
        self._tasks: set[asyncio.Task] = set()

    # ── Connexion ───────────────────────────────────────────────────

    async def run(self) -> None:
        """Boucle de vie : connexion, écoute, reconnexion avec attente croissante."""
        delay = RETRY_MIN
        while True:
            try:
                await self._session()
                delay = RETRY_MIN  # session normale terminée : on se reconnecte vite
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.connected or delay == RETRY_MIN:
                    logger.warning("Eufy : connexion à %s impossible (%s)", self.url, exc)
            self.connected = False
            await asyncio.sleep(delay)
            delay = min(delay * 2, RETRY_MAX)

    def _open(self):
        if self._connect is not None:
            return self._connect(self.url)
        from websockets.asyncio.client import connect

        # Les photos d'événements dépassent la limite par défaut (1 Mo) une
        # fois écrites en JSON (un nombre par octet).
        return connect(self.url, max_size=32 * 1024 * 1024, open_timeout=10)

    async def _session(self) -> None:
        async with self._open() as ws:
            self._ws = ws
            hello = json.loads(await ws.recv())
            schema = min(MAX_SCHEMA, int(hello.get("maxSchemaVersion") or MAX_SCHEMA))
            reader = asyncio.create_task(self._read(ws))
            try:
                await self._command("set_api_schema", schemaVersion=schema)
                state = await self._command("start_listening")
                self.connected = True
                logger.info("Eufy : connecté à %s (schéma %s)", self.url, schema)
                await self._load_names(state)
                await reader
            finally:
                reader.cancel()
                self._ws = None
                for future in self._requests.values():
                    future.cancel()
                self._requests.clear()

    async def _command(self, command: str, **params: Any) -> dict[str, Any]:
        """Commande eufy-security-ws et sa réponse (même messageId)."""
        message_id = f"arrmada-{next(self._ids)}"
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._requests[message_id] = future
        await self._ws.send(json.dumps({"messageId": message_id, "command": command, **params}))
        try:
            return await asyncio.wait_for(future, timeout=15)
        finally:
            self._requests.pop(message_id, None)

    async def _read(self, ws: Any) -> None:
        async for raw in ws:
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if message.get("type") == "result":
                future = self._requests.get(str(message.get("messageId")))
                if future is not None and not future.done():
                    if message.get("success", True):
                        future.set_result(message.get("result") or {})
                    else:
                        future.set_exception(RuntimeError(str(message.get("errorCode"))))
            elif message.get("type") == "event":
                self.handle_event(message.get("event") or {})

    async def _load_names(self, result: dict[str, Any]) -> None:
        """Noms des caméras : dans l'état initial (anciens schémas) ou demandés un à un."""
        devices = ((result or {}).get("state") or {}).get("devices") or []
        for device in devices:
            if isinstance(device, dict):
                serial = str(device.get("serialNumber") or "")
                name = device.get("name") or (device.get("properties") or {}).get("name")
            else:
                serial, name = str(device), None
                try:
                    props = await self._command("device.get_properties", serialNumber=serial)
                    name = (props.get("properties") or {}).get("name")
                except Exception:  # caméra qui ne répond pas : on garde son numéro
                    name = None
            if serial:
                self.names[serial] = str(name or serial)
        logger.info("Eufy : %d caméra(s) : %s", len(self.names), ", ".join(self.names.values()))

    # ── Événements ──────────────────────────────────────────────────

    def handle_event(self, event: dict[str, Any], now: float | None = None) -> None:
        """Un événement de eufy-security-ws (appelé pour chaque message)."""
        now = now if now is not None else time.time()
        if event.get("source") != "device":
            return
        serial = str(event.get("serialNumber") or "")
        name = str(event.get("event") or "")
        if name == "property changed" and event.get("name") == "picture":
            found = picture_bytes(event.get("value"))
            if found:
                self._pictures[serial] = (found[0], found[1], now)
                waiter = self._waiters.get(serial)
                if waiter is not None:
                    waiter.set()
            return
        detection = DETECTIONS.get(name)
        if detection is None or detection[0] not in self.kinds or event.get("state") is False:
            return
        if now - self._last_alert.get(serial, 0.0) < self.cooldown:
            return  # même caméra, il y a moins d'une minute : pas de rafale
        self._last_alert[serial] = now
        task = asyncio.create_task(self._announce(serial, detection, now))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _announce(self, serial: str, detection: tuple[str, str], at: float) -> None:
        picture = self._pictures.get(serial)
        if picture is None or at - picture[2] > PICTURE_FRESH:
            waiter = self._waiters.setdefault(serial, asyncio.Event())
            try:
                await asyncio.wait_for(waiter.wait(), timeout=self.picture_wait)
            except TimeoutError:
                pass  # pas de photo à temps : la pop-up s'affiche sans
            finally:
                self._waiters.pop(serial, None)
            picture = self._pictures.get(serial)
            if picture is not None and picture[2] < at - PICTURE_FRESH:
                picture = None
        snapshot_id = self.snapshots.add(picture[0], picture[1]) if picture else None
        await self.publish(serial, detection, snapshot_id, at)

    async def publish(
        self, serial: str, detection: tuple[str, str], snapshot_id: int | None, at: float
    ) -> None:
        data = {
            "camera": self.names.get(serial, serial or "Caméra"),
            "serial": serial,
            "detection": detection[0],
            "label": detection[1],
            "snapshot_id": snapshot_id,
            "at": datetime.fromtimestamp(at, UTC).isoformat(),
        }
        self.last_event = data
        logger.info("Eufy : %s · %s", data["label"], data["camera"])
        await self._publish("camera", data)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()


# ── Instance de l'application ───────────────────────────────────

bridge: EufyBridge | None = None
_runner: asyncio.Task | None = None


async def _publish_on_bus(event_type: str, data: dict[str, Any]) -> None:
    from app.utils.event_bus import event_bus

    await event_bus.publish(event_type=event_type, data=data)


def start(url: str, detections: str) -> EufyBridge | None:
    """Démarre l'abonnement si EUFY_WS_URL est réglée (au démarrage du backend)."""
    global bridge, _runner
    if not url:
        return None
    kinds = parse_kinds(detections) or {"person"}
    bridge = EufyBridge(url, kinds, _publish_on_bus)
    _runner = asyncio.create_task(bridge.run())
    logger.info("Eufy : abonnement à %s (détections : %s)", url, ", ".join(sorted(kinds)))
    return bridge


async def stop() -> None:
    global _runner
    if _runner is not None:
        _runner.cancel()
        _runner = None
    if bridge is not None:
        await bridge.shutdown()

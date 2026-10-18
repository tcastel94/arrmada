"""Tablette du salon en mode kiosk pendant un média (Fully Kiosk Browser).

Quand la TV d'une pièce lance un film ou un épisode, la tablette de cette
pièce (écran d'appoint, page `/ecran`) passe au premier plan et se
verrouille en mode kiosk : l'heure de fin reste affichée, personne ne sort
de la page par erreur. À l'arrêt, elle est déverrouillée et renvoyée en
arrière-plan : la tablette redevient une tablette normale.

Comment : l'API « Remote Admin » de Fully Kiosk (licence PLUS), en HTTP
sur le réseau local :
    http://<tablette>:2323/?cmd=lockKiosk&password=…&type=json
Le mot de passe Remote Admin est gardé chiffré côté serveur (Fernet, comme
les clés API des services) et ne repart jamais vers la web app.

Le déclencheur est le suivi de lecture que la TV envoie déjà
(`POST /api/kodi/scrobble`). Deux garde-fous :
  - un « stop » n'est appliqué qu'après STOP_GRACE secondes : entre deux
    épisodes enchaînés, Kodi envoie stop puis play, la tablette ne doit pas
    faire de va-et-vient ;
  - une TV éteinte sans « stop » : un veilleur relâche la tablette quand la
    lecture n'est plus signalée (même règle que l'écran d'appoint).

Analogie : un `systemctl start/stop` lancé par un hook, avec une
temporisation pour ne pas « flapper ».
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.now_playing import now_playing
from app.utils.logger import get_logger

# Journal du projet (comme les autres services) : un logger Python nu
# n'affiche rien sous WARNING, les messages d'information étaient perdus.
logger = get_logger(__name__)

DEFAULT_PORT = 2323
TIMEOUT_SECONDS = 5.0
STOP_GRACE = 20.0  # s avant de relâcher la tablette après un « stop »
WATCH_EVERY = 60.0  # s entre deux vérifications « lecture toujours en cours ? »
RETRY_AFTER = 300.0  # s avant de réessayer une tablette injoignable (pas d'acharnement)

# Commandes Remote Admin de Fully, dans l'ordre.
LOCK_COMMANDS = ("screenOn", "toForeground", "loadStartURL", "lockKiosk")
RELEASE_COMMANDS = ("unlockKiosk", "toBackground")
PLAYING_EVENTS = ("play", "resume", "progress")


@dataclass(frozen=True)
class KioskTarget:
    """Une tablette à piloter (écran d'appoint avec le mode kiosk activé)."""

    device_id: int
    name: str
    host: str
    port: int
    password: str


def check_host(host: str) -> str:
    """Adresse de la tablette : IP du réseau local ou nom d'hôte local.

    Une IP publique est refusée : le serveur ne doit pas servir de relais
    vers Internet avec un mot de passe (garde-fou « SSRF »).
    """
    value = (host or "").strip().strip("[]")
    if not value or any(ch in value for ch in "/?#@ "):
        raise ValueError("Adresse de tablette invalide")
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        # Nom d'hôte (tablette.lan, pixel-tablet) : lettres, chiffres, points, tirets
        if not all(part and part.replace("-", "").isalnum() for part in value.split(".")):
            raise ValueError("Adresse de tablette invalide") from None
        return value
    from app.services.devices import _is_private

    if not _is_private(str(ip)):
        raise ValueError("La tablette doit être sur le réseau local (adresse privée)")
    return value


def base_url(host: str, port: int) -> str:
    host = check_host(host)
    if ":" in host:  # IPv6 littérale
        host = f"[{host}]"
    return f"http://{host}:{int(port or DEFAULT_PORT)}/"


async def send(
    client: httpx.AsyncClient, target: KioskTarget, command: str
) -> tuple[bool, str, dict]:
    """Une commande Remote Admin ; (réussi, message, réponse JSON)."""
    try:
        response = await client.get(
            base_url(target.host, target.port),
            params={"cmd": command, "password": target.password, "type": "json"},
            timeout=TIMEOUT_SECONDS,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return False, f"tablette injoignable ({type(exc).__name__})", {}
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}", payload
    # Fully : {"status": "OK", "statustext": "…"} ou {"status": "Error", …}
    status = str(payload.get("status") or "").upper()
    text = str(payload.get("statustext") or "")
    if status == "ERROR" or "login" in text.lower():
        return False, text or "refusé par Fully (mot de passe ?)", payload
    return True, text or "OK", payload


ClientFactory = Callable[[], httpx.AsyncClient]
TargetLoader = Callable[[str], Awaitable[list[KioskTarget]]]


class KioskController:
    """Verrouille / relâche les tablettes d'une pièce selon la lecture de sa TV."""

    def __init__(
        self,
        load_targets: TargetLoader,
        client_factory: ClientFactory = httpx.AsyncClient,
        stop_grace: float = STOP_GRACE,
        watch_every: float = WATCH_EVERY,
    ) -> None:
        self._load_targets = load_targets
        self._client_factory = client_factory
        self.stop_grace = stop_grace
        self.watch_every = watch_every
        self._locked: set[str] = set()  # pièces dont la tablette est verrouillée
        self._failed_at: dict[str, float] = {}  # dernier échec de verrouillage, par pièce
        self._release_tasks: dict[str, asyncio.Task] = {}
        self._watch_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def is_locked(self, room: str) -> bool:
        return room in self._locked

    async def on_playback(self, room: str, event: str) -> None:
        """Une nouvelle de la TV de cette pièce (appelée sans attendre par le scrobble)."""
        try:
            if event == "stop":
                self._schedule_release(room)
            elif event in PLAYING_EVENTS:
                self._cancel(self._release_tasks, room)
                failed = self._failed_at.get(room)
                retry = failed is None or time.monotonic() - failed >= RETRY_AFTER
                if room not in self._locked and retry:
                    await self.lock(room)
        except Exception:  # la tablette ne doit jamais gêner la TV
            logger.exception("Mode kiosk : échec pour la pièce %s", room)

    async def _run(self, room: str, commands: Iterable[str]) -> list[dict[str, Any]]:
        targets = await self._load_targets(room)
        results = []
        if not targets:
            return results
        async with self._client_factory() as client:
            for target in targets:
                for command in commands:
                    ok, message, _ = await send(client, target, command)
                    results.append(
                        {"device": target.name, "command": command, "ok": ok, "message": message}
                    )
                    if not ok:
                        logger.warning("Mode kiosk : %s → %s : %s", target.name, command, message)
                        break  # tablette injoignable ou refus : inutile d'insister
        return results

    async def lock(self, room: str) -> list[dict[str, Any]]:
        async with self._lock:
            results = await self._run(room, LOCK_COMMANDS)
            if any(r["ok"] and r["command"] == "lockKiosk" for r in results):
                self._locked.add(room)
                self._failed_at.pop(room, None)
                logger.info("Mode kiosk : tablette(s) de la pièce %s verrouillée(s)", room)
                self._start_watch(room)
            elif results:
                self._failed_at[room] = time.monotonic()  # réessai dans RETRY_AFTER s
            return results

    async def release(self, room: str) -> list[dict[str, Any]]:
        async with self._lock:
            self._cancel(self._watch_tasks, room)
            self._locked.discard(room)
            results = await self._run(room, RELEASE_COMMANDS)
            if results:
                logger.info("Mode kiosk : tablette(s) de la pièce %s relâchée(s)", room)
            return results

    # ── Temporisation et veilleur ───────────────────────────────────

    @staticmethod
    def _cancel(tasks: dict[str, asyncio.Task], room: str) -> None:
        task = tasks.pop(room, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    def _schedule_release(self, room: str) -> None:
        if room not in self._locked:
            return
        self._cancel(self._release_tasks, room)

        async def _later() -> None:
            await asyncio.sleep(self.stop_grace)
            self._release_tasks.pop(room, None)
            await self.release(room)

        self._release_tasks[room] = asyncio.create_task(_later())

    def _start_watch(self, room: str) -> None:
        self._cancel(self._watch_tasks, room)

        async def _watch() -> None:
            while room in self._locked:
                await asyncio.sleep(self.watch_every)
                if room in self._locked and now_playing.current(room, time.time()) is None:
                    logger.info("Mode kiosk : plus de lecture signalée dans %s", room)
                    self._watch_tasks.pop(room, None)
                    await self.release(room)
                    return

        self._watch_tasks[room] = asyncio.create_task(_watch())

    async def shutdown(self) -> None:
        for tasks in (self._release_tasks, self._watch_tasks):
            for task in tasks.values():
                task.cancel()
            tasks.clear()


# ── Lecture des tablettes en base ───────────────────────────────────

# Fabrique de sessions de base (None : celle de l'application ; les tests
# y mettent leur base en mémoire).
session_factory: Any = None


async def targets_for_room(room: str) -> list[KioskTarget]:
    """Écrans d'appoint de la pièce avec le mode kiosk activé et un mot de passe."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.device import Device

    async with (session_factory or async_session_factory)() as session:
        rows = (
            (
                await session.execute(
                    select(Device).where(
                        Device.kind == "screen",
                        Device.room == room,
                        Device.kiosk_control.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
    return [target for target in (target_of(device) for device in rows) if target]


def target_of(device: Any) -> KioskTarget | None:
    """Tablette pilotable : adresse (réglée, sinon la dernière vue) + mot de passe."""
    from app.services.encryption import decrypt_api_key

    host = (device.kiosk_host or device.last_ip or "").strip()
    if not host or not device.kiosk_password:
        return None
    try:
        password = decrypt_api_key(device.kiosk_password)
    except Exception:  # clé de chiffrement changée : à ressaisir
        logger.warning("Mode kiosk : mot de passe illisible pour %s", device.name)
        return None
    return KioskTarget(device.id, device.name, host, device.kiosk_port or DEFAULT_PORT, password)


kiosk = KioskController(targets_for_room)

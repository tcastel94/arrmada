"""Télécommande tactile : la tablette sous la TV pilote la lecture en cours.

La tablette (écran d'appoint) dépose une commande pour SA pièce ; la TV de
la pièce, pendant une lecture, attend les commandes par « long polling » :
elle pose une question (`GET /api/tv/remote?after=N`) à laquelle le serveur
ne répond qu'à l'arrivée d'une commande, ou au bout de 15 s (comme un
`tail -f` sur une file d'attente). Réaction quasi immédiate, sans connexion
permanente ni relevé toutes les secondes.

File en mémoire, par pièce : perdue au redémarrage du serveur, sans gravité
(une commande n'a de sens que dans les secondes qui suivent). Une commande
de plus de 15 s n'est jamais rejouée (TV qui se reconnecte après une coupure).

Commandes (action, valeur) :
  - toggle / play / pause ;
  - seek : décalage en secondes (−600 à +600) ;
  - skip : passer l'intro / le récap / le générique en cours ;
  - next : épisode suivant ;
  - track : {"type": "text" | "audio", "index": n} (−1 : sous-titres coupés) ;
  - subtitle_download : sous-titres FR par Bazarr ;
  - subtitle_sync : resynchro des sous-titres sur le son (Bazarr, ffsubsync) ;
  - subtitle_shift : décalage manuel en ms (−5 000 à +5 000 par appui).
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import time
from collections import deque
from typing import Any

ACTIONS = {
    "toggle", "play", "pause", "seek", "skip", "next", "track",
    "subtitle_download", "subtitle_sync", "subtitle_shift",
}  # fmt: skip
MAX_AGE = 15.0  # secondes : au-delà, une commande n'est plus rejouée
WAIT = 15.0  # attente maximale d'une question de la TV
KEEP = 20  # commandes gardées par pièce


class InvalidCommand(ValueError):
    """Action inconnue ou valeur hors bornes."""


def clean_command(action: Any, value: Any) -> dict[str, Any]:
    """Commande vérifiée : action connue, valeur bornée (rien d'autre ne passe)."""
    action = str(action or "")
    if action not in ACTIONS:
        raise InvalidCommand(f"Action inconnue : {action}")
    if action == "seek":
        try:
            seconds = int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidCommand("Décalage invalide") from exc
        if not -600 <= seconds <= 600 or seconds == 0:
            raise InvalidCommand("Décalage hors bornes")
        return {"action": action, "value": seconds}
    if action == "subtitle_shift":
        try:
            ms = int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidCommand("Décalage invalide") from exc
        if not -5000 <= ms <= 5000 or ms == 0:
            raise InvalidCommand("Décalage hors bornes")
        return {"action": action, "value": ms}
    if action == "track":
        if not isinstance(value, dict) or value.get("type") not in ("text", "audio"):
            raise InvalidCommand("Piste invalide")
        index = value.get("index")
        if not isinstance(index, int) or not -1 <= index <= 99:
            raise InvalidCommand("Piste invalide")
        if index == -1 and value["type"] == "audio":
            raise InvalidCommand("Le son ne se coupe pas d'ici")
        return {"action": action, "value": {"type": value["type"], "index": index}}
    return {"action": action, "value": None}


class RemoteQueue:
    def __init__(self) -> None:
        self._rooms: dict[str, deque[dict[str, Any]]] = {}
        self._ids = itertools.count(1)
        self._last_id = 0
        self._changed: asyncio.Condition | None = None

    def _condition(self) -> asyncio.Condition:
        # Créée au premier usage, dans la boucle d'événements du serveur
        if self._changed is None:
            self._changed = asyncio.Condition()
        return self._changed

    def clear(self) -> None:
        self._rooms.clear()
        self._changed = None

    @property
    def last_id(self) -> int:
        return self._last_id

    async def push(self, room: str, command: dict[str, Any]) -> dict[str, Any]:
        """Dépose une commande (déjà vérifiée) et réveille la TV de la pièce."""
        entry = {**command, "id": next(self._ids), "at": time.time()}
        self._last_id = entry["id"]
        self._rooms.setdefault(room, deque(maxlen=KEEP)).append(entry)
        condition = self._condition()
        async with condition:
            condition.notify_all()
        return entry

    def pending(self, room: str, after: int, now: float) -> list[dict[str, Any]]:
        return [
            {"id": c["id"], "action": c["action"], "value": c["value"]}
            for c in self._rooms.get(room, ())
            if c["id"] > after and now - c["at"] <= MAX_AGE
        ]

    async def wait(self, room: str, after: int, timeout: float = WAIT) -> dict[str, Any]:
        """Commandes de la pièce après `after`, en attendant jusqu'à `timeout` s.

        `after` < 0 (première question de la TV) : aucune commande, juste le
        curseur — on ne rejoue pas ce qui a été demandé avant le lancement.
        """
        if after < 0:
            return {"last_id": self._last_id, "commands": []}
        condition = self._condition()
        deadline = time.monotonic() + timeout
        async with condition:
            while True:
                found = self.pending(room, after, time.time())
                left = deadline - time.monotonic()
                if found or left <= 0:
                    break
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(condition.wait(), left)
        last = max([after, *[c["id"] for c in found]])
        return {"last_id": max(last, after), "commands": found}


remote_queue = RemoteQueue()

"""Lecture en cours par pièce, pour l'écran d'appoint (tablette sous la TV).

Source : le suivi de lecture que l'add-on Kodi envoie déjà (`POST
/api/kodi/scrobble`) : « play », « pause », « resume », « stop », et la
position toutes les 30 s. Aucun réglage à faire dans Kodi (pas besoin
d'activer son serveur web).

Rangé en mémoire, par pièce (salon, cinema) : comme un fichier d'état dans
/run, perdu au redémarrage du serveur et recréé à la prochaine nouvelle de
la TV (30 s au plus pendant une lecture).

L'écran calcule lui-même la position seconde par seconde entre deux
nouvelles : position + (maintenant − `updated_at`) pendant la lecture.
"""

from __future__ import annotations

import threading
from typing import Any

# Sans nouvelle d'une lecture « en cours » depuis ce délai (3 relevés de 30 s
# manqués), on la considère arrêtée : Kodi éteint, TV débranchée…
STALE_AFTER = 100
# En pause, la TV ne donne plus de nouvelles : on garde l'état plus longtemps.
PAUSED_STALE_AFTER = 3 * 3600


def _number(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _same_item(state: dict[str, Any], data: dict[str, Any]) -> bool:
    """Même titre (et même épisode quand la TV le précise).

    Les add-ons d'avant la 1.10 n'envoient la saison / l'épisode qu'au début
    de la lecture : une valeur absente ne veut pas dire « autre épisode ».
    """
    if state.get("title") != data.get("title"):
        return False
    return all(
        data.get(key) in (None, "") or state.get(key) == data.get(key)
        for key in ("season", "episode")
    )


class NowPlaying:
    """État de lecture par pièce (sûr entre plusieurs requêtes simultanées)."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._rooms.clear()

    def record(self, room: str, data: dict[str, Any], now: float) -> None:
        """Une nouvelle de la TV de cette pièce."""
        event = str(data.get("event") or "progress")
        with self._lock:
            if event == "stop":
                self._rooms.pop(room, None)
                return
            previous = self._rooms.get(room)
            title = str(data.get("title") or "").strip()
            if not title and previous:
                title = previous["title"]  # « pause » / « resume » sans titre
            if not title:
                return
            fresh = dict(data, title=title)
            same = previous is not None and _same_item(previous, fresh)
            state: dict[str, Any] = dict(previous) if same and previous else {}
            if not same:
                # Nouveau titre : début de la séance maintenant
                state = {"started_at": now, "title": title}
            for key in (
                "media_type",
                "season",
                "episode",
                "episode_title",
                "year",
                "tmdb_id",
                "poster",
                "fanart",
                "device_name",
            ):
                if data.get(key) not in (None, ""):
                    state[key] = data[key]
            if data.get("total"):
                state["duration"] = _number(data["total"])
            before = state.get("position")
            if data.get("position") is not None:
                state["position"] = _number(data["position"])
            # Piège Kodi : une vidéo en pause est toujours « en lecture », le
            # relevé des 30 s continue. En pause : indicateur `paused` (add-on
            # 1.9+), ou position qui n'avance pas depuis une pause (anciennes).
            paused = event == "pause" or bool(data.get("paused"))
            if (
                not paused
                and event == "progress"
                and same
                and previous is not None
                and previous.get("state") == "paused"
                and before is not None
                and abs(state.get("position", 0.0) - float(before)) < 2
            ):
                paused = True
            state["state"] = "paused" if paused else "playing"
            state["updated_at"] = now
            self._rooms[room] = state

    def current(self, room: str, now: float) -> dict[str, Any] | None:
        """Lecture en cours dans la pièce, ou None (rien, ou nouvelles trop anciennes)."""
        with self._lock:
            state = self._rooms.get(room)
            if state is None:
                return None
            limit = PAUSED_STALE_AFTER if state.get("state") == "paused" else STALE_AFTER
            if now - float(state.get("updated_at") or 0) > limit:
                self._rooms.pop(room, None)
                return None
            return dict(state)


now_playing = NowPlaying()

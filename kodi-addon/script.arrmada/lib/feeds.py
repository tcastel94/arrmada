# -*- coding: utf-8 -*-
"""Flux de données mis en cache sur la TV (ADR-003 § 1) — logique pure, sans Kodi.

Principe : le **service** de l'add-on (toujours actif) télécharge chaque flux
à son rythme et l'enregistre dans un fichier JSON ; les **listes** et les
**widgets** lisent ce fichier et s'affichent instantanément, même serveur
coupé. C'est le même principe qu'un cache de paquets `apt` : on consulte la
copie locale, une tâche de fond la tient à jour.

Le temps réel (SSE, `/api/events/stream`) sert à rafraîchir tout de suite
les flux concernés par un événement (un import → « Ajouts récents »…).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterator, List, NamedTuple, Optional, Set, Tuple


class Feed(NamedTuple):
    name: str
    path: str  # route du serveur ArrMada
    ttl: int  # secondes avant de redemander au serveur
    label: str  # titre affiché (liste, widget)


FEEDS: Dict[str, Feed] = {
    feed.name: feed
    for feed in (
        Feed("recent", "/api/kodi/widgets/recent", 600, "Ajouts récents"),
        Feed("upcoming", "/api/calendar?days=7", 1800, "À venir (7 jours)"),
        Feed("downloads", "/api/downloads", 30, "Téléchargements en cours"),
        Feed("foryou", "/api/recommendations", 6 * 3600, "Pour toi"),
        Feed(
            "missing",
            "/api/media?availability=missing&monitored=true&sort=added&order=desc&per_page=100",
            1800,
            "Manquants surveillés",
        ),
        Feed("notifications", "/api/notifications?limit=50", 120, "Notifications"),
    )
}

# Un flux plus vieux que ça n'est plus affiché tel quel : la liste le
# redemande au serveur (cas d'une TV restée éteinte plusieurs jours).
MAX_AGE = 3 * 24 * 3600

RETRY_AFTER_ERROR = 120  # serveur injoignable : on réessaie dans 2 min


def cache_file(cache_dir: str, name: str) -> str:
    return os.path.join(cache_dir, f"feed-{name}.json")


def load(cache_dir: str, name: str) -> Optional[Dict[str, Any]]:
    """{"fetched_at": horodatage, "data": réponse du serveur} ou None."""
    try:
        with open(cache_file(cache_dir, name), encoding="utf-8") as handle:
            entry = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(entry, dict) or "data" not in entry:
        return None
    return entry


def save(cache_dir: str, name: str, data: Any, now: float) -> bool:
    """Enregistre le flux (écriture atomique). Vrai si son contenu a changé."""
    previous = load(cache_dir, name)
    changed = previous is None or _canonical(previous.get("data")) != _canonical(data)
    os.makedirs(cache_dir, exist_ok=True)
    path = cache_file(cache_dir, name)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump({"fetched_at": now, "data": data}, handle, ensure_ascii=False)
    os.replace(tmp, path)  # jamais de fichier à moitié écrit lu par une liste
    return changed


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)


def is_stale(entry: Optional[Dict[str, Any]], ttl: int, now: float) -> bool:
    """Vrai s'il faut redemander le flux au serveur."""
    if not entry:
        return True
    return now - float(entry.get("fetched_at") or 0) >= ttl


def is_usable(entry: Optional[Dict[str, Any]], now: float) -> bool:
    """Vrai si une liste peut afficher ce cache sans attendre le serveur."""
    return bool(entry) and now - float(entry.get("fetched_at") or 0) < MAX_AGE


def is_error(response: Any) -> bool:
    """Réponse d'erreur de l'API (on garde alors l'ancien cache)."""
    return isinstance(response, dict) and response.get("status") == "error"


# ─────────────────────────────────────────────────────────────────────────────
# Temps réel : événements du serveur → flux à rafraîchir, notification à l'écran
# ─────────────────────────────────────────────────────────────────────────────

_EVENT_FEEDS: Dict[str, Set[str]] = {
    "new_import": {"recent", "missing", "upcoming", "downloads", "notifications"},
    "download_grab": {"downloads", "missing", "notifications"},
    "download_update": {"downloads"},
    "media_deleted": {"recent", "missing"},
    "media_renamed": {"recent"},
    "health_alert": {"notifications"},
    "health_restored": {"notifications"},
}


def feeds_for_event(event_type: str, data: Dict[str, Any]) -> Set[str]:
    """Flux à rafraîchir immédiatement après un événement du serveur."""
    names = set(_EVENT_FEEDS.get(event_type, set()))
    if event_type == "cache_invalidated" and "media" in (data.get("patterns") or []):
        names |= {"recent", "missing"}
    return names


def osd_message(event_type: str, data: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """(titre, message) de la notification à l'écran, ou None."""
    title = str(data.get("title") or "").strip()
    quality = str(data.get("quality") or "").strip()
    if event_type == "new_import" and title:
        return "Importé sur le NAS", f"{title} · {quality}" if quality else title
    if event_type == "download_grab" and title:
        return "Téléchargement lancé", title
    if event_type == "health_alert":
        return "Alerte ArrMada", title or str(data.get("message") or "Un service a un problème")
    return None


class SSEParser:
    """Découpe un flux SSE (texte, ligne par ligne) en événements.

    Format : des lignes « event: … », « data: … », « id: … », un événement
    se termine par une ligne vide. Les lignes « : » sont des commentaires.
    """

    def __init__(self) -> None:
        self._event = "message"
        self._data: List[str] = []
        self._id = ""

    def feed(self, line: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
        """Ajoute une ligne ; renvoie (type, données, id) à la fin d'un événement."""
        line = line.rstrip("\r\n")
        if not line:
            if not self._data:
                self._event = "message"
                return None
            raw = "\n".join(self._data)
            event, event_id = self._event, self._id
            self._event, self._data = "message", []
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"raw": raw}
            return event, data if isinstance(data, dict) else {"value": data}, event_id
        if line.startswith(":"):
            return None
        field, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field == "event":
            self._event = value
        elif field == "data":
            self._data.append(value)
        elif field == "id":
            self._id = value
        return None


def parse_stream(lines: Iterator[str]) -> Iterator[Tuple[str, Dict[str, Any], str]]:
    """Événements d'une suite de lignes (pratique pour les tests)."""
    parser = SSEParser()
    for line in lines:
        event = parser.feed(line)
        if event:
            yield event

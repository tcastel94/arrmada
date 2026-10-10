# -*- coding: utf-8 -*-
"""Flux de données mis en cache sur la TV (ADR-003 § 1) — logique pure, sans Kodi.

Principe : le **service** de l'add-on (toujours actif) télécharge chaque flux
à son rythme et l'enregistre dans un fichier JSON ; les **listes** et les
**widgets** lisent ce fichier et s'affichent instantanément, même serveur
coupé. C'est le même principe qu'un cache de paquets `apt` : on consulte la
copie locale, une tâche de fond la tient à jour.

Le « temps réel » : toutes les 5 s, le service relève les derniers
événements du serveur (`/api/events/recent`) et rafraîchit tout de suite les
flux concernés (un import → « Ajouts récents »…). Un simple relevé, pas de
connexion permanente : depuis la 1.7.1, le service n'a plus aucun fil de fond
(voir lib/background.py).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple


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


def next_feed(
    forced: Set[str],
    fetched_at: Dict[str, float],
    retry_at: Dict[str, float],
    now: float,
) -> Optional[str]:
    """Le flux à rafraîchir maintenant, ou None s'il n'y a rien à faire.

    Le service en rafraîchit **un seul par tour de boucle** (1 s) : chaque
    tour reste court, Kodi garde la main. Priorité aux flux réclamés par un
    événement (`forced`), puis aux flux périmés qui ne sont pas en attente
    après une erreur (`retry_at`).
    """
    for name in FEEDS:
        if name in forced:
            return name
    for name, feed in FEEDS.items():
        if now - fetched_at.get(name, 0.0) >= feed.ttl and now >= retry_at.get(name, 0.0):
            return name
    return None


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


# Relevé des événements : toutes les EVENTS_EVERY secondes. Après une coupure
# plus longue, au plus MAX_OSD_PER_POLL notifications (les plus récentes) :
# pas de rafale de bulles à l'écran.
EVENTS_EVERY = 5
MAX_OSD_PER_POLL = 3


def _event_id(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_events(response: Any) -> List[Tuple[int, str, Dict[str, Any]]]:
    """Réponse de /api/events/recent → [(numéro, type, données)], triée."""
    if not isinstance(response, dict):
        return []
    events = []
    for event in response.get("events") or []:
        if not isinstance(event, dict):
            continue
        event_id = _event_id(event.get("id"))
        if event_id is None:
            continue
        data = event.get("data")
        events.append(
            (event_id, str(event.get("type") or ""), data if isinstance(data, dict) else {})
        )
    return sorted(events, key=lambda event: event[0])


class EventCursor:
    """Où en est la TV dans la liste des événements du serveur.

    Comme la position de lecture d'un `tail -f` : on retient le numéro du
    dernier événement traité et on ne demande que les suivants
    (`?since_id=<numéro>`).

    - Au tout premier relevé, on note seulement la position du serveur : pas
      de notification pour des imports d'avant l'allumage de la TV.
    - Le serveur numérote ses événements depuis son démarrage. S'il a
      redémarré (`boot_id` différent), sa numérotation est repartie de 1 :
      `accept()` renvoie None, il faut relire depuis 0.
    """

    def __init__(self) -> None:
        self.last_id = 0
        self.boot = ""  # identifiant du démarrage du serveur ("" = inconnu)
        self.started = False  # premier relevé fait ?

    def accept(self, response: Any) -> Optional[List[Tuple[int, str, Dict[str, Any]]]]:
        """Événements nouveaux à traiter ; None = serveur redémarré, relire depuis 0."""
        events = parse_events(response)
        meta = response if isinstance(response, dict) else {}
        boot = str(meta.get("boot_id") or "")
        if not self.started:
            self.started = True
            self.boot = boot
            server_last = _event_id(meta.get("last_id")) or 0
            self.last_id = max([event[0] for event in events] + [server_last, self.last_id])
            return []
        if boot and self.boot and boot != self.boot:
            self.boot = boot
            self.last_id = 0
            return None
        self.boot = boot or self.boot
        fresh = [event for event in events if event[0] > self.last_id]
        if fresh:
            self.last_id = fresh[-1][0]
        return fresh

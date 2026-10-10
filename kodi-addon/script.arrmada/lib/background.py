# -*- coding: utf-8 -*-
"""Tâches de fond du service (ADR-003 § 1) : cache des flux + temps réel.

Deux fils, lancés par service.py au démarrage de Kodi :

  FeedRefresher   télécharge chaque flux à son rythme (lib/feeds.py) et
                  l'écrit dans le cache local. Quand un flux change, il
                  publie `arrmada.reload` dans la mémoire commune de Kodi
                  (Window(10000)) : un widget de skin qui ajoute
                  `&reload=$INFO[Window(Home).Property(arrmada.reload)]` à
                  son chemin se recharge alors tout seul.

  EventListener   reste connecté au flux temps réel du serveur
                  (`/api/events/stream`, SSE). Un événement (import,
                  téléchargement lancé…) déclenche une notification à
                  l'écran et le rafraîchissement immédiat des flux concernés.
                  Connexion coupée : nouvel essai avec une attente croissante
                  (5 s, 10 s, 20 s… 2 min), et rattrapage des événements
                  manqués via `/api/events/recent`.

Comme un démon systemd : ils tournent tant que Kodi tourne, et s'arrêtent
proprement quand Kodi demande l'arrêt (Monitor.abortRequested).
"""

from __future__ import annotations

import socket
import threading
import time

import xbmc
import xbmcgui

import feeds
import ui_common as ui
from api import ArrMadaAPI
from kodi_helper import get_setting_bool

HOME = 10000  # fenêtre « Accueil » de Kodi : ses propriétés sont visibles partout
STREAM_PATH = "/api/events/stream"
READ_TIMEOUT = 60  # sans événement pendant 60 s, la connexion est rouverte
MAX_BACKOFF = 120
LIBRARY_SCAN_EVERY = 60  # au plus un scan de médiathèque par minute
SHORT_CONNECTION = 5  # connexion fermée en moins de 5 s : traitée comme une erreur


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Service : {message}", level)


class FeedRefresher(threading.Thread):
    """Tient le cache des flux à jour (un « cron » interne au service)."""

    def __init__(self, monitor: xbmc.Monitor) -> None:
        super().__init__(name="arrmada-feeds", daemon=True)
        self._monitor = monitor
        self._wake = threading.Event()
        self._forced: set = set()
        self._lock = threading.Lock()
        self._next_try: dict = {}  # nom → horodatage du prochain essai après une erreur
        self._stopping = threading.Event()

    def stop(self) -> None:
        self._stopping.set()
        self._wake.set()

    def _should_stop(self) -> bool:
        return self._stopping.is_set() or self._monitor.abortRequested()

    def force(self, names) -> None:
        """Rafraîchir ces flux dès que possible (appelé par EventListener)."""
        with self._lock:
            self._forced |= set(names)
        self._wake.set()

    def run(self) -> None:
        while not self._should_stop():
            self._cycle()
            self._wake.wait(5)
            self._wake.clear()

    def _cycle(self) -> None:
        cache = ui.cache_dir()
        with self._lock:
            forced, self._forced = self._forced, set()
        changed = []
        for name, feed in feeds.FEEDS.items():
            if self._should_stop():
                return
            now = time.time()
            due = feeds.is_stale(feeds.load(cache, name), feed.ttl, now)
            if name not in forced and (not due or now < self._next_try.get(name, 0)):
                continue
            started = time.perf_counter()
            data = ArrMadaAPI.get_feed(feed.path, timeout=10)
            if feeds.is_error(data):
                if name not in self._next_try:  # journal à la 1re erreur seulement
                    _log(f"flux « {name} » indisponible : {data.get('message')}", xbmc.LOGWARNING)
                self._next_try[name] = now + feeds.RETRY_AFTER_ERROR
                continue
            if self._next_try.pop(name, None) is not None:
                _log(f"flux « {name} » de nouveau disponible")
            if feeds.save(cache, name, data, now):
                changed.append(name)
            _log(f"flux « {name} » à jour en {ui.ms_since(started)} ms", xbmc.LOGDEBUG)
        if changed:
            home = xbmcgui.Window(HOME)
            stamp = str(int(time.time()))
            home.setProperty("arrmada.reload", stamp)
            for name in changed:
                home.setProperty(f"arrmada.reload.{name}", stamp)
            _log(f"flux mis à jour : {', '.join(sorted(changed))}")


class EventListener(threading.Thread):
    """Écoute le temps réel du serveur, avec reconnexion automatique."""

    def __init__(self, monitor: xbmc.Monitor, refresher: FeedRefresher) -> None:
        super().__init__(name="arrmada-events", daemon=True)
        self._monitor = monitor
        self._refresher = refresher
        self.connected = False  # lu par service.py (ancienne surveillance en repli)
        self._last_id = 0
        self._baselined = False  # dernier numéro d'événement connu du serveur
        self._last_scan = 0.0
        self._stopping = threading.Event()
        self._response = None

    def stop(self) -> None:
        """Arrêt de Kodi : coupe la connexion pour débloquer la lecture en cours.

        Sans ça, le fil resterait bloqué jusqu'à 60 s dans readline() et Kodi
        tuerait le service au bout de 5 s (trace d'erreur dans kodi.log).
        """
        self._stopping.set()
        response = self._response
        if response is not None:
            try:
                response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
            except Exception:  # déjà fermée, ou structure interne différente
                pass

    def _should_stop(self) -> bool:
        return self._stopping.is_set() or self._monitor.abortRequested()

    def run(self) -> None:
        backoff = 5
        while not self._should_stop():
            started = time.monotonic()
            try:
                self._listen()
                if time.monotonic() - started < SHORT_CONNECTION:
                    raise ConnectionError("connexion refermée aussitôt")
                backoff = 5
                # Fin normale (délai de lecture, serveur redémarré) : on rouvre
                # tout de suite ; le rattrapage récupère ce qui a été publié.
                if self._monitor.waitForAbort(1):
                    break
            except Exception as exc:  # réseau, serveur arrêté, jeton refusé…
                if self._should_stop():
                    break
                if self.connected:
                    _log(f"temps réel interrompu : {exc}", xbmc.LOGWARNING)
                self.connected = False
                if self._monitor.waitForAbort(backoff) or self._stopping.is_set():
                    break
                backoff = min(backoff * 2, MAX_BACKOFF)
        self.connected = False

    def _listen(self) -> None:
        """Lit le flux jusqu'à sa fin (délai de lecture ou fermeture)."""
        response = ArrMadaAPI.open_stream(STREAM_PATH, timeout=READ_TIMEOUT)
        self._response = response
        if not self.connected:
            _log("temps réel connecté")
        self.connected = True
        self._catch_up()
        parser = feeds.SSEParser()
        try:
            while not self._should_stop():
                try:
                    raw = response.readline()
                except OSError:  # délai de lecture dépassé ou arrêt : on rouvrira
                    return
                if not raw:
                    return  # fermé par le serveur
                event = parser.feed(raw.decode("utf-8", "replace"))
                if event:
                    self._handle(*event)
        finally:
            self._response = None
            response.close()

    def _catch_up(self) -> None:
        """Événements publiés pendant une coupure (le serveur en garde 50).

        À la toute première connexion, on note seulement le dernier numéro
        (pas de notification pour des imports d'avant le démarrage de Kodi).
        """
        recent = ArrMadaAPI.get_feed(f"/api/events/recent?since_id={self._last_id}", timeout=10)
        if not isinstance(recent, dict):
            return
        if not self._baselined:
            self._baselined = True
            ids = [int(e["id"]) for e in recent.get("events") or [] if str(e.get("id")).isdigit()]
            self._last_id = max(ids + [self._last_id])
            return
        for event in recent.get("events") or []:
            event_id = str(event.get("id"))
            if event_id.isdigit() and int(event_id) <= self._last_id:
                continue  # déjà traité avant la coupure
            self._handle(event.get("type", ""), event.get("data") or {}, event_id)

    def _handle(self, event_type: str, data: dict, event_id: str) -> None:
        # Les numéros repartent de 1 si le serveur redémarre : en direct, on
        # prend toujours le dernier reçu (pas de comparaison avec l'ancien).
        if event_id.isdigit():
            self._last_id = int(event_id)
        names = feeds.feeds_for_event(event_type, data)
        if names:
            self._refresher.force(names)
        message = feeds.osd_message(event_type, data)
        if message and get_setting_bool("enable_notifications", default=True):
            ui.notify(message[0], message[1], 6000)
        if event_type == "new_import":
            self._scan_library()

    def _scan_library(self) -> None:
        """Nouveau fichier sur le NAS : la médiathèque Kodi le découvre."""
        now = time.time()
        if now - self._last_scan >= LIBRARY_SCAN_EVERY:
            self._last_scan = now
            _log("nouvel import : scan de la médiathèque vidéo")
            xbmc.executebuiltin("UpdateLibrary(video)")

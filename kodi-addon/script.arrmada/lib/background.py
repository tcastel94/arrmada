# -*- coding: utf-8 -*-
"""Travail de fond du service (ADR-003 § 1) : cache des flux + événements.

Depuis la 1.7.1, **aucun fil d'exécution de fond** : tout se fait par petits
morceaux, dans la boucle principale du service (un tour par seconde), comme
dans la 1.4.2. À chaque tour, `BackgroundTasks.tick()` fait au plus :

  1. un relevé des événements du serveur (`/api/events/recent`), toutes les
     5 s. Un import, un téléchargement lancé… déclenche une bulle à l'écran
     (avec l'affiche du titre, phase 3) et le rafraîchissement immédiat des
     flux concernés. Pendant un film, rien ne s'affiche : un résumé
     « Pendant ta séance » apparaît à l'arrêt (réglage « Notifications
     pendant la lecture ») ;
  2. le téléchargement d'UN flux (le plus urgent) vers le cache local.
     Quand un flux change, `arrmada.reload` est publié dans la mémoire
     commune de Kodi (Window(10000)) : un widget de skin qui ajoute
     `&reload=$INFO[Window(Home).Property(arrmada.reload)]` à son chemin se
     recharge alors tout seul.

Pourquoi ce choix (incident 1.7.0, Kodi qui se fermait sur la Shield) : la
1.7.0 utilisait deux fils permanents, dont une connexion réseau ouverte en
continu. C'est la seule vraie nouveauté du service par rapport à la 1.4.2,
qui tournait sans souci. Un relevé toutes les 5 s coûte une requête minuscule
sur le réseau local, et un service à un seul fil s'arrête toujours proprement.

Analogie : on passe d'un démon qui garde une socket ouverte à un cron très
rapproché. Le relevé des événements sert aussi de sonde de santé (comme le
« health check » d'un répartiteur de charge) : serveur injoignable → plus
aucun téléchargement de flux, nouvel essai avec une attente croissante
(5 s, 10 s, 20 s… 2 min).
"""

from __future__ import annotations

import time

import xbmc
import xbmcgui

import feeds
import ui_common as ui
from api import ArrMadaAPI
from kodi_helper import get_setting_bool

HOME = 10000  # fenêtre « Accueil » de Kodi : ses propriétés sont visibles partout
EVENTS_PATH = "/api/events/recent"
# Délais réseau courts : chaque requête bloque la boucle du service, et Kodi
# coupe un service qui met plus de 5 s à s'arrêter.
EVENTS_TIMEOUT = 3
FEED_TIMEOUT = 4
MAX_BACKOFF = 120
LIBRARY_SCAN_EVERY = 60  # au plus un scan de médiathèque par minute


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Service : {message}", level)


def _watching() -> bool:
    """Un film ou un épisode est à l'écran (lecture ou pause)."""
    return bool(xbmc.getCondVisibility("Player.HasVideo"))


class BackgroundTasks:
    """Cache des flux et relevé des événements, un petit morceau par tour."""

    def __init__(self, monitor: xbmc.Monitor) -> None:
        self._monitor = monitor
        self._cursor = feeds.EventCursor()
        self._next_poll = 0.0  # prochain relevé des événements
        self._backoff = feeds.EVENTS_EVERY
        self._forced: set = set()  # flux réclamés par un événement
        self._fetched_at: dict = {}  # nom → date du cache (lue une fois sur disque)
        self._retry_at: dict = {}  # nom → prochain essai après une erreur
        self._changed: set = set()  # flux modifiés, pas encore annoncés au skin
        self._last_scan = 0.0
        self._held: list = []  # bulles retenues pendant un film (résumé à l'arrêt)
        self.connected = False  # le dernier relevé a réussi (lu par service.py)

    def tick(self) -> None:
        """Un tour de boucle : au plus un relevé et un flux."""
        now = time.time()
        if now >= self._next_poll:
            self._poll_events(now)
        if self._held and not _watching():
            # Film terminé : ce qui s'est passé pendant la séance, en une bulle
            self._show(feeds.merge_notifications(self._held, heading="Pendant ta séance"))
            self._held = []
        if self.connected and not self._monitor.abortRequested():
            self._refresh_one_feed(now)

    # ── Événements ──────────────────────────────────────────────────────

    def _poll_events(self, now: float) -> None:
        response = ArrMadaAPI.get_feed(
            f"{EVENTS_PATH}?since_id={self._cursor.last_id}", timeout=EVENTS_TIMEOUT
        )
        if feeds.is_error(response):
            if self.connected:
                _log(f"serveur injoignable : {response.get('message')}", xbmc.LOGWARNING)
            self.connected = False
            self._next_poll = now + self._backoff
            self._backoff = min(self._backoff * 2, MAX_BACKOFF)
            return
        if not self.connected:
            _log("relevé des événements actif (toutes les 5 s)")
        self.connected = True
        self._backoff = feeds.EVENTS_EVERY
        self._next_poll = now + feeds.EVENTS_EVERY

        fresh = self._cursor.accept(response)
        if fresh is None:  # serveur redémarré : ses numéros sont repartis de 1
            _log("serveur redémarré : relecture des événements depuis le début")
            response = ArrMadaAPI.get_feed(f"{EVENTS_PATH}?since_id=0", timeout=EVENTS_TIMEOUT)
            fresh = [] if feeds.is_error(response) else (self._cursor.accept(response) or [])
        bubbles = []
        for _, event_type, data in fresh:
            bubble = self._handle(event_type, data)
            if bubble:
                bubbles.append(bubble)
        if not bubbles or not get_setting_bool("enable_notifications", default=True):
            return
        if _watching() and not get_setting_bool("notify_during_playback", default=False):
            self._held.extend(bubbles)  # pas de bulle sur le film : résumé à l'arrêt
            return
        self._show(feeds.merge_notifications(bubbles))

    def _handle(self, event_type: str, data: dict):
        """Rafraîchissements et scan pour un événement ; sa bulle (ou None)."""
        self._forced |= feeds.feeds_for_event(event_type, data)
        # Un titre seulement ajouté à Radarr/Sonarr n'a pas encore de fichier
        if event_type == "new_import" and data.get("event", "Download") == "Download":
            self._scan_library()
        return feeds.osd_notification(event_type, data)

    @staticmethod
    def _show(bubbles: list) -> None:
        """Bulles en haut de l'écran, avec l'affiche du titre, sans son."""
        dialog = xbmcgui.Dialog()
        for bubble in bubbles:
            icon = bubble.get("icon") or ui.ADDON.getAddonInfo("icon")
            dialog.notification(bubble["heading"], bubble["message"], icon, 7000, False)

    def _scan_library(self) -> None:
        """Nouveau fichier sur le NAS : la médiathèque Kodi le découvre."""
        now = time.time()
        if now - self._last_scan < LIBRARY_SCAN_EVERY:
            return
        self._last_scan = now
        if xbmc.getCondVisibility("Library.IsScanningVideo"):
            return  # un scan tourne déjà (lancé par le serveur, par exemple)
        _log("nouvel import : scan de la médiathèque vidéo")
        xbmc.executebuiltin("UpdateLibrary(video)")

    # ── Flux en cache ───────────────────────────────────────────────────

    def _cache_dates(self, cache: str) -> dict:
        """Date de chaque flux en cache (lue sur disque au premier tour seulement)."""
        for name in feeds.FEEDS:
            if name not in self._fetched_at:
                entry = feeds.load(cache, name)
                self._fetched_at[name] = float((entry or {}).get("fetched_at") or 0)
        return self._fetched_at

    def _refresh_one_feed(self, now: float) -> None:
        cache = ui.cache_dir()
        name = feeds.next_feed(self._forced, self._cache_dates(cache), self._retry_at, now)
        if name is None:
            return
        self._forced.discard(name)
        started = time.perf_counter()
        data = ArrMadaAPI.get_feed(feeds.FEEDS[name].path, timeout=FEED_TIMEOUT)
        if feeds.is_error(data):
            if name not in self._retry_at:  # journal à la 1re erreur seulement
                _log(f"flux « {name} » indisponible : {data.get('message')}", xbmc.LOGWARNING)
            self._retry_at[name] = now + feeds.RETRY_AFTER_ERROR
            return
        if self._retry_at.pop(name, None) is not None:
            _log(f"flux « {name} » de nouveau disponible")
        if feeds.save(cache, name, data, now):
            self._changed.add(name)
        self._fetched_at[name] = now
        _log(f"flux « {name} » à jour en {ui.ms_since(started)} ms", xbmc.LOGDEBUG)
        # Annonce au skin une fois la série de rafraîchissements terminée :
        # les widgets se rechargent une fois, pas six au démarrage de Kodi.
        if (
            self._changed
            and feeds.next_feed(self._forced, self._fetched_at, self._retry_at, now) is None
        ):
            self._announce()

    def _announce(self) -> None:
        home = xbmcgui.Window(HOME)
        stamp = str(int(time.time() * 1000))  # unique, même pour deux annonces dans la seconde
        home.setProperty("arrmada.reload", stamp)
        for name in self._changed:
            home.setProperty(f"arrmada.reload.{name}", stamp)
        _log(f"flux mis à jour : {', '.join(sorted(self._changed))}")
        self._changed.clear()

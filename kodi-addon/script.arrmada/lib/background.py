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
  2. une étape de la synchronisation vu / reprise entre les TV
     (lib/watch_sync.py, phase 4.4) : relire ce qui a changé ailleurs,
     déposer ce qui a changé ici ;
  3. le téléchargement d'UN flux (le plus urgent) vers le cache local.
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

import base64
import os
import time
import urllib.parse
from datetime import datetime, timezone

import xbmc
import xbmcgui

import camera_data
import device
import feeds
import pairing_data
import ready_data
import remote_data
import sync_data
import toast
import ui_common as ui
import watch_sync
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
        self._ready_held: list = []  # « Prêt à regarder » arrivés pendant un film
        self.sync = watch_sync.WatchSync(monitor)  # vu / reprise partagés (phase 4.4)
        self.connected = False  # le dernier relevé a réussi (lu par service.py)

    def tick(self) -> None:
        """Un tour de boucle : au plus un relevé, une étape de synchro et un flux."""
        now = time.time()
        home = xbmcgui.Window(HOME)
        if home.getProperty(pairing_data.PAIRED_NOW) == "1":
            home.clearProperty(pairing_data.PAIRED_NOW)
            self._after_pairing(now)
        if now >= self._next_poll:
            self._poll_events(now)
        if self._held and not _watching():
            # Film terminé : ce qui s'est passé pendant la séance, en une bulle
            self._show(feeds.merge_notifications(self._held, heading="Pendant ta séance"))
            self._held = []
        if self._ready_held and not _watching():
            # Film terminé : le titre arrivé entre-temps (le plus récent)
            self._open_ready(self._ready_held[-1])
            self._ready_held = []
        if self.connected and not self._monitor.abortRequested():
            self.sync.tick(now)
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
            self.sync.wake()  # changements faits ailleurs pendant la coupure
            self._refresh_device()
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

    def _after_pairing(self, now: float) -> None:
        """TV tout juste appairée (1.19.1) : relevé, flux et vu partagé tout de suite.

        Avant l'appairage, le serveur refusait la TV : les essais étaient
        espacés (jusqu'à 2 min). Sans ce coup de pouce, l'accueil resterait
        vide quelques minutes.
        """
        _log("TV appairée : relevé des événements et des flux tout de suite")
        self._next_poll = now
        self._backoff = feeds.EVENTS_EVERY
        self._retry_at.clear()
        self._forced |= set(feeds.FEEDS)
        self.sync.wake()

    def _refresh_device(self) -> None:
        """Nom, pièce et ampli de cette TV tels que réglés dans la web app.

        Ils peuvent avoir changé depuis l'appairage (TV déplacée au bureau :
        plus d'ampli). Lu à chaque (re)connexion au serveur.
        """
        if not device.load().get("token"):
            return
        me = ArrMadaAPI.device_me()
        if feeds.is_error(me) or not me.get("paired"):
            return
        device.update(
            {key: me[key] for key in ("name", "room", "avr_name", "has_amp") if key in me}
        )

    def _handle(self, event_type: str, data: dict):
        """Rafraîchissements et scan pour un événement ; sa bulle (ou None)."""
        if event_type == camera_data.EVENT:
            self._camera(data)  # jamais retenue pour « Pendant ta séance »
            return None
        if event_type == sync_data.EVENT:
            self.sync.wake()  # une autre TV a vu / repris un titre : on relit
            return None
        if event_type == remote_data.EVENT:
            self._remote_play(data)  # « Lire sur la TV » depuis la web app (1.19)
            return None
        if event_type == ready_data.EVENT:
            self._ready(data)  # « Prêt à regarder » (ADR-005, lot 4)
            return None
        self._forced |= feeds.feeds_for_event(event_type, data)
        # Un titre seulement ajouté à Radarr/Sonarr n'a pas encore de fichier
        if event_type == "new_import" and data.get("event", "Download") == "Download":
            self._scan_library()
        return feeds.osd_notification(event_type, data)

    # ── « Lire sur la TV » depuis la web app (1.19.0) ───────────────────

    def _remote_play(self, data: dict) -> None:
        """Demande adressée à CETTE TV et récente : lecture dans une invocation à part.

        La recherche dans la médiathèque et l'empilement des épisodes suivants
        prennent quelques secondes : hors de la boucle du service, qui ne doit
        jamais attendre (règle de la 1.7.1).
        """
        now = datetime.now(timezone.utc)
        if not remote_data.for_me(data, device.load().get("id"), now):
            return  # pour une autre TV, ou trop vieille (TV rallumée, serveur redémarré)
        params = remote_data.plugin_params(data)
        _log(f"lecture demandée depuis la web app : {remote_data.describe(params)}")
        query = urllib.parse.urlencode(params)
        xbmc.executebuiltin(f"RunPlugin(plugin://script.arrmada/?{query})")

    # ── « Prêt à regarder » (ADR-005, lot 4) ─────────────────────────────

    def _ready(self, data: dict) -> None:
        """Titre demandé par CETTE TV : pop-up « Regarder », après le film en cours."""
        now = datetime.now(timezone.utc)
        if not ready_data.for_me(data, device.load().get("id"), now):
            return  # lancé depuis une autre TV (elle a sa propre pop-up)
        params = ready_data.popup_params(data)
        if _watching():
            _log(f"prêt à regarder pendant la lecture : {params.get('title')} (après le film)")
            self._ready_held.append(params)
            return
        self._open_ready(params)

    def _open_ready(self, params: dict) -> None:
        """Pop-up dans une invocation à part : la boucle du service n'attend jamais."""
        _log(f"prêt à regarder : {params.get('title')}")
        query = urllib.parse.urlencode(params)
        xbmc.executebuiltin(f"RunPlugin(plugin://script.arrmada/?{query})")

    # ── Caméras Eufy : pop-up pendant un film, bulle sinon ──────────────

    def _camera(self, data: dict) -> None:
        popup_open = xbmcgui.Window(HOME).getProperty(camera_data.POPUP_PROP) == "1"
        mode = camera_data.wants_popup(
            _watching(), get_setting_bool("camera_alerts", default=True), popup_open
        )
        if not mode:
            return
        image = self._camera_snapshot(camera_data.snapshot_id(data))
        now = xbmc.getInfoLabel("System.Time(HH:mm)")  # heure de la TV, 24 h
        texts = camera_data.popup(data, local_time=now)
        _log(f"caméra : {texts['title']} · {texts['subtitle']} ({mode})")
        if mode == "popup":
            # Fenêtre ouverte par une invocation à part : la boucle du service
            # ne reste jamais bloquée pendant les 5 s de la pop-up.
            query = urllib.parse.urlencode(
                {"action": "camera", "title": texts["title"],
                 "subtitle": texts["subtitle"], "image": image}
            )  # fmt: skip
            xbmc.executebuiltin(f"RunPlugin(plugin://script.arrmada/?{query})")
            return
        bubble = camera_data.bubble(data, image, local_time=now)
        toast.post(
            bubble["heading"], bubble["message"], bubble["icon"], camera_data.NOTIFY_MS, sound=True
        )

    @staticmethod
    def _camera_snapshot(snapshot: int) -> str:
        """Photo de la détection dans le cache de l'add-on ; "" sans photo."""
        if not snapshot:
            return ""
        response = ArrMadaAPI.get_feed(f"/api/cameras/snapshot/{snapshot}", timeout=EVENTS_TIMEOUT)
        if feeds.is_error(response) or not isinstance(response, dict):
            return ""
        try:
            data = base64.b64decode(response.get("image") or "", validate=True)
        except ValueError:
            return ""
        folder = ui.cache_dir()
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, camera_data.file_name(snapshot, int(time.time())))
            with open(path, "wb") as handle:
                handle.write(data)
            # Seules les dernières photos restent (pas d'accumulation sur la TV)
            old = sorted(
                (f for f in os.listdir(folder) if f.startswith("arrmada-camera-")),
                key=lambda name: os.path.getmtime(os.path.join(folder, name)),
            )
            for name in old[: -camera_data.SNAPSHOT_KEEP]:
                os.remove(os.path.join(folder, name))
        except OSError as exc:
            _log(f"photo de caméra non enregistrée : {exc}", xbmc.LOGWARNING)
            return ""
        return path

    @staticmethod
    def _show(bubbles: list) -> None:
        """Bulles avec l'affiche du titre, sans son : en bas à droite sur un écran
        ArrMada (le menu du haut reste visible), bulle Kodi ailleurs."""
        for bubble in bubbles:
            toast.post(bubble["heading"], bubble["message"], bubble.get("icon") or "", 7000)

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

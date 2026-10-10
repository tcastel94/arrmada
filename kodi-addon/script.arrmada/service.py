# -*- coding: utf-8 -*-
"""ArrMada Background Service for Kodi.

- Tracks playback progress and sends scrobbles to ArrMada
- Keeps the local feed cache fresh for native lists and SiLVO widgets, and
  polls the server's recent events every 5 s for TV OSD alerts
  (lib/background.py, ADR-003 § 1). Since 1.7.1 everything runs in this one
  loop: no background thread (1.7.0 closed Kodi on a Shield, see CHANGELOG)
- Startup circuit breaker (lib/startup_guard.py): after two Kodi crashes in a
  row right after startup, the service falls back to "safe mode" (1.4.2
  behaviour: scrobble + legacy download alerts only)
- The old polling of /api/kodi/addon-status only runs while the server's
  events are unreachable (or in safe mode)
"""

from __future__ import annotations

import sys
import os
import time
import xbmc
import xbmcaddon
import xbmcvfs

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
import kodi_helper
from kodi_helper import get_current_item_info, show_notification, get_setting_bool, get_setting_int
from audio_switcher import run_audio_switch
from background import BackgroundTasks
import startup_guard
import threading

ADDON = xbmcaddon.Addon("script.arrmada")


class ArrMadaPlayer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self._last_scrobble_time = 0
        self._current_media_info = None

    def onPlayBackStarted(self):
        if not self.isPlayingVideo():
            return
            
        # Run audio switcher in background so we don't block
        threading.Thread(target=run_audio_switch, args=(self,)).start()

        if not get_setting_bool("enable_scrobble"):
            return


        xbmc.sleep(1000)  # Wait for infolabels to settle
        info = get_current_item_info()
        self._current_media_info = info

        total_time = self.getTotalTime()
        current_time = self.getTime()
        progress = (current_time / total_time * 100) if total_time > 0 else 0

        ArrMadaAPI.send_scrobble({
            "event": "play",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "tmdb_id": info.get("tmdb_id"),
            "season": info.get("season"),
            "episode": info.get("episode"),
            "percentage": round(progress, 1),
            "position": int(current_time),
            "total": int(total_time),
        })

    def onPlayBackPaused(self):
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return

        info = self._current_media_info or get_current_item_info()
        total_time = self.getTotalTime()
        current_time = self.getTime()
        progress = (current_time / total_time * 100) if total_time > 0 else 0

        ArrMadaAPI.send_scrobble({
            "event": "pause",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "percentage": round(progress, 1),
            "position": int(current_time),
            "total": int(total_time),
        })

    def onPlayBackResumed(self):
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return

        info = self._current_media_info or get_current_item_info()
        total_time = self.getTotalTime()
        current_time = self.getTime()
        progress = (current_time / total_time * 100) if total_time > 0 else 0

        ArrMadaAPI.send_scrobble({
            "event": "resume",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "percentage": round(progress, 1),
            "position": int(current_time),
            "total": int(total_time),
        })

    def onPlayBackStopped(self):
        if not get_setting_bool("enable_scrobble"):
            return

        info = self._current_media_info or get_current_item_info()
        self._current_media_info = None

        ArrMadaAPI.send_scrobble({
            "event": "stop",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "percentage": 0,
        })

    def onPlayBackEnded(self):
        if not get_setting_bool("enable_scrobble"):
            return

        info = self._current_media_info or get_current_item_info()
        self._current_media_info = None

        ArrMadaAPI.send_scrobble({
            "event": "stop",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "percentage": 100,
        })

    def check_periodic_progress(self):
        """Send progress update every 30s during active playback."""
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return

        now = time.time()
        if now - self._last_scrobble_time < 30:
            return

        self._last_scrobble_time = now
        info = self._current_media_info or get_current_item_info()
        total_time = self.getTotalTime()
        current_time = self.getTime()
        progress = (current_time / total_time * 100) if total_time > 0 else 0

        ArrMadaAPI.send_scrobble({
            "event": "progress",
            "title": info.get("title"),
            "media_type": info.get("media_type"),
            "tmdb_id": info.get("tmdb_id"),
            "percentage": round(progress, 1),
            "position": int(current_time),
            "total": int(total_time),
        })


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Service : {message}", level=level)


class ServiceMonitor(xbmc.Monitor):
    """Le Monitor du service, prévenu par Kodi quand un réglage de l'add-on change.

    Piège Kodi (lu dans AddonManager.cpp) : à l'enregistrement des réglages,
    Kodi ne recharge que la PREMIÈRE copie de l'add-on en mémoire, alors que
    chaque module en a une (`xbmcaddon.Addon(...)`). Sans ce signal, le service
    ne voyait pas « Mode minimal » décoché (ni l'intervalle de vérification
    changé) avant le redémarrage de Kodi.
    """

    def __init__(self) -> None:
        super().__init__()
        self.settings_changed = False

    def onSettingsChanged(self) -> None:  # appelé par Kodi
        self.settings_changed = True


def _reload_settings() -> None:
    """Copie neuve de l'add-on : relit settings.xml (get_setting_* l'utilisent)."""
    kodi_helper.ADDON = xbmcaddon.Addon("script.arrmada")


def _save_guard(path: str, state: dict) -> None:
    """Le disjoncteur ne doit jamais faire tomber le service."""
    try:
        startup_guard.save(path, state)
    except OSError as exc:
        _log(f"état de démarrage non enregistré : {exc}", xbmc.LOGWARNING)


def _start_tasks(monitor: xbmc.Monitor, guard_file: str):
    """Travail de fond (cache + événements), ou None en mode minimal."""
    if get_setting_bool("safe_mode", default=False):
        _log("mode minimal (réglage) : ni cache des listes ni relevé des événements")
        return None
    state, tripped = startup_guard.on_start(startup_guard.load(guard_file))
    _save_guard(guard_file, state)
    if tripped:
        # Kodi s'est fermé deux fois de suite peu après le démarrage : on
        # passe en mode minimal (comportement de la 1.4.2) et on le dit.
        try:
            ADDON.setSettingBool("safe_mode", True)  # visible dans les paramètres
        except Exception as exc:  # réglage absent (profil abîmé…) : mode minimal quand même
            _log(f"réglage « safe_mode » non enregistré : {exc}", xbmc.LOGWARNING)
        _log(
            f"Kodi s'est fermé {startup_guard.TRIP_AFTER} fois de suite après le démarrage : "
            "mode minimal activé (Paramètres de l'add-on → Avancé pour le retirer)",
            xbmc.LOGWARNING,
        )
        show_notification(
            "ArrMada · mode minimal",
            "Kodi s'est fermé 2 fois au démarrage. Réglage : Paramètres → Avancé",
            is_error=False,
            time_ms=12000,
        )
        return None
    return BackgroundTasks(monitor)


def main():
    monitor = ServiceMonitor()
    player = ArrMadaPlayer()

    xbmc.log("[ArrMada] Service started", level=xbmc.LOGINFO)

    # Cache des flux (listes, widgets) et événements : un petit morceau de
    # travail par tour de boucle, sans fil de fond (lib/background.py).
    guard_file = startup_guard.state_path(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")))
    tasks = _start_tasks(monitor, guard_file)
    healthy_at = time.time() + startup_guard.HEALTHY_AFTER if tasks else 0.0
    _reload_settings()  # le disjoncteur a pu cocher « Mode minimal » à l'instant
    safe_mode = get_setting_bool("safe_mode", default=False)

    last_notification_check = 0
    seen_downloads: set[str] = set()
    seen_event_ids: set[int] = set()
    initial_load = True

    while not monitor.abortRequested():
        # 0. Réglages modifiés pendant que Kodi tourne (case « Mode minimal »…) :
        #    on relit, et on réagit au changement seulement.
        if monitor.settings_changed:
            monitor.settings_changed = False
            _reload_settings()
        wanted = get_setting_bool("safe_mode", default=False)
        if wanted != safe_mode:
            safe_mode = wanted
            if safe_mode:
                _log("mode minimal activé depuis les paramètres")
                tasks = None
            else:
                _log("mode minimal retiré : cache des listes et relevé des événements actifs")
                tasks = BackgroundTasks(monitor)
                healthy_at = time.time() + startup_guard.HEALTHY_AFTER

        # 1. Handle player tracking
        if player.isPlayingVideo():
            player.check_periodic_progress()

        # 2. Cache des flux et événements du serveur (au plus 2 petites requêtes)
        if tasks is not None:
            tasks.tick()
            if healthy_at and time.time() >= healthy_at:
                _save_guard(guard_file, startup_guard.healthy())  # démarrage réussi
                healthy_at = 0.0

        # 3. Check ArrMada notifications / downloads / auto-scan
        now = time.time()
        interval = get_setting_int("check_interval", 15)

        # Ancienne surveillance par interrogation : seulement si les événements
        # du serveur ne sont pas relevés (sinon les notifications arriveraient
        # en double).
        if (
            not (tasks is not None and tasks.connected)
            and get_setting_bool("enable_notifications")
            and (now - last_notification_check >= interval)
        ):
            last_notification_check = now
            try:
                status = ArrMadaAPI.get_addon_status()
                if status.get("status") == "ok":
                    current_downloads = {d.get("title") for d in status.get("downloads", []) if d.get("title")}
                    recent_events = status.get("recent_events", [])

                    if initial_load:
                        seen_downloads = current_downloads
                        seen_event_ids = {ev.get("id") for ev in recent_events if ev.get("id")}
                        initial_load = False
                    else:
                        # 1. Find downloads that finished
                        finished = seen_downloads - current_downloads
                        should_scan = False

                        for title in finished:
                            show_notification("ArrMada", f"📥 Téléchargement terminé : {title}", is_error=False, time_ms=6000)
                            should_scan = True

                        # 2. Check new import events from activity log
                        for ev in recent_events:
                            ev_id = ev.get("id")
                            if ev_id and ev_id not in seen_event_ids:
                                seen_event_ids.add(ev_id)
                                ev_title = ev.get("title") or "Nouveau média"
                                show_notification("ArrMada", f"📥 Importé sur le NAS : {ev_title}", is_error=False, time_ms=5000)
                                should_scan = True

                        # 3. Trigger Kodi Video Library auto-scan if any new media was added
                        if should_scan:
                            xbmc.log("[ArrMada] New media detected, triggering Kodi UpdateLibrary(video)", level=xbmc.LOGINFO)
                            xbmc.executebuiltin("UpdateLibrary(video)")

                        seen_downloads = current_downloads
            except Exception as exc:
                xbmc.log(f"[ArrMada] Service notification error: {exc}", level=xbmc.LOGDEBUG)

        if monitor.waitForAbort(1):
            break

    # Arrêt propre (sortie de Kodi, mise à jour de l'add-on) : ce n'est pas
    # un plantage, le disjoncteur repart de zéro.
    _save_guard(guard_file, startup_guard.healthy())
    xbmc.log("[ArrMada] Service stopped", level=xbmc.LOGINFO)


if __name__ == "__main__":
    main()


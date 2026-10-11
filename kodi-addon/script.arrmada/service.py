# -*- coding: utf-8 -*-
"""ArrMada Background Service for Kodi.

- Tracks playback progress and sends scrobbles to ArrMada (since 1.10.0 also
  the poster, episode and pause state for the living-room ambient screen,
  lib/playback_data.py)
- Keeps the local feed cache fresh for native lists and SiLVO widgets, and
  polls the server's recent events every 5 s for TV OSD alerts
  (lib/background.py, ADR-003 § 1). Since 1.7.1 everything runs in this one
  loop: no background thread (1.7.0 closed Kodi on a Shield, see CHANGELOG)
- Startup circuit breaker (lib/startup_guard.py): after two Kodi crashes in a
  row right after startup, the service falls back to "safe mode" (1.4.2
  behaviour: scrobble + legacy download alerts only)
- The old polling of /api/kodi/addon-status only runs while the server's
  events are unreachable (or in safe mode)
- Phase 3: the TV never sends the admin password any more. A TV that still
  has it in its settings pairs itself once, then erases it (lib/migration.py)
- ADR-004 phase 4.2: when Kodi's own home screen is shown (startup, back from
  an add-on), the ArrMada home opens instead (setting "shell_mode"; never in
  safe mode, never on top of a dialog or a video, suspended for the session
  when the user picks "Kodi interface"; lib/shell_data.should_open_shell)
- ADR-004 phase 4.4: watched / resume shared between the TVs (the library
  item that just changed is handed to lib/watch_sync.py, which posts it from
  the background tasks), and the "Next episode" card a few seconds before
  the end of a library episode (lib/upnext_window.py)
"""

from __future__ import annotations

import sys
import os
import time
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
import kodi_helper
from kodi_helper import show_notification, get_setting_bool, get_setting_int
from audio_switcher import run_audio_switch
from background import BackgroundTasks
import migration
import playback_data
import shell_data
import startup_guard
import sync_data
import threading
import upnext_data
import watch_sync

ADDON = xbmcaddon.Addon("script.arrmada")
MIGRATION_RETRY = 300  # s entre deux essais d'appairage automatique (serveur injoignable)


def _read_playing_item(player: xbmc.Player) -> dict:
    """Ce que lit le LECTEUR (jamais l'élément sélectionné dans une liste)."""
    labels = {key: xbmc.getInfoLabel(label) for key, label in playback_data.LABELS.items()}
    media_type = ""
    try:
        media_type = player.getVideoInfoTag().getMediaType()
    except Exception:  # la lecture vient de s'arrêter : les libellés suffisent
        pass
    return playback_data.playing_item(labels, media_type)


class ArrMadaPlayer(xbmc.Player):
    """Suivi de lecture envoyé au serveur (historique + écran d'appoint du salon).

    1.10.0 : infos lues sur le lecteur (VideoPlayer.*), affiche et fond,
    indicateur de pause dans le relevé des 30 s, dernière position gardée
    pour l'arrêt (Kodi ne la donne plus une fois la vidéo arrêtée).
    """

    def __init__(self):
        super().__init__()
        self._last_scrobble_time = 0.0
        self._item = None  # vidéo suivie (None : rien, ou de la musique)
        self._position = 0.0
        self._total = 0.0
        # Élément de la médiathèque Kodi en lecture : ("movie" | "episode", n°)
        # ou None (fichier hors médiathèque). Sert au partage vu / reprise et
        # à l'encart « Épisode suivant » (phase 4.4).
        self._library_item = None
        self._upnext_offered = False

    def _track_library_item(self) -> None:
        """Nouvelle vidéo : celle d'avant (épisode enchaîné) part au partage vu / reprise."""
        try:
            tag = self.getVideoInfoTag()
            kind, dbid = tag.getMediaType(), tag.getDbId()
        except Exception:  # lecture déjà arrêtée
            kind, dbid = "", 0
        current = (kind, dbid) if kind in sync_data.ID_ORDER and dbid > 0 else None
        if self._library_item and self._library_item != current:
            watch_sync.schedule(*self._library_item)
        self._library_item = current
        self._upnext_offered = False

    def _release_library_item(self) -> None:
        """Arrêt ou fin : Kodi enregistre vu / reprise, on le dépose dans 3 s."""
        if self._library_item:
            watch_sync.schedule(*self._library_item)
        self._library_item = None

    def _times(self):
        """(position, durée) en secondes ; les dernières connues si Kodi ne répond plus."""
        try:
            position, total = self.getTime(), self.getTotalTime()
        except Exception:
            return self._position, self._total
        self._position, self._total = position, total
        return position, total

    def _send(self, event: str, paused: bool = False, ended: bool = False) -> None:
        if self._item is None:
            return
        position, total = (self._position, self._total) if event == "stop" else self._times()
        payload = playback_data.scrobble_payload(
            event, self._item, position, total, paused=paused, ended=ended
        )
        ArrMadaAPI.send_scrobble(payload)

    def onPlayBackStarted(self):
        # Nouvelle lecture (ou épisode suivant enchaîné) : on oublie la précédente.
        # Le relevé des 30 s repart de zéro : le « play » d'onAVStarted vient d'abord.
        self._item = None
        self._position = self._total = 0.0
        self._last_scrobble_time = time.time()
        if not self.isPlayingVideo():
            return

        # Run audio switcher in background so we don't block
        threading.Thread(target=run_audio_switch, args=(self,)).start()

    def onAVStarted(self):
        """Image et son démarrés : titre, épisode, durée et images sont connus."""
        if not self.isPlayingVideo():
            return
        self._track_library_item()
        if not get_setting_bool("enable_scrobble"):
            return
        self._item = _read_playing_item(self)
        self._last_scrobble_time = time.time()
        self._send("play")

    def onPlayBackPaused(self):
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return
        self._send("pause", paused=True)

    def onPlayBackResumed(self):
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return
        self._send("resume")

    def onPlayBackStopped(self):
        if get_setting_bool("enable_scrobble"):
            self._send("stop")
        self._item = None
        self._release_library_item()

    def onPlayBackEnded(self):
        if get_setting_bool("enable_scrobble"):
            self._send("stop", ended=True)
        self._item = None
        self._release_library_item()

    def check_upnext(self) -> None:
        """Encart « Épisode suivant » quand il reste N s (réglage) d'un épisode."""
        if self._upnext_offered or not self._library_item or self._library_item[0] != "episode":
            return
        threshold = upnext_data.seconds_setting(kodi_helper.ADDON.getSetting("upnext_seconds"))
        try:
            position, total = self.getTime(), self.getTotalTime()
        except Exception:
            return
        if not upnext_data.should_offer(total - position, total, threshold, False, True):
            return
        self._upnext_offered = True  # une seule fois par épisode, même sans suite
        import upnext_window  # chargé seulement quand il sert

        upnext_window.offer(self._library_item[1])

    def check_periodic_progress(self):
        """Position toutes les 30 s, pause comprise (Kodi reste « en lecture » en pause)."""
        if not self.isPlayingVideo() or not get_setting_bool("enable_scrobble"):
            return

        now = time.time()
        if now - self._last_scrobble_time < playback_data.PROGRESS_EVERY:
            return

        self._last_scrobble_time = now
        if self._item is None:  # service démarré pendant une lecture
            self._item = _read_playing_item(self)
        self._send("progress", paused=xbmc.getCondVisibility("Player.Paused"))


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Service : {message}", level=level)


class ShellWatch:
    """Rouvre l'accueil ArrMada quand l'accueil de Kodi s'affiche (ADR-004, 4.2).

    Comme un `Restart=always` de systemd, mais avec une limite : au-delà de
    3 ouvertures en une minute (écran qui se fermerait tout seul), on
    s'arrête jusqu'au prochain démarrage de Kodi.
    """

    def __init__(self) -> None:
        self.history: list = []
        self.last_open = 0.0

    def tick(self, safe_mode: bool) -> None:
        home = xbmcgui.Window(10000)
        now = time.time()
        state = {
            "enabled": get_setting_bool("shell_mode", default=True),
            "safe_mode": safe_mode,
            "suspended": bool(home.getProperty(shell_data.SHELL_OFF)),
            "home_active": xbmc.getCondVisibility("Window.IsActive(home)"),
            "modal": xbmc.getCondVisibility(
                "System.HasActiveModalDialog | System.ScreenSaverActive"
            ),
            "playing": xbmc.getCondVisibility("Player.HasVideo"),
            "shell_open": bool(home.getProperty(shell_data.SHELL_PROP)),
            "opening_age": (now - self.last_open) if self.last_open else None,
        }
        if not shell_data.should_open_shell(state):
            return
        if shell_data.opens_too_often(self.history, now):
            home.setProperty(shell_data.SHELL_OFF, "1")
            _log(
                "l'accueil ArrMada se referme tout seul : retour automatique arrêté "
                "jusqu'au prochain démarrage de Kodi",
                xbmc.LOGWARNING,
            )
            return
        self.history = [t for t in self.history if now - t <= shell_data.OPEN_WINDOW] + [now]
        self.last_open = now
        _log("accueil de Kodi à l'écran : ouverture de l'accueil ArrMada")
        xbmc.executebuiltin("RunPlugin(plugin://script.arrmada/?action=shell)")


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

    def onNotification(self, sender, method, data) -> None:  # appelé par Kodi
        """« Marqué vu / non vu » (ici, dans Kodi ou un autre add-on) : à partager."""
        item = sync_data.library_update(method, data)
        if item:
            watch_sync.schedule(*item, delay=1)


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
    # Ancien mot de passe encore là : appairage automatique (tout de suite,
    # puis toutes les 5 min tant que le serveur ne répond pas).
    migrate_at = time.time() if migration.needed() else 0.0

    shell = ShellWatch()
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

        # 0b. Ancien mot de passe → appairage automatique (phase 3)
        if migrate_at and time.time() >= migrate_at:
            outcome = migration.run()
            migrate_at = time.time() + MIGRATION_RETRY if outcome == "retry" else 0.0
            _reload_settings()  # le mot de passe vient d'être effacé
            if outcome == "done" and tasks is not None:
                tasks = BackgroundTasks(monitor)  # relevés tout de suite, avec le jeton

        # 1. Handle player tracking (+ encart « Épisode suivant », phase 4.4)
        if player.isPlayingVideo():
            player.check_periodic_progress()
            if not safe_mode:
                try:
                    player.check_upnext()
                except Exception as exc:  # jamais au point de faire tomber le service
                    _log(f"épisode suivant : {exc}", xbmc.LOGWARNING)

        # 1b. Accueil de Kodi à l'écran → accueil ArrMada (ADR-004, phase 4.2)
        try:
            shell.tick(safe_mode)
        except Exception as exc:  # jamais au point de faire tomber le service
            _log(f"retour automatique : {exc}", xbmc.LOGWARNING)

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


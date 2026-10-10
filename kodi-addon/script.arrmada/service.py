# -*- coding: utf-8 -*-
"""ArrMada Background Service for Kodi.

- Tracks playback progress and sends scrobbles to ArrMada
- Keeps the local feed cache fresh for native lists and SiLVO widgets
  (lib/background.py, ADR-003 § 1)
- Listens to the server's real-time stream (SSE) for TV OSD alerts; the old
  polling of /api/kodi/addon-status only runs while the stream is down
"""

from __future__ import annotations

import sys
import os
import time
import xbmc
import xbmcaddon

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import get_current_item_info, show_notification, get_setting_bool, get_setting_int
from audio_switcher import run_audio_switch
from background import EventListener, FeedRefresher
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


def main():
    monitor = xbmc.Monitor()
    player = ArrMadaPlayer()

    xbmc.log("[ArrMada] Service started", level=xbmc.LOGINFO)

    # Cache des flux (listes, widgets) et temps réel : deux fils de fond
    refresher = FeedRefresher(monitor)
    refresher.start()
    listener = EventListener(monitor, refresher)
    listener.start()

    last_notification_check = 0
    seen_downloads: set[str] = set()
    seen_event_ids: set[int] = set()
    initial_load = True

    while not monitor.abortRequested():
        # 1. Handle player tracking
        if player.isPlayingVideo():
            player.check_periodic_progress()

        # 2. Check ArrMada notifications / downloads / auto-scan
        now = time.time()
        interval = get_setting_int("check_interval", 15)

        # Ancienne surveillance par interrogation : seulement si le temps réel
        # est coupé (sinon les notifications arriveraient en double).
        if (
            not listener.connected
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

    # Arrêt propre des fils de fond : Kodi tue le service s'il traîne > 5 s
    listener.stop()
    refresher.stop()
    listener.join(3)
    refresher.join(3)
    xbmc.log("[ArrMada] Service stopped", level=xbmc.LOGINFO)


if __name__ == "__main__":
    main()


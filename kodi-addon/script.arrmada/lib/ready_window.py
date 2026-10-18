# -*- coding: utf-8 -*-
"""Pop-up « Prêt à regarder » (ADR-005, lot 4).

Mise en page : resources/skins/Default/1080i/script-arrmada-ready.xml.
Logique : lib/ready_data.py. Ouverte par le service (RunPlugin …?action=ready)
sur la TV qui a lancé la demande, jamais pendant un film.

« Regarder » lance le titre depuis la médiathèque Kodi de cette TV, comme
« Lire sur la TV » (kodi_library.remote_play). Le titre vient d'arriver sur
le NAS : si cette TV ne l'a pas encore dans sa médiathèque, on la met à jour
et on réessaie pendant une trentaine de secondes.
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import ready_data
import ui_common as ui

XML_FILE = "script-arrmada-ready.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
BUTTONS = 970
BTN_WATCH = 971
BTN_LATER = 972

POPUP_PROP = "arrmada.ready_open"  # une seule pop-up à la fois
LIBRARY_TRIES = 7  # essais de lecture (≈ 30 s) le temps que Kodi voie le fichier
LIBRARY_WAIT = 5


class ReadyPopup(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._params = dict(kwargs.get("params") or {})
        self._closed = threading.Event()
        self.watch = False  # « Regarder » choisi (lu après la fermeture)

    def onInit(self):
        texts = ready_data.texts(self._params)
        self.setProperty("title", texts["title"])
        self.setProperty("details", texts["details"])
        self.setProperty("poster", self._params.get("poster") or "")
        can_play = ready_data.can_play(self._params)
        self.setProperty("can_play", "1" if can_play else "")
        ui.focus_when_visible(self, BTN_WATCH if can_play else BTN_LATER)
        threading.Thread(target=self._timer, name="arrmada-ready", daemon=True).start()

    def _timer(self) -> None:
        monitor = xbmc.Monitor()
        left = float(ready_data.DISPLAY_SECONDS)
        while left > 0 and not self._closed.is_set() and not ui.SHUTDOWN.is_set():
            if monitor.waitForAbort(0.5):
                break
            left -= 0.5
        self.close_popup()

    def close_popup(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            self.close()

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_popup()

    def onClick(self, controlId):
        if controlId == BTN_WATCH:
            self.watch = True
        self.close_popup()


def _watch(params: dict) -> None:
    """Lecture ; titre pas encore dans la médiathèque de la TV : mise à jour et réessais."""
    import kodi_library

    play = ready_data.play_params(params)
    monitor = xbmc.Monitor()
    for attempt in range(LIBRARY_TRIES):
        last = attempt == LIBRARY_TRIES - 1
        if kodi_library.remote_play(play, quiet=not last):
            return
        if attempt == 0:
            ui.notify(params.get("title") or "ArrMada", "Mise à jour de la médiathèque de la TV…")
            xbmc.executebuiltin("UpdateLibrary(video)")
        if last or monitor.waitForAbort(LIBRARY_WAIT):
            return


def show(params: dict) -> None:
    """Affiche la pop-up (bloque jusqu'à sa fermeture), puis lance la lecture si demandé."""
    home = xbmcgui.Window(10000)
    if home.getProperty(POPUP_PROP) == "1":
        return
    home.setProperty(POPUP_PROP, "1")
    window = ReadyPopup(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", params=params)
    try:
        ui.log("Prêt à regarder", ready_data.texts(params)["title"])
        window.doModal()
        watch = window.watch
    finally:
        window._closed.set()
        home.clearProperty(POPUP_PROP)
        del window
    if watch:
        _watch(params)

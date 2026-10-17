# -*- coding: utf-8 -*-
"""Bouton « Passer l'intro » / « Passer le récap » (1.17.0).

Mise en page : resources/skins/Default/1080i/script-arrmada-skip.xml.
Logique pure (reconnaître un chapitre d'intro) : lib/chapter_data.py.

Ouvert par le service (RunPlugin …?action=skip) quand le chapitre en cours
s'appelle Intro, Opening, Previously on… Le bouton reste 10 s, ou jusqu'à
la fin du chapitre. OK : saut à l'heure exacte du chapitre suivant (`to`,
lue dans le MKV), sinon la touche « chapitre suivant » de Kodi.
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import chapter_data
import ui_common as ui
import upnext_data

XML_FILE = "script-arrmada-skip.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
CARD = 100
BTN_SKIP = 301
TICK = 0.25


def _seconds(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class SkipButton(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._params = kwargs.get("params") or {}
        self._closed = threading.Event()
        self.skip = False

    def onInit(self):
        self.setProperty("label", self._params.get("label") or "Passer l'intro")
        self.setProperty("bar", "bar-100")
        threading.Thread(target=self._timer, name="arrmada-skip", daemon=True).start()

    def _timer(self) -> None:
        """Disparaît au bout de 10 s, à la fin du chapitre ou à l'arrêt."""
        monitor, player = xbmc.Monitor(), xbmc.Player()
        until = _seconds(self._params.get("until"))
        chapter = _seconds(self._params.get("chapter"))
        left = float(chapter_data.DISPLAY_SECONDS)
        while left > 0 and not self._closed.is_set() and not ui.SHUTDOWN.is_set():
            if monitor.waitForAbort(TICK):
                break
            left -= TICK
            try:
                if not player.isPlayingVideo():
                    break
                if until and player.getTime() >= until:
                    break  # chapitre fini : plus rien à passer
            except RuntimeError:
                break
            # Sans liste de chapitres (pas un MKV) : Player.Chapter, « 01 » ou « 1 »
            if not until and _seconds(xbmc.getInfoLabel("Player.Chapter")) != chapter:
                break
            self.setProperty("bar", upnext_data.bar(left, chapter_data.DISPLAY_SECONDS))
        self.close_button()

    def close_button(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            self.close()

    def onClick(self, controlId):
        if controlId == BTN_SKIP:
            self.skip = True
            self.close_button()

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_button()


def show(params: dict) -> None:
    """Affiche le bouton (bloque jusqu'à sa disparition), puis saute si demandé."""
    home = xbmcgui.Window(10000)
    if home.getProperty(chapter_data.POPUP_PROP) == "1":
        return
    home.setProperty(chapter_data.POPUP_PROP, "1")
    window = SkipButton(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", params=params)
    skip = False
    try:
        window.doModal()
        skip = window.skip
    finally:
        window._closed.set()
        home.clearProperty(chapter_data.POPUP_PROP)
        del window
    if not skip:
        return
    target = _seconds(params.get("to"))
    if target:
        # Saut à l'heure exacte du chapitre suivant (lue dans le fichier)
        whole = int(target)
        ui.jsonrpc(
            "Player.Seek",
            {"playerid": 1, "value": {"time": {
                "hours": whole // 3600, "minutes": whole % 3600 // 60,
                "seconds": whole % 60, "milliseconds": int((target - whole) * 1000)}}},
        )  # fmt: skip
    else:
        # Attendre la fin de l'animation de fermeture : sinon l'action irait au
        # bouton, pas au lecteur (même piège que le panneau, vu sur le banc).
        xbmc.Monitor().waitForAbort(0.6)
        xbmc.executebuiltin("Action(chapterorbigstepforward)")
    where = f"{target:.0f} s" if target else "chapitre suivant"
    ui.log("Passer l'intro", f"saut après le chapitre {params.get('chapter')} → {where}")

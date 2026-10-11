# -*- coding: utf-8 -*-
"""Pop-up « Personne détectée » par-dessus le film (caméras Eufy).

Mise en page : resources/skins/Default/1080i/script-arrmada-camera.xml.
Ouverte par le service (RunPlugin …?action=camera) quand une alerte arrive
pendant une lecture vidéo : la photo de la caméra en bas à droite, 15 s.
La lecture continue dessous ; toute touche de la télécommande ferme la
pop-up (la première pression sert à la fermer, pas à piloter le film).
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import camera_data
import ui_common as ui

XML_FILE = "script-arrmada-camera.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
CARD = 100
PHOTO = 110


class CameraPopup(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._texts = kwargs.get("texts") or {}
        self._image = kwargs.get("image") or ""
        self._closed = threading.Event()

    def onInit(self):
        for key, value in self._texts.items():
            self.setProperty(key, value)
        self.setProperty("image", self._image)
        threading.Thread(target=self._timer, name="arrmada-camera", daemon=True).start()

    def _timer(self) -> None:
        monitor = xbmc.Monitor()
        deadline = camera_data.DISPLAY_SECONDS
        while deadline > 0 and not self._closed.is_set() and not ui.SHUTDOWN.is_set():
            if monitor.waitForAbort(0.5):
                break
            deadline -= 0.5
        self.close_popup()

    def close_popup(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            self.close()

    def onAction(self, action):
        self.close_popup()  # toute touche ferme la pop-up


def show(params: dict) -> None:
    """Affiche la pop-up (bloque jusqu'à sa fermeture) ; une seule à la fois."""
    home = xbmcgui.Window(10000)
    if home.getProperty(camera_data.POPUP_PROP) == "1":
        return
    home.setProperty(camera_data.POPUP_PROP, "1")
    texts = {
        "title": params.get("title") or "Détection",
        "subtitle": params.get("subtitle") or "",
    }
    window = CameraPopup(
        XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i",
        texts=texts, image=params.get("image") or "",
    )  # fmt: skip
    try:
        ui.log("Caméras", f"pop-up : {texts['title']} · {texts['subtitle']}")
        window.doModal()
    finally:
        window._closed.set()
        home.clearProperty(camera_data.POPUP_PROP)
        del window

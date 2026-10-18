# -*- coding: utf-8 -*-
"""Dialogue « Débloquer » de l'écran Téléchargements (ADR-005, lot 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-unstick.xml.

1. Le serveur établit un diagnostic (GET …/diagnose) : ce qui va, ce qui
   bloque, ce que le bouton va faire. La TV l'affiche tel quel.
2. Le bouton d'action demande « débloque » (POST …/unstick) : le serveur
   refait le diagnostic et applique le remède (import sans écrasement, ou
   autre release). Rien n'est effacé ni écrasé dans la médiathèque.
Réseau dans des fils d'arrière-plan (ADR-003), comme partout dans l'appli.
"""

from __future__ import annotations

import threading

import xbmcgui

import board_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-unstick.xml"

# Identifiants des boutons : DOIVENT correspondre au XML (vérifié par les tests).
BUTTONS = 960
BTN_ACTION = 961
BTN_CLOSE = 962


class UnstickWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._service = kwargs.get("service_type", "")
        self._download_id = kwargs.get("download_id", "")
        self._title = kwargs.get("title", "")
        self._initialized = False
        self._working = False
        self.result = None  # réponse du serveur après l'action (lue par l'appelant)

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        self.setProperty("title", self._title)
        self.setProperty("state", "loading")
        self.setProperty("close_label", "Annuler")
        threading.Thread(target=self._diagnose, name="arrmada-unstick", daemon=True).start()

    def _set(self, key: str, value: str) -> None:
        try:
            self.setProperty(key, value)
        except RuntimeError:
            pass  # dialogue fermé entre-temps

    def _diagnose(self) -> None:
        model = board_data.unstick_model(
            ArrMadaAPI.diagnose_download(self._service, self._download_id)
        )
        for index in range(1, 4):
            state, text, detail = (
                model["steps"][index - 1] if index <= len(model["steps"]) else ("", "", "")
            )
            self._set(f"s{index}_state", state)
            self._set(f"s{index}_text", text)
            self._set(f"s{index}_detail", detail)
        self._set("action", model["action"] if model["can_fix"] else "")
        self._set("close_label", "Annuler" if model["can_fix"] else "Fermer")
        self._set("state", "ready")
        ui.focus_when_visible(self, BTN_ACTION if model["can_fix"] else BTN_CLOSE)

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS and not self._working:
            self.close()

    def onClick(self, controlId):
        if controlId == BTN_CLOSE and not self._working:
            self.close()
        elif controlId == BTN_ACTION and not self._working:
            self._working = True
            self._set("state", "working")
            ui.run_in_background(self._fix)

    def _fix(self) -> None:
        self.result = ArrMadaAPI.unstick_download(self._service, self._download_id)
        ok = isinstance(self.result, dict) and self.result.get("status") == "ok"
        message = (self.result or {}).get("message") if isinstance(self.result, dict) else ""
        ui.notify(self._title or "Débloquer", message or ("C'est reparti" if ok else "Échec"), 6000)
        self._working = False
        try:
            self.close()
        except RuntimeError:
            pass


def open_unstick(service_type: str, download_id: str, title: str):
    """Ouvre le dialogue ; renvoie la réponse du serveur si l'action a été lancée."""
    window = UnstickWindow(
        XML_FILE,
        ui.ADDON.getAddonInfo("path"),
        "Default",
        "1080i",
        service_type=service_type,
        download_id=download_id,
        title=title,
    )
    try:
        window.doModal()
        return window.result
    finally:
        del window

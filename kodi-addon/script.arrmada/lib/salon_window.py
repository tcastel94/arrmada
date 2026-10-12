# -*- coding: utf-8 -*-
"""Écran « Salon » de l'appli Kodi ArrMada (phase 2, ADR-003 § 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-salon.xml.

  - Lecture en cours : affichée par Kodi lui-même (infolabels Player.*),
    pilotée par des commandes internes (PlayerControl, Seek) : aucun réseau.
  - Ampli Yamaha : état rafraîchi toutes les REFRESH_SECONDS par un fil
    d'arrière-plan ; chaque commande (volume, muet, marche, préréglage) part
    elle aussi en arrière-plan, puis l'état est relu.

Ouverture : bouton « Salon » de l'Accueil, ou depuis n'importe où (par
exemple une touche de la télécommande via Skin Shortcuts / keymap) :
    RunPlugin(plugin://script.arrmada/?action=salon)
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import pairing_data
import screens_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-salon.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
PLAYER_BUTTONS = 800
BTN_BACK30 = 801
BTN_PLAYPAUSE = 802
BTN_FWD30 = 803
BTN_STOP = 804
AMP_BUTTONS = 820
BTN_VOL_DOWN = 821
BTN_VOL_UP = 822
BTN_MUTE = 823
BTN_POWER = 824
PRESETS = 830

REFRESH_SECONDS = 3
VOLUME_STEP = 4  # pas de l'ampli par appui (Yamaha : 0,5 dB par unité)
ROOM_NAMES = {"salon": "Salon", "cinema": "Salle de cinéma"}  # pièces avec un ampli
NO_AMP_MESSAGE = "Pas d'ampli dans cette pièce : le son passe par la TV."

PLAYER_COMMANDS = {
    BTN_BACK30: "Seek(-30)",
    BTN_PLAYPAUSE: "PlayerControl(Play)",
    BTN_FWD30: "Seek(30)",
    BTN_STOP: "PlayerControl(Stop)",
}


class SalonWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._initialized = False
        self._stop = threading.Event()
        self._wake = threading.Event()  # relecture immédiate après une commande
        self._monitor = xbmc.Monitor()
        self._model: dict = {}
        self._presets: list[str] = []
        self._profiles: dict = {}

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        import device

        self.setProperty("room_name", pairing_data.ROOM_NAMES.get(ui.room(), ui.room()))
        self.setProperty("amp_power", "…")
        # Bureau (1.19.1) : commandes masquées d'emblée, sans attendre le serveur
        with_amp = device.has_amp()
        self._show_amp(with_amp)
        self.setProperty("amp_message", "Connexion à l'ampli…" if with_amp else NO_AMP_MESSAGE)
        playing = xbmc.getCondVisibility("Player.HasMedia")
        if playing or with_amp:  # sans ampli ni lecture : rien à sélectionner, Retour ferme
            ui.focus_when_visible(self, BTN_PLAYPAUSE if playing else BTN_VOL_UP)
        threading.Thread(target=self._loop, name="arrmada-salon", daemon=True).start()

    def _loop(self) -> None:
        while not self._stop.is_set() and not self._monitor.abortRequested():
            self._refresh()
            self._wake.wait(REFRESH_SECONDS)
            self._wake.clear()

    def close_window(self) -> None:
        self._stop.set()
        self._wake.set()
        self.close()

    # ── Ampli ───────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        state = ArrMadaAPI.yamaha_state()
        if not self._profiles:  # préréglages : lus une fois (ils changent rarement)
            profiles = ArrMadaAPI.yamaha_profiles()
            # Une réponse d'erreur n'est pas gardée : nouvel essai au prochain tour
            if isinstance(profiles, dict) and any(room in profiles for room in ROOM_NAMES):
                self._profiles = profiles
        if self._stop.is_set():
            return
        with_amp = not (isinstance(state, dict) and state.get("status") == "no_amp")
        if not with_amp:  # le serveur fait foi (TV déplacée au bureau depuis)
            model = screens_data.build_salon({}, {})
            message = NO_AMP_MESSAGE
        elif not isinstance(state, dict) or state.get("status") == "error":
            model = screens_data.build_salon({}, {})
            message = "Serveur ArrMada injoignable : ampli indisponible."
        else:
            model = screens_data.build_salon(state, self._profiles)
            message = ""
            if not model["configured"]:
                message = "Aucun ampli Yamaha configuré dans ArrMada (Réglages → Yamaha)."
            elif not model["online"]:
                message = "L'ampli ne répond pas (débranché ou hors réseau ?)."
        try:
            self._render(model, message)
            self._show_amp(with_amp)
        except RuntimeError:
            pass  # fenêtre fermée

    def _show_amp(self, with_amp: bool) -> None:
        """Pièce sans ampli : propriété « no_amp » (le XML masque les commandes)."""
        self.setProperty("no_amp", "" if with_amp else "1")
        if not with_amp:
            self.setProperty("amp_name", "Son de la TV")
        elif not self.getProperty("amp_name"):
            self.setProperty("amp_name", "Ampli Yamaha")

    def _render(self, model: dict, message: str) -> None:
        self._model = model
        self.setProperty("amp_message", message)
        self.setProperty("amp_configured", "1" if model["configured"] and model["online"] else "")
        self.setProperty("amp_name", model["name"])
        self.setProperty("amp_power", model["power"])
        self.setProperty("amp_on", "1" if model["is_on"] else "")
        self.setProperty("amp_volume", model["volume"])
        self.setProperty("amp_volume_bar", model["volume_bar"])
        self.setProperty("amp_db", model["db"])
        self.setProperty("amp_mute", "1" if model["mute"] else "")
        self.setProperty("amp_input", model["input"] or "—")
        self.setProperty("amp_program", model["program"] or "—")
        rooms = [p["room"] for p in model["presets"]]
        if rooms != self._presets:
            self._presets = rooms
            items = []
            for preset in model["presets"]:
                item = xbmcgui.ListItem(label=preset["name"], offscreen=True)
                item.setProperty("current", "1" if preset["room"] == ui.room() else "")
                items.append(item)
            presets = self.getControl(PRESETS)
            presets.reset()
            presets.addItems(items)

    def _command(self, action: str, value=None, done: str = "") -> None:
        """Commande ampli en arrière-plan, puis relecture immédiate de l'état."""
        result = ArrMadaAPI.yamaha_control(action, value)
        if result.get("status") == "error":
            ui.notify("Ampli", result.get("detail") or result.get("message") or "Commande refusée")
        elif done:
            ui.notify("Ampli", done, 1500)
        self._wake.set()

    def _apply_preset(self, room: str) -> None:
        result = ArrMadaAPI.yamaha_apply_preset(room, "movie")
        name = ROOM_NAMES.get(room, room)
        ok = result.get("status") != "error"
        ui.notify(
            "Ampli", f"Préréglage « {name} » appliqué" if ok else (result.get("message") or "Échec")
        )
        self._wake.set()

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_window()

    def onClick(self, controlId):
        if controlId in PLAYER_COMMANDS:
            xbmc.executebuiltin(PLAYER_COMMANDS[controlId])
        elif controlId == BTN_VOL_DOWN:
            ui.run_in_background(self._command, "volume_step", -VOLUME_STEP)
        elif controlId == BTN_VOL_UP:
            ui.run_in_background(self._command, "volume_step", VOLUME_STEP)
        elif controlId == BTN_MUTE:
            ui.run_in_background(self._command, "mute", not self._model.get("mute"))
        elif controlId == BTN_POWER:
            target = "standby" if self._model.get("is_on") else "on"
            ui.run_in_background(
                self._command,
                "power",
                target,
                "Mise en veille" if target == "standby" else "Allumage",
            )
        elif controlId == PRESETS:
            position = self.getControl(PRESETS).getSelectedPosition()
            if 0 <= position < len(self._presets):
                ui.run_in_background(self._apply_preset, self._presets[position])


def open_salon() -> None:
    window = SalonWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
    finally:
        window._stop.set()
        window._wake.set()
        del window

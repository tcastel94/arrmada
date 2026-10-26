# -*- coding: utf-8 -*-
"""Écran « Appairer cette TV » (phase 1, ADR-003 § 4).

Mise en page : resources/skins/Default/1080i/script-arrmada-pair.xml.

Tout le dialogue avec le serveur se fait dans un fil d'arrière-plan
(l'interface ne fige jamais) :
  1. demande d'un code (`pair_start`) → 6 cases + QR code + compte à rebours ;
  2. toutes les `interval` secondes, `pair_poll` ;
  3. code validé dans la web app → jeton enregistré, écran « TV appairée »,
     fermeture automatique.
Code expiré ou serveur injoignable : bouton « Nouveau code » / « Réessayer ».
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import device
import pairing_data
import server_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-pair.xml"

# Identifiant du seul bouton : DOIT correspondre au XML (vérifié par les tests).
BTN_RETRY = 901

DONE_SECONDS = 4  # durée d'affichage de « TV appairée » avant fermeture
EXPIRED = ("Ce code a expiré", "Demande un nouveau code et valide-le dans les 10 minutes.")


def _platform() -> str:
    """« Kodi 21.1 · Android » (voir ui_common.platform_name)."""
    return ui.platform_name()


class PairWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._initialized = False
        self._stop = threading.Event()
        self._monitor = xbmc.Monitor()
        self._worker: threading.Thread | None = None
        self.paired: dict = {}

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        self._start_worker()

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Dialogue avec le serveur (fil d'arrière-plan) ───────────────────────

    def _start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._run, name="arrmada-pair", daemon=True)
        self._worker.start()

    def _set_state(self, state: str, **props: str) -> None:
        for key, value in props.items():
            self.setProperty(key, value)
        self.setProperty("state", state)
        if state in ("expired", "error"):
            ui.focus_when_visible(self, BTN_RETRY)

    def _fail(self, state: str, title: str, message: str) -> None:
        ui.log("Appairage", f"{state} : {message}", xbmc.LOGWARNING)
        self._set_state(
            state,
            message_title=title,
            message=message,
            retry_label="Nouveau code" if state == "expired" else "Réessayer",
        )

    def _run(self) -> None:
        try:
            self._pair()
        except RuntimeError:
            pass  # fenêtre fermée pendant l'appairage

    def _pair(self) -> None:
        self._set_state("loading")
        started = ArrMadaAPI.pair_start(_platform())
        if self._stop.is_set():
            return
        if server_data.is_not_configured(started):
            # Adresse effacée entre-temps : pas de « injoignable » trompeur
            self._fail("error", server_data.NOT_CONFIGURED_TITLE, started["message"])
            return
        if started.get("status") == "error" or not started.get("device_code"):
            message = started.get("message") or "Réponse inattendue du serveur"
            if started.get("code") == 403:
                message += " (l'appairage n'est possible que depuis le réseau local)."
            self._fail("error", "Serveur ArrMada injoignable", message)
            return

        code = started["user_code"]
        for index, char in enumerate(pairing_data.code_tiles(code), start=1):
            self.setProperty(f"code_{index}", char)
        expires_at = time.monotonic() + float(started.get("expires_in") or 600)
        self._set_state(
            "waiting",
            qr=ArrMadaAPI.absolute_url(started.get("qr_url") or ""),
            web_hint=pairing_data.web_hint(started.get("verification_url") or ""),
            countdown=pairing_data.fmt_countdown(expires_at - time.monotonic()),
        )
        ui.log("Appairage", f"code {pairing_data.format_code(code)} affiché")

        interval = max(2.0, float(started.get("interval") or 3))
        next_poll = time.monotonic() + interval
        while not self._stop.is_set() and not self._monitor.abortRequested():
            remaining = expires_at - time.monotonic()
            self.setProperty("countdown", pairing_data.fmt_countdown(remaining))
            if remaining <= 0:
                self._fail("expired", *EXPIRED)
                return
            if time.monotonic() >= next_poll:
                next_poll = time.monotonic() + interval
                response = ArrMadaAPI.pair_poll(started["device_code"])
                state, message = pairing_data.poll_outcome(response)
                if state == "ok":
                    self._done(response)
                    return
                if state == "expired":
                    self._fail("expired", *EXPIRED)
                    return
                if state == "error":
                    # Coupure passagère (Wi-Fi, redémarrage du serveur) : on
                    # réessaie au tour suivant, sans perdre le code affiché.
                    ui.log("Appairage", f"interrogation impossible : {message}", xbmc.LOGWARNING)
            self._stop.wait(1.0)  # le compte à rebours avance chaque seconde

    def _done(self, response: dict) -> None:
        info = response.get("device") or {}
        device.save(ArrMadaAPI.get_config()["url"], response["token"], info)
        self.paired = info
        self._set_state("done", summary=pairing_data.device_summary(info))
        ui.log("Appairage", f"TV appairée : {pairing_data.device_summary(info)}")
        self._stop.wait(DONE_SECONDS)
        if not self._stop.is_set():
            self.close_window()

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_window()

    def onClick(self, controlId):
        if controlId == BTN_RETRY:
            self._start_worker()


def open_pairing() -> dict:
    """Ouvre l'écran d'appairage ; renvoie l'appareil appairé ({} si annulé).

    Sans adresse de serveur (nouvelle installation), on commence par
    « Trouver le serveur ArrMada » : un code demandé à personne ne sert à rien.
    """
    import server_setup

    if not server_setup.ensure_configured():
        return {}
    window = PairWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
        return dict(window.paired)
    finally:
        window._stop.set()
        del window

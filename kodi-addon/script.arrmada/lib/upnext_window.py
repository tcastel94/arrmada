# -*- coding: utf-8 -*-
"""Encart « Épisode suivant » à la fin d'un épisode (ADR-004, phase 4.4).

Mise en page : resources/skins/Default/1080i/script-arrmada-upnext.xml.
Logique pure (moment d'ouverture, textes, compte à rebours) :
lib/upnext_data.py, testée en CI.

Deux moitiés, comme pour la pop-up des caméras :

  - `offer()` tourne dans le SERVICE (appelé par la boucle quand il reste
    20 s) : il trouve l'épisode suivant dans la file de Kodi (ou l'y ajoute)
    et ouvre l'encart par une invocation à part (RunPlugin), pour que la
    boucle du service ne reste jamais bloquée ;
  - `show()` tourne dans cette invocation : l'encart lui-même, qui suit la
    position du lecteur et se ferme seul à la fin de l'épisode.

L'encart ne met jamais la lecture en pause et n'empêche rien : Retour le
ferme, l'épisode suivant démarre à la fin comme d'habitude.
"""

from __future__ import annotations

import threading
import urllib.parse

import xbmc
import xbmcgui

import kodi_library
import ui_common as ui
import upnext_data
import watch_data

XML_FILE = "script-arrmada-upnext.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
CARD = 100
BUTTONS = 300
BTN_NOW = 301
BTN_CANCEL = 302

VIDEO_PLAYLIST = 1
TICK = 0.25  # s entre deux mises à jour du compte à rebours


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Épisode suivant", message, level)


def _video_player() -> tuple:
    """(n° du lecteur vidéo, n° de sa liste de lecture, position dans la liste)."""
    players = ui.jsonrpc("Player.GetActivePlayers", {})
    playerid = next((p.get("playerid") for p in players or [] if p.get("type") == "video"), None)
    if playerid is None:
        return None, -1, -1
    props = ui.jsonrpc(
        "Player.GetProperties", {"playerid": playerid, "properties": ["playlistid", "position"]}
    )
    return playerid, int(props.get("playlistid", -1)), int(props.get("position", -1))


def _playlist(playlistid: int) -> list:
    result = ui.jsonrpc(
        "Playlist.GetItems", {"playlistid": playlistid, "properties": upnext_data.PLAYLIST_PROPS}
    )
    return result.get("items") or []


# ─────────────────────────────────────────────────────────────────────────────
# Côté service : trouver l'épisode suivant et ouvrir l'encart
# ─────────────────────────────────────────────────────────────────────────────


def _queue_next(episodeid: int, playlistid: int):
    """Rien en file : ajoute l'épisode suivant de la série (comme « Lire la suite »)."""
    details = kodi_library.episode_details(episodeid)
    chain = watch_data.chain_after(
        kodi_library.show_episodes(details.get("tvshowid") or 0), episodeid, limit=1
    )
    if not chain:
        return False
    ui.jsonrpc("Playlist.Add", {"playlistid": playlistid, "item": [{"episodeid": chain[0]}]})
    _log(f"épisode {chain[0]} ajouté à la file après l'épisode {episodeid}")
    return True


def offer(episodeid: int) -> bool:
    """Ouvre l'encart si un épisode suit ; False sinon (dernier épisode, lecture hors liste)."""
    if xbmcgui.Window(10000).getProperty(upnext_data.POPUP_PROP) == "1":
        return False
    _, playlistid, position = _video_player()
    if playlistid != VIDEO_PLAYLIST or position < 0:
        # Vidéo lancée hors de la liste de lecture (lien direct, autre add-on) :
        # Kodi n'enchaînerait rien, l'encart promettrait un épisode qui ne vient pas.
        _log(f"lecture hors liste (liste {playlistid}) : pas d'encart", xbmc.LOGDEBUG)
        return False
    upcoming = upnext_data.next_in_playlist(_playlist(playlistid), position)
    if upcoming is None and _queue_next(episodeid, playlistid):
        upcoming = upnext_data.next_in_playlist(_playlist(playlistid), position)
    if upcoming is None:
        _log("dernier épisode de la série : pas d'encart")
        return False
    params = upnext_data.popup_params(upcoming)
    params["current"] = str(episodeid)  # « Lancer maintenant » le marque vu
    _log(f"encart : {params['show']} {params['line']}")
    xbmc.executebuiltin(f"RunPlugin(plugin://script.arrmada/?{urllib.parse.urlencode(params)})")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Côté encart
# ─────────────────────────────────────────────────────────────────────────────


def cancel_chain() -> int:
    """Retire ce qui suit l'épisode en cours : la lecture s'arrêtera à sa fin."""
    _, playlistid, position = _video_player()
    if playlistid < 0:
        return 0
    removed = 0
    for index in upnext_data.positions_to_remove(len(_playlist(playlistid)), position):
        if ui.jsonrpc("Playlist.Remove", {"playlistid": playlistid, "position": index}) == "OK":
            removed += 1
    return removed


class UpNextPopup(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._params = kwargs.get("params") or {}
        self._closed = threading.Event()
        self._player = xbmc.Player()
        self._file = ""
        self._threshold = 0.0

    def onInit(self):
        for key in ("show", "code", "title", "line", "thumb"):
            self.setProperty(key, self._params.get(key, ""))
        try:
            self._file = self._player.getPlayingFile()
            self._threshold = max(1.0, self._player.getTotalTime() - self._player.getTime())
        except RuntimeError:
            self.close_popup()  # la lecture vient de s'arrêter
            return
        self._update()
        ui.focus_when_visible(self, BTN_NOW)
        threading.Thread(target=self._timer, name="arrmada-upnext", daemon=True).start()

    def _remaining(self):
        """Secondes avant la fin de l'épisode ; None s'il n'est plus à l'écran."""
        try:
            if not self._player.isPlayingVideo() or self._player.getPlayingFile() != self._file:
                return None
            return self._player.getTotalTime() - self._player.getTime()
        except RuntimeError:
            return None

    def _update(self) -> bool:
        remaining = self._remaining()
        if remaining is None or remaining <= 0.3:
            return False
        self.setProperty("countdown", upnext_data.countdown_label(remaining))
        self.setProperty("bar", upnext_data.bar(remaining, self._threshold))
        return True

    def _timer(self) -> None:
        monitor = xbmc.Monitor()
        while not self._closed.is_set() and not ui.SHUTDOWN.is_set():
            if monitor.waitForAbort(TICK) or not self._update():
                break
        self.close_popup()  # épisode terminé (le suivant démarre) ou lecture arrêtée

    def close_popup(self) -> None:
        if not self._closed.is_set():
            self._closed.set()
            self.close()

    def onClick(self, controlId):
        if controlId == BTN_NOW:
            self.close_popup()
            current = int(self._params.get("current") or 0)
            if current:
                # Passer au suivant = épisode fini, même si le générique dépasse
                # les 10 % de fin à partir desquels Kodi le compte « vu » tout seul.
                kodi_library.set_watched("episode", current, True)
            _log("lancer maintenant")
            self._player.playnext()
        elif controlId == BTN_CANCEL:
            self.close_popup()
            removed = cancel_chain()
            _log(f"annulé : {removed} épisode(s) retiré(s) de la file")
            ui.notify("Épisode suivant annulé", "La lecture s'arrêtera à la fin de cet épisode")

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_popup()  # l'encart disparaît, la suite démarre quand même


def show(params: dict) -> None:
    """Affiche l'encart (bloque jusqu'à sa fermeture) ; un seul à la fois."""
    home = xbmcgui.Window(10000)
    if home.getProperty(upnext_data.POPUP_PROP) == "1":
        return
    home.setProperty(upnext_data.POPUP_PROP, "1")
    window = UpNextPopup(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", params=params)
    try:
        window.doModal()
    finally:
        window._closed.set()
        home.clearProperty(upnext_data.POPUP_PROP)
        del window

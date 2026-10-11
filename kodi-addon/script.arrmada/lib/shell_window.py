# -*- coding: utf-8 -*-
"""Accueil média ArrMada : la « coquille » qui remplace l'accueil de Kodi.

ADR-004, phase 4.2. Mise en page : resources/skins/Default/1080i/script-arrmada-shell.xml.

À l'écran :
  - en haut, le menu principal : Accueil, Films, Séries, Découvrir,
    Rechercher, Téléchargements, Salon, Tableau de bord (l'ancien Accueil),
    Réglages ;
  - l'en-tête (« héros ») : fond, titre, état et résumé de l'élément
    sélectionné ;
  - les rangées : Reprendre (médiathèque Kodi de CET appareil), Ajouts
    récents, Pour toi, Bientôt (caches du service, donc instantanées).

Retour ne fait pas tomber dans l'accueil de Kodi : un menu « Quitter ? »
propose de rester, de passer à l'interface Kodi (jusqu'au prochain
démarrage), d'ouvrir les réglages de Kodi ou de quitter Kodi.

Le service rouvre cet écran tout seul quand l'accueil de Kodi s'affiche
(démarrage, retour d'un add-on) : propriété « arrmada.shell » posée tant
qu'il est ouvert (service.py, shell_data.should_open_shell).
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import listing
import navigation
import shell_data
import ui_common as ui
import watch_data

XML_FILE = "script-arrmada-shell.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
MENU = 400  # groupe des boutons du menu principal
MENU_BUTTONS = (401, 402, 403, 404, 405, 406, 407, 408, 409)  # ordre de shell_data.MENU
ROW_GROUPS = 500  # rangées (liste verticale qui défile)
ROW_LISTS = (610, 620, 630, 640)  # ordre de shell_data.ROWS

REFRESH_MINUTES = 2  # relecture des caches tant que l'écran est ouvert
SHELL_PROP = shell_data.SHELL_PROP
SHELL_OFF = shell_data.SHELL_OFF

ROW_BY_LIST = {list_id: key for list_id, (key, _) in zip(ROW_LISTS, shell_data.ROWS)}
LIST_BY_ROW = {key: list_id for list_id, key in ROW_BY_LIST.items()}
MENU_BY_BUTTON = {button: key for button, (key, _) in zip(MENU_BUTTONS, shell_data.MENU)}


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Coquille", message, level)


class ShellWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._rows: dict = {key: [] for key, _ in shell_data.ROWS}
        self._ids: dict = {key: [] for key, _ in shell_data.ROWS}
        self._initialized = False
        self._stop = threading.Event()
        self._busy = threading.Lock()
        self._opened_at = time.perf_counter()

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        home = xbmcgui.Window(10000)
        home.setProperty(SHELL_PROP, "1")
        home.clearProperty(SHELL_OFF)  # revenu dans ArrMada : le retour automatique reprend
        if self._initialized:
            # Retour d'un écran ou d'une lecture : « Reprendre » a pu changer.
            ui.run_in_background(self._load)
            return
        self._initialized = True
        self.setProperty("version", ui.ADDON.getAddonInfo("version"))
        _log(f"ouverture en {ui.ms_since(self._opened_at)} ms")
        threading.Thread(target=self._loop, name="arrmada-shell", daemon=True).start()

    def close_window(self) -> None:
        self._stop.set()
        xbmcgui.Window(10000).clearProperty(SHELL_PROP)
        self.close()

    def _loop(self) -> None:
        """Fil d'arrière-plan : remplit les rangées, puis les relit de temps en temps."""
        monitor = xbmc.Monitor()
        while not self._stop.is_set() and not monitor.abortRequested():
            self._load()
            if self._stop.wait(REFRESH_MINUTES * 60):
                break

    # ── Rangées ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            started = time.perf_counter()
            rows = shell_data.limit_rows(self._fetch_rows())
            if self._stop.is_set():
                return
            try:
                self._render(rows)
            except RuntimeError:
                return  # fenêtre fermée pendant le chargement
            counts = ", ".join(f"{key} {len(rows[key])}" for key, _ in shell_data.ROWS)
            _log(f"rangées en {ui.ms_since(started)} ms : {counts}")
        finally:
            self._busy.release()

    @staticmethod
    def _fetch_rows() -> dict:
        """Médiathèque Kodi (Reprendre) + caches du service (les autres rangées)."""
        import kodi_library

        rows: dict = {}
        try:
            rows["continue"] = watch_data.continue_entries(kodi_library.continue_watching())
        except Exception as exc:  # médiathèque illisible : les autres rangées s'affichent
            _log(f"« Reprendre » indisponible : {exc}", xbmc.LOGWARNING)
        recent = listing.read_feed("recent")
        rows["recent"] = navigation._with_kodi_state(navigation._entries("recent", recent))
        rows["foryou"] = navigation._entries("foryou", listing.read_feed("foryou"), sub="foryou")
        rows["upcoming"] = navigation._entries("upcoming", listing.read_feed("upcoming"))
        return rows

    def _render(self, rows: dict) -> None:
        for key, _ in shell_data.ROWS:
            entries = rows[key]
            ids = [str(entry.get("action")) for entry in entries]
            self._rows[key] = entries
            if ids == self._ids[key]:
                continue  # rien de neuf : on ne fait pas sauter la sélection
            self._ids[key] = ids
            control = self.getControl(LIST_BY_ROW[key])
            position = control.getSelectedPosition()
            items = []
            for index, entry in enumerate(entries):
                item = listing.make_listitem(entry, navigation.PLUGIN_BASE)
                item.setProperty("index", str(index))
                item.setProperty("status", str((entry.get("props") or {}).get("status") or ""))
                items.append(item)
            control.reset()
            control.addItems(items)
            if 0 <= position < len(items):
                control.selectItem(position)
        self.setProperty("empty", "" if shell_data.first_row(rows) else "1")
        self._ensure_focus(rows)
        self._update_hero()

    def _ensure_focus(self, rows: dict) -> None:
        """À l'arrivée : focus sur la première rangée non vide (sinon le menu)."""
        try:
            focused = self.getFocusId()
        except RuntimeError:
            focused = 0
        if focused in ROW_LISTS or focused in MENU_BUTTONS:
            return
        first = shell_data.first_row(rows)
        ui.focus_when_visible(self, LIST_BY_ROW[first] if first else MENU_BUTTONS[0])

    # ── En-tête (élément sélectionné) ──────────────────────────────────────

    def _selected(self, list_id: int | None = None) -> dict | None:
        try:
            list_id = list_id or self.getFocusId()
        except RuntimeError:
            return None
        key = ROW_BY_LIST.get(list_id)
        if not key:
            return None
        item = self.getControl(list_id).getSelectedItem()
        if not item or not item.getProperty("index"):
            return None
        index = int(item.getProperty("index"))
        entries = self._rows.get(key) or []
        return entries[index] if 0 <= index < len(entries) else None

    def _update_hero(self) -> None:
        entry = self._selected()
        if entry is None:
            return  # focus sur le menu : l'en-tête garde le dernier titre
        for key, value in shell_data.hero(entry).items():
            self.setProperty(f"hero_{key}", value)

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self._quit_menu()
            return
        try:
            focus = self.getFocusId()
        except RuntimeError:
            return
        if focus not in ROW_LISTS:
            return
        if action_id in ui.MENU_ACTIONS:
            entry = self._selected(focus)
            if entry and navigation.entry_menu(entry):
                ui.run_in_background(self._load)
        elif action_id in ui.PLAY_ACTIONS:
            entry = self._selected(focus)
            if entry:
                self._play(entry)
        else:
            self._update_hero()

    def onFocus(self, controlId):
        if controlId in ROW_LISTS:
            self._update_hero()

    def onClick(self, controlId):
        if controlId in ROW_LISTS:
            entry = self._selected(controlId)
            if entry:
                navigation.open_entry(entry)
        elif controlId in MENU_BY_BUTTON:
            self._open_menu(MENU_BY_BUTTON[controlId])

    @staticmethod
    def _play(entry: dict) -> None:
        """Touche Lecture : lire directement (Reprendre, ou titre présent dans Kodi)."""
        action = entry.get("action") or {}
        if action.get("action") == "resume_play":
            navigation.resume_play(action, wait=False)
        elif "play" in (entry.get("context") or []):
            navigation.context_action(dict(action, op="play"), wait=False)
        else:
            navigation.open_entry(entry)

    def _open_menu(self, key: str) -> None:
        if key == "home":
            first = shell_data.first_row(self._rows)
            ui.focus_when_visible(self, LIST_BY_ROW[first] if first else MENU_BUTTONS[0])
        elif key in ("movies", "series", "discover"):
            import grid_window

            grid_window.open_grid({"movies": "movie", "series": "series"}.get(key, key))
        elif key == "search":
            ui.open_search()
        elif key == "queue":
            import downloads_window

            downloads_window.open_downloads()
        elif key == "salon":
            import salon_window

            salon_window.open_salon()
        elif key == "board":
            import home_window

            home_window.open_home()
        elif key == "settings":
            ui.ADDON.openSettings()

    def _quit_menu(self) -> None:
        """Retour : jamais d'accueil Kodi par surprise, toujours une porte de sortie."""
        index = xbmcgui.Dialog().contextmenu([label for _, label in shell_data.QUIT_CHOICES])
        choice = shell_data.QUIT_CHOICES[index][0] if index >= 0 else "stay"
        if choice == "kodi":
            xbmcgui.Window(10000).setProperty(SHELL_OFF, "1")
            _log("interface Kodi choisie : retour automatique suspendu jusqu'au redémarrage")
            self.close_window()
        elif choice == "kodi_settings":
            xbmc.executebuiltin("ActivateWindow(Settings)")
        elif choice == "quit":
            self.close_window()
            xbmc.executebuiltin("Quit")


def open_shell() -> None:
    """Ouvre l'accueil média et bloque jusqu'à sa fermeture."""
    home = xbmcgui.Window(10000)
    if home.getProperty(SHELL_PROP) == "1":
        _log("déjà ouvert : rien à faire")
        return
    window = ShellWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
    finally:
        window._stop.set()
        home.clearProperty(SHELL_PROP)
        del window

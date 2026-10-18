# -*- coding: utf-8 -*-
"""Écran « Applis & sources » d'ArrMada (ADR-004, phase 4.3).

Mise en page : resources/skins/Default/1080i/script-arrmada-apps.xml.

Remplace les écrans Add-ons, TV et Vidéos → Fichiers de SiLVO :
  - onglets Vidéo (YouTube, IPTV en add-on…), TV en direct (chaînes et
    programme en cours), Musique, Dossiers (partages du NAS : vidéos perso),
    Favoris (ceux de Kodi), Applis Android (Shield) ;
  - OK sur un add-on ou un dossier : son contenu s'affiche ICI, en liste avec
    un aperçu ; Retour remonte d'un niveau, comme `cd ..` ;
  - OK sur une vidéo : « Reprendre à … / Depuis le début » puis lecture par
    Kodi ; sur une chaîne : la TV en direct ;
  - appui long : « Ouvrir dans Kodi », issue de secours toujours présente
    pour un add-on qui a besoin de l'interface de Kodi.

Règle d'or de l'ADR-003 : tout ce qui interroge Kodi (un add-on peut mettre
plusieurs secondes à répondre) passe par un fil d'arrière-plan.
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import apps_data
import kodi_sources
import ui_common as ui

XML_FILE = "script-arrmada-apps.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
TABS = 200
TILES = 300
LIST = 400

TITLE = "Applis & sources"


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Applis", message, level)


class AppsWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._tabs = kwargs.get("tabs") or list(apps_data.TABS)
        self._tab = apps_data.tab_index(self._tabs, kwargs.get("tab") or "video")
        # Ouvert directement sur une appli (rangée « Tes applis » de l'accueil) :
        # Retour à sa racine ferme l'écran au lieu d'afficher les onglets.
        self._start = kwargs.get("start")
        self._stack: list = []  # dossiers ouverts : {"app", "entries", "position"}
        self._entries: list = []  # ce qui est affiché
        self._tab_cache: dict = {}  # onglet → éléments (Retour instantané)
        self._tab_positions: dict = {}
        self._generation = 0  # chaque chargement invalide les réponses en retard
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._initialized = False

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            # Retour d'une lecture ou de Kodi : reprise et programmes ont changé
            self._reload_current()
            return
        self._initialized = True
        tabs = self.getControl(TABS)
        tabs.reset()
        tabs.addItems([xbmcgui.ListItem(label=label, offscreen=True) for _, label in self._tabs])
        tabs.selectItem(self._tab)
        if self._start:
            self._enter(self._start)
        else:
            ui.focus_when_visible(self, TABS)
            self._show_tab()

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Chargement ─────────────────────────────────────────────────────────

    def _tab_key(self) -> str:
        return self._tabs[self._tab][0] if self._tabs else "video"

    def _bump(self) -> int:
        """Nouvel affichage : les réponses encore en route pour l'ancien sont ignorées."""
        with self._lock:
            self._generation += 1
            return self._generation

    def _begin(self) -> int:
        """Nouveau chargement : écran vidé, « Chargement… », réponses en retard ignorées."""
        generation = self._bump()
        self._entries = []
        for control in (TILES, LIST):
            self.getControl(control).reset()
        self.setProperty("message", "")
        self.setProperty("status", "")
        self.setProperty("loading", "1")
        return generation

    def _current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation and not self._stop.is_set()

    def _show_tab(self, refresh: bool = False) -> None:
        """Racine d'un onglet (tuiles ou chaînes), depuis le cache si possible."""
        key = self._tab_key()
        self._stack = []
        self.setProperty("browsing", "")
        self.setProperty("title", TITLE)
        self.setProperty("crumb", "")
        layout = apps_data.layout_for(key, browsing=False)
        if key in self._tab_cache and not refresh:
            self._bump()
            entries, message = self._tab_cache[key]
            self._render(entries, layout, self._tab_positions.get(key, 0), message, key)
            return
        generation = self._begin()

        def _load() -> None:
            try:
                entries, error = kodi_sources.tab_entries(key)
            except Exception as exc:  # Kodi illisible : on le dit, sans planter l'écran
                entries, error = [], str(exc)
            if not self._current(generation):
                return
            self._tab_cache[key] = (entries, error)
            self._render(entries, layout, self._tab_positions.get(key, 0), error, key)

        threading.Thread(target=_load, name="arrmada-apps", daemon=True).start()

    def _enter(self, app: dict) -> None:
        """Ouvre un dossier (add-on, partage du NAS…) dans l'écran."""
        self._remember_position()
        self._stack.append({"app": app, "entries": None, "position": 0})
        self._show_frame(load=True)

    def _show_frame(self, load: bool = False) -> None:
        frame = self._stack[-1]
        app = frame["app"]
        self.setProperty("browsing", "1")
        self.setProperty("title", app["label"])
        self.setProperty("crumb", apps_data.breadcrumb([f["app"]["label"] for f in self._stack]))
        if frame["entries"] is not None and not load:
            self._bump()
            self._render(frame["entries"], "list", frame["position"], "", "browse")
            return
        generation = self._begin()

        def _load() -> None:
            try:
                entries, error = kodi_sources.directory(app["path"], app.get("media") or "video")
            except Exception as exc:
                entries, error = [], str(exc)
            if not self._current(generation):
                return
            if error and not entries:
                self._open_failed(app, error)
                return
            frame["entries"] = entries
            self._render(entries, "list", frame["position"], "", "browse")

        threading.Thread(target=_load, name="arrmada-apps", daemon=True).start()

    def _open_failed(self, app: dict, error: str) -> None:
        """Dossier illisible ici : on reste où l'on était, Kodi reste une issue."""
        ui.notify(app["label"], "Ne s'ouvre pas ici. Appui long : Ouvrir dans Kodi", 5000)
        _log(f"{app['path']} illisible : {error}", xbmc.LOGWARNING)
        self._stack.pop()
        try:
            if self._stack:
                self._show_frame()
            elif self._start:
                self.close_window()
            else:
                self._show_tab()
        except RuntimeError:
            return  # fenêtre fermée entre-temps

    def _reload_current(self) -> None:
        if self._stack:
            self._remember_position()
            self._show_frame(load=True)
        else:
            self._remember_position()
            self._show_tab(refresh=True)

    def _remember_position(self) -> None:
        control = self._visible_control()
        try:
            position = self.getControl(control).getSelectedPosition()
        except RuntimeError:
            return
        if position < 0:
            return
        if self._stack:
            self._stack[-1]["position"] = position
        else:
            self._tab_positions[self._tab_key()] = position

    # ── Affichage ──────────────────────────────────────────────────────────

    def _focus_id(self) -> int:
        try:
            return self.getFocusId()
        except RuntimeError:  # aucun contrôle n'a le focus
            return 0

    def _visible_control(self) -> int:
        return TILES if self.getProperty("layout") == "tiles" else LIST

    def _render(self, entries: list, layout: str, position: int, error: str, key: str) -> None:
        try:
            self._entries = entries
            self.setProperty("layout", layout)
            control_id = TILES if layout == "tiles" else LIST
            other = LIST if control_id == TILES else TILES
            self.getControl(other).reset()
            control = self.getControl(control_id)
            control.reset()
            control.addItems([self._item(app, i) for i, app in enumerate(entries)])
            if 0 < position < len(entries):
                control.selectItem(position)
            self.setProperty("loading", "")
            self.setProperty("status", apps_data.count_label(len(entries)))
            self.setProperty("message", "" if entries else error or apps_data.EMPTY.get(key, ""))
        except RuntimeError:
            return  # fenêtre fermée pendant le chargement
        # Piège Kodi (constaté sur le banc) : la liste qui avait le focus est
        # vidée pendant le chargement ; Kodi se rabat sur le contrôle par
        # défaut (les onglets, masqués dans un dossier) et plus rien n'a le
        # focus, alors que getFocusId() répond encore 400. On le repose donc
        # toujours sur ce qui vient d'être rempli.
        if entries:
            ui.focus_when_visible(self, control_id)
        elif not self._stack and self._focus_id() != TABS:
            ui.focus_when_visible(self, TABS)

    @staticmethod
    def _item(app: dict, index: int) -> xbmcgui.ListItem:
        item = xbmcgui.ListItem(label=app["label"], label2=app.get("label2") or "", offscreen=True)
        art = dict(app.get("art") or {})
        if art.get("thumb"):
            art.setdefault("icon", art["thumb"])
        item.setArt({key: value for key, value in art.items() if value})
        item.setProperty("index", str(index))
        item.setProperty("plot", app.get("plot") or "")
        item.setProperty("bar", app.get("bar") or "")
        item.setProperty("number", app.get("number") or "")
        return item

    def _selected(self) -> dict | None:
        try:
            item = self.getControl(self._visible_control()).getSelectedItem()
        except RuntimeError:
            return None
        if not item or not item.getProperty("index"):
            return None
        index = int(item.getProperty("index"))
        return self._entries[index] if 0 <= index < len(self._entries) else None

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self._back()
            return
        focus = self._focus_id()
        if focus not in (TILES, LIST):
            return
        if action_id in ui.MENU_ACTIONS:
            app = self._selected()
            if app:
                self._long_press(app)
        elif action_id in ui.PLAY_ACTIONS:
            app = self._selected()
            if app and app["target"] in ("play", "channel"):
                self._activate(app)

    def onClick(self, controlId):
        if controlId == TABS:
            index = self.getControl(TABS).getSelectedPosition()
            if 0 <= index < len(self._tabs):
                self._remember_position()
                self._tab = index
                self._show_tab()
        elif controlId in (TILES, LIST):
            app = self._selected()
            if app:
                self._activate(app)

    def _back(self) -> None:
        """Retour : dossier parent, puis racine de l'onglet, puis fermeture."""
        if not self._stack:
            self.close_window()
            return
        self._stack.pop()
        if self._stack:
            self._show_frame()
        elif self._start:
            self.close_window()
        else:
            self._show_tab()

    def _activate(self, app: dict) -> None:
        target = app.get("target")
        if target == "browse":
            self._enter(app)
        elif target == "tab":
            index = apps_data.tab_index(self._tabs, app.get("tab") or "")
            if self._tabs[index][0] == app.get("tab"):
                self._remember_position()
                self._tab = index
                self.getControl(TABS).selectItem(index)
                self._show_tab()
        else:
            run(app)

    def _long_press(self, app: dict) -> None:
        ops = apps_data.context_ops(app)
        if not ops:
            return
        index = xbmcgui.Dialog().contextmenu([label for _, label in ops])
        if index < 0:
            return
        op = ops[index][0]
        if op == "from_start":
            play(app, resume=False)
            return
        command = apps_data.op_command(op, app)
        if command:
            _log(f"appui long « {op} » : {command}")
            xbmc.executebuiltin(command)


# ─────────────────────────────────────────────────────────────────────────────
# Ouverture et actions (aussi utilisées par l'accueil média et le plugin)
# ─────────────────────────────────────────────────────────────────────────────


def play(app: dict, resume=None) -> bool:
    """Lit une vidéo de dossier ou d'add-on ; propose de reprendre si elle a été commencée."""
    if resume is None:
        import kodi_library  # import local : évite de charger la médiathèque pour rien

        resume = kodi_library.ask_resume(int(app.get("resume") or 0))
        if resume is None:
            return False
    return kodi_sources.play_file(app["path"], resume=bool(resume))


def run(app: dict) -> None:
    """OK sur une appli qui ne s'ouvre pas dans l'écran : lecture, chaîne, commande Kodi."""
    target = app.get("target")
    if target == "play":
        play(app)
    elif target == "channel":
        kodi_sources.play_channel(int(app.get("id") or 0))
    elif target == "run" and app.get("command"):
        _log(f"commande Kodi : {app['command']}")
        xbmc.executebuiltin(app["command"])


def open_apps(tab: str = "video", start: dict | None = None) -> None:
    """Ouvre l'écran (sur un onglet, ou directement dans une appli) ; bloque jusqu'à Retour."""
    tabs = apps_data.visible_tabs(kodi_sources.has_pvr(), kodi_sources.is_android())
    window = AppsWindow(
        XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", tabs=tabs, tab=tab, start=start
    )
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window


def activate(action: dict) -> None:
    """Élément « app » d'une rangée de l'accueil ou d'une liste du plugin."""
    app = apps_data.app_from_action(action)
    target = app["target"]
    if target == "browse" and app["path"]:
        open_apps(tab="music" if app["media"] == "music" else "video", start=app)
    elif target == "tab":
        open_apps(tab=app["tab"] or "video")
    else:
        run(app)

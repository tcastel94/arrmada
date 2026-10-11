# -*- coding: utf-8 -*-
"""Grille ArrMada : Films, Séries, Découvrir, Recherche (ADR-004, phases 4.2-4.3).

Mise en page : resources/skins/Default/1080i/script-arrmada-grid.xml.

Remplace les vues de SiLVO pour parcourir la bibliothèque : un mur
d'affiches avec, en haut, les onglets de la bibliothèque (Tous de A à Z,
Ajoutés récemment, Par genre, En 4K, Pas encore disponibles) ou de Découvrir
(Pour toi, Films tendance, Séries tendance).

- Le serveur trie et découpe la bibliothèque en pages de 100 : la grille
  charge la page suivante toute seule, deux lignes avant d'arriver au bout
  (shell_data.need_more). Comme un `less` qui lit le fichier au fil de l'eau.
- Chaque affiche porte l'état de la médiathèque Kodi de CET appareil :
  pastille « Vu », barre de reprise (watch_data.annotate).
- OK : la Fiche (film), l'écran Série (série présente dans Kodi), ou la
  fenêtre « Demander » (titre de Découvrir). Appui long : Lire, Fiche,
  Meilleure version, Marquer comme vu / non vu.
- Recherche (4.3) : les résultats de Radarr / Sonarr s'affichent ici et non
  plus dans une liste de SiLVO ; onglets Tout / Films / Séries, et
  « Nouvelle recherche » qui rouvre le clavier.

Règle d'or de l'ADR-003 : les appels réseau passent par un fil
d'arrière-plan, l'écran ne fige jamais.
"""

from __future__ import annotations

import threading
import time

import xbmcgui

import catalog_data
import feeds
import home_data
import library_data
import listing
import navigation
import shell_data
import ui_common as ui
import watch_data
from api import ArrMadaAPI

XML_FILE = "script-arrmada-grid.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
TABS = 200
GRID = 300

NAV_ACTIONS = (
    xbmcgui.ACTION_MOVE_LEFT,
    xbmcgui.ACTION_MOVE_RIGHT,
    xbmcgui.ACTION_MOVE_UP,
    xbmcgui.ACTION_MOVE_DOWN,
    xbmcgui.ACTION_PAGE_UP,
    xbmcgui.ACTION_PAGE_DOWN,
)
TITLES = {"movie": "Films", "series": "Séries", "discover": "Découvrir", "search": "Recherche"}


def _tabs_for(source: str) -> list:
    """Onglets (clé, libellé) : vues de la bibliothèque, sous-flux de Découvrir, recherche."""
    if source == "discover":
        return list(shell_data.DISCOVER_TABS)
    if source == "search":
        return list(shell_data.SEARCH_TABS)
    return [(view.key, view.label) for view in library_data.views_for(source)]


class GridWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._source: str = kwargs.get("source") or "movie"
        self._tabs = _tabs_for(self._source)
        self._tab = 0
        self._genre = ""  # nom du genre côté serveur (vue « genre »)
        self._genre_label = ""
        self._entries: list = []
        self._page = self._pages = self._total = 0
        self._generation = 0  # chaque rechargement invalide les réponses en retard
        self._loading = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._initialized = False
        self._indexes = None  # (films, séries) de la médiathèque Kodi, lus une fois
        self._query: str = kwargs.get("query") or ""  # recherche (4.3)
        self._results = None  # réponse du serveur à la recherche, filtrée par onglet

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            return  # retour d'une fiche ou d'une lecture : la grille reste où elle était
        self._initialized = True
        self.setProperty("title", TITLES.get(self._source, "ArrMada"))
        tabs = self.getControl(TABS)
        tabs.reset()
        tabs.addItems([xbmcgui.ListItem(label=label, offscreen=True) for _, label in self._tabs])
        tabs.selectItem(self._tab)
        ui.focus_when_visible(self, TABS)
        self._reload()

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Chargement ─────────────────────────────────────────────────────────

    def _subtitle(self) -> str:
        if self._source == "search":
            return f"« {self._query} » · {self._tabs[self._tab][1]}"
        if self._genre:
            return self._genre_label
        return self._tabs[self._tab][1] if self._tabs else ""

    def _reload(self) -> None:
        """Repart de la page 1 (nouvel onglet, nouveau genre)."""
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._entries = []
            self._page = self._pages = self._total = 0
            self._loading = True
        self.getControl(GRID).reset()
        self.setProperty("subtitle", self._subtitle())
        self.setProperty("error", "")
        self.setProperty("status", shell_data.grid_status(0, 0, True))
        threading.Thread(
            target=self._load_page, args=(generation, 1), name="arrmada-grid", daemon=True
        ).start()

    def _load_more(self) -> None:
        with self._lock:
            if self._loading:
                return
            self._loading = True
            generation, page = self._generation, self._page + 1
        threading.Thread(
            target=self._load_page, args=(generation, page), name="arrmada-grid", daemon=True
        ).start()

    def _load_page(self, generation: int, page: int) -> None:
        started = time.perf_counter()
        try:
            entries, current, pages, total, error = self._fetch(page)
        except Exception as exc:  # serveur ou médiathèque illisible : on le dit
            entries, current, pages, total, error = [], page, page, 0, str(exc)
        with self._lock:
            if generation != self._generation or self._stop.is_set():
                return  # réponse d'un onglet quitté entre-temps
            first = len(self._entries)
            self._entries.extend(entries)
            self._page, self._pages, self._total = current, pages, total
            self._loading = False
            shown = len(self._entries)
        try:
            items = [self._item(entry, first + i) for i, entry in enumerate(entries)]
            grid = self.getControl(GRID)
            # Piège Kodi (ControlList.addItems → GUI_MSG_LABEL_BIND) : ajouter des
            # éléments réattache toute la liste et remet la sélection en haut.
            # On la remet où elle était (constaté sur le banc à la page 2).
            position = grid.getSelectedPosition() if page > 1 else -1
            grid.addItems(items)
            if position > 0:
                grid.selectItem(position)
            self.setProperty("error", error if not shown else "")
            self.setProperty("status", shell_data.grid_status(shown, total, False))
            if page == 1 and items and self.getFocusId() in (TABS, 0):
                self.setFocusId(GRID)
        except RuntimeError:
            return  # fenêtre fermée pendant le chargement
        ui.log(
            "Grille",
            f"{TITLES.get(self._source)} · {self._subtitle()} : page {current}/{pages}, "
            f"{len(entries)} titre(s) en {ui.ms_since(started)} ms",
        )

    def _fetch(self, page: int) -> tuple:
        """(entrées, page, nombre de pages, total, message d'erreur)."""
        key = self._tabs[self._tab][0]
        if self._source == "search":
            if self._results is None:
                self._results = ArrMadaAPI.lookup_media(self._query)
            entries = catalog_data.entries_lookup(self._results, key)
            if not entries:
                return [], 1, 1, 0, f"Aucun résultat pour « {self._query} »."
            # Pastilles « Vu » / reprise : seulement pour les titres déjà suivis
            followed = [e for e in entries if (e.get("action") or {}).get("action") == "detail"]
            watch_data.annotate(followed, *self._kodi_indexes())
            return entries, 1, 1, len(entries), ""
        if self._source == "discover":
            data = listing.read_feed("foryou")
            if data is None:
                return [], 1, 1, 0, navigation._empty_after_error()
            entries = navigation._entries("foryou", data, sub=key)
            return entries, 1, 1, len(entries), ""
        view = "genre" if self._genre else key
        payload = ArrMadaAPI.get_media(
            library_data.browse_query(self._source, view, self._genre, page)
        )
        if feeds.is_error(payload):
            described = home_data.describe_error(payload)
            return [], page, page, 0, f"{described['title']} : {described['action']}"
        entries = catalog_data.entries_media(payload.get("items") or [], missing=view == "missing")
        if view != "missing":
            entries = watch_data.annotate(entries, *self._kodi_indexes())
        current, pages, total = library_data.page_info(payload)
        return entries, current, pages, total, ""

    def _kodi_indexes(self, refresh: bool = False) -> tuple:
        if self._indexes is None or refresh:
            import kodi_library

            try:
                self._indexes = kodi_library.library_indexes()
            except Exception:  # médiathèque illisible : pas de pastilles, c'est tout
                self._indexes = ({}, {})
        return self._indexes

    @staticmethod
    def _item(entry: dict, index: int) -> xbmcgui.ListItem:
        item = listing.make_listitem(entry, navigation.PLUGIN_BASE)
        item.setProperty("index", str(index))
        # Titre suivi sans fichier : affiche atténuée, pas de « Lire »
        action = entry.get("action") or {}
        unavailable = action.get("action") == "detail" and "play" not in (
            entry.get("context") or []
        )
        item.setProperty("unavailable", "1" if unavailable else "")
        return item

    def _selected(self) -> dict | None:
        item = self.getControl(GRID).getSelectedItem()
        if not item or not item.getProperty("index"):
            return None
        index = int(item.getProperty("index"))
        return self._entries[index] if 0 <= index < len(self._entries) else None

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self.close_window()
            return
        try:
            focus = self.getFocusId()
        except RuntimeError:
            return
        if focus != GRID:
            return
        if action_id in NAV_ACTIONS:
            self._maybe_more()
        elif action_id in ui.MENU_ACTIONS:
            entry = self._selected()
            if entry and navigation.entry_menu(entry) in ("seen", "unseen"):
                self._refresh_selected(entry)
        elif action_id in ui.PLAY_ACTIONS:
            entry = self._selected()
            if entry and "play" in (entry.get("context") or []):
                navigation.context_action(dict(entry["action"], op="play"), wait=False)

    def onClick(self, controlId):
        if controlId == GRID:
            entry = self._selected()
            if entry:
                navigation.open_entry(entry)
        elif controlId == TABS:
            self._choose_tab(self.getControl(TABS).getSelectedPosition())

    def _maybe_more(self) -> None:
        selected = self.getControl(GRID).getSelectedPosition()
        if shell_data.need_more(selected, len(self._entries), self._page, self._pages):
            self._load_more()

    def _choose_tab(self, index: int) -> None:
        if not 0 <= index < len(self._tabs):
            return
        key = self._tabs[index][0]
        if key == "new":
            query = ui.ask_query()
            if not query:
                self.getControl(TABS).selectItem(self._tab)  # annulé : l'onglet ne bouge pas
                return
            self._query, self._results, index = query, None, 0
            self.getControl(TABS).selectItem(0)
        elif key == "genres":
            genre = self._pick_genre()
            if not genre:
                return
            self._genre, self._genre_label = genre
        else:
            self._genre = self._genre_label = ""
        self._tab = index
        self._reload()

    def _pick_genre(self):
        """Liste des genres (avec le nombre de titres) ; (nom, libellé) ou None."""
        facets = ArrMadaAPI.get_media_facets(self._source)
        if feeds.is_error(facets):
            ui.notify("Genres", home_data.describe_error(facets)["title"])
            return None
        choices = library_data.genre_choices(facets)
        if not choices:
            ui.notify("Genres", "Aucun genre connu")
            return None
        index = xbmcgui.Dialog().select("Par genre", [label for _, label in choices])
        if index < 0:
            return None
        name, label = choices[index]
        return name, f"Par genre · {label}"

    def _refresh_selected(self, entry: dict) -> None:
        """Après « Marquer comme vu / non vu » : pastille et menu à jour."""
        movies, shows = self._kodi_indexes(refresh=True)
        watch_data.annotate([entry], movies, shows)
        item = self.getControl(GRID).getSelectedItem()
        if item:
            props = entry.get("props") or {}
            item.setProperty("watched", props.get("watched", ""))
            item.setProperty("bar", props.get("bar", ""))
            item.setProperty("kodi_status", props.get("kodi_status", ""))


def open_grid(source: str, query: str = "") -> None:
    """Ouvre la grille (« movie », « series », « discover », « search ») ; bloque jusqu'à Retour."""
    window = GridWindow(
        XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", source=source, query=query
    )
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

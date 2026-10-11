# -*- coding: utf-8 -*-
"""Écran « Série » : saisons → épisodes (ADR-004, phase 4.1).

Mise en page : resources/skins/Default/1080i/script-arrmada-series.xml.

Remplace l'écran Vidéos de SiLVO pour les séries : on choisit la saison,
puis l'épisode, on voit ce qui est déjà vu et où on en est. Les données
viennent de la médiathèque Kodi de CET appareil (lib/kodi_library.py), la
mise en forme de lib/watch_data.py (testée en CI).

Ouverture sans jamais figer l'interface (règle d'or de l'ADR-003) :
  1. ce que l'écran appelant connaît (titre, affiche, fanart) s'affiche tout
     de suite ;
  2. un fil d'arrière-plan lit la série et ses épisodes dans Kodi, puis
     remplit l'écran, saison et épisode « à suivre » déjà sélectionnés ;
  3. au retour d'une lecture, l'écran se remet à jour (vu, reprise) sans
     perdre la saison ni l'épisode sélectionnés.

Télécommande :
  OK sur un épisode      le lire (« Reprendre à … » / « Depuis le début »)
  OK maintenu / Menu     Lire depuis le début, Marquer vu / non vu, toute la saison
  Lecture/Pause          lire l'épisode sélectionné (ou la suite)
  Gauche / Droite        sur les saisons : change de saison
"""

from __future__ import annotations

import threading
import time

import xbmcgui

import kodi_library
import ui_common as ui
import watch_data

XML_FILE = "script-arrmada-series.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
SEASONS = 200
EPISODES = 300
BUTTONS = 400
BTN_PLAY = 401
BTN_DETAIL = 402

SEASON_MOVES = (xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT)


class SeriesWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        # `entry` : {"title", "kind", "arr_id", "tvdb_id", "poster", "fanart", "clearlogo"…}
        self._entry: dict = dict(kwargs.get("entry") or {})
        self._tvshowid: int = int(kwargs.get("tvshowid") or 0)
        self._wanted_season = kwargs.get("season")  # saison demandée par la Fiche
        self._opened_at = time.perf_counter()
        self._initialized = False
        self._stop = threading.Event()
        self._busy = threading.Lock()
        self._raw: list = []  # épisodes tels que Kodi les donne (pour l'enchaînement)
        self._model: dict = {}
        self._season_index = -1  # saison affichée
        self._positions: dict = {}  # épisode sélectionné dans chaque saison déjà vue

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            # Retour d'une lecture : vu / reprise ont changé, on relit.
            self._load_async(keep_selection=True)
            return
        self._initialized = True
        entry = self._entry
        self.setProperty("title", entry.get("title", ""))
        for art in ("poster", "fanart", "clearlogo"):
            self.setProperty(art, entry.get(art, ""))
        self.setProperty("play_label", "Lire")
        self.setProperty("has_detail", "1" if entry.get("arr_id") else "")
        ui.focus_when_visible(self, BTN_PLAY)
        ui.log("Série", f"ouverture en {ui.ms_since(self._opened_at)} ms : {entry.get('title')}")
        self._load_async(keep_selection=False)

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Chargement depuis la médiathèque Kodi ──────────────────────────────

    def _load_async(self, keep_selection: bool) -> None:
        threading.Thread(
            target=self._load, args=(keep_selection,), name="arrmada-series", daemon=True
        ).start()

    def _load(self, keep_selection: bool) -> None:
        if not self._busy.acquire(blocking=False):
            return  # un chargement est déjà en cours
        try:
            started = time.perf_counter()
            show = kodi_library.show_details(self._tvshowid)
            raw = kodi_library.show_episodes(self._tvshowid)
            if self._stop.is_set():
                return
            model = watch_data.build_show(show, raw)
            self._raw, self._model = raw, model
            try:
                self._render(model, keep_selection)
            except RuntimeError:
                return  # fenêtre fermée pendant le chargement
            ui.log(
                "Série",
                f"{len(raw)} épisode(s) chargé(s) en {ui.ms_since(started)} ms "
                f"(à suivre : {model['play_label'] or 'rien'})",
            )
        finally:
            self._busy.release()

    def _render(self, model: dict, keep_selection: bool) -> None:
        for key in ("poster", "fanart", "clearlogo"):
            if model[key]:
                self.setProperty(key, model[key])
        if model["title"]:
            self.setProperty("title", model["title"])
        self.setProperty("meta", model["meta"])
        self.setProperty("plot", model["plot"])
        self.setProperty("play_label", model["play_label"] or "Lire")
        self.setProperty("empty", "" if model["seasons"] else "1")

        seasons = self.getControl(SEASONS)
        keep_season = self._season_index if keep_selection else -1
        keep_episode = self.getControl(EPISODES).getSelectedPosition() if keep_selection else -1
        items = []
        for season in model["seasons"]:
            item = xbmcgui.ListItem(
                label=season["label"], label2=season["progress"], offscreen=True
            )
            item.setProperty("bar", season["bar"])
            items.append(item)
        seasons.reset()
        seasons.addItems(items)

        if 0 <= keep_season < len(items):
            index, episode = keep_season, keep_episode
        else:
            index, episode = self._start_position(model)
            self._positions = {}
        seasons.selectItem(index)
        self._season_index = -1  # force le remplissage des épisodes
        self._show_season(index, episode)
        self.setProperty("loaded", "1")

    def _start_position(self, model: dict) -> tuple:
        """Saison demandée par la Fiche, sinon celle de l'épisode à suivre."""
        wanted = self._wanted_season
        self._wanted_season = None
        if wanted is not None:
            for i, season in enumerate(model["seasons"]):
                if season["season"] == wanted:
                    return i, 0
        return model["start_season"], model["start_episode"]

    def _show_season(self, index: int, select: int | None = None) -> None:
        """Remplit la rangée des épisodes avec ceux de la saison n° `index`.

        En revenant sur une saison, on retrouve l'épisode qu'on y avait
        sélectionné ; la première fois, l'épisode « à suivre » (ou le 1er).
        """
        seasons = self._model.get("seasons") or []
        if not 0 <= index < len(seasons) or index == self._season_index:
            return
        container = self.getControl(EPISODES)
        if self._season_index >= 0:
            self._positions[self._season_index] = container.getSelectedPosition()
        if select is None:
            start = self._model.get("start_episode", 0)
            fallback = start if index == self._model.get("start_season") else 0
            select = self._positions.get(index, fallback)
        self._season_index = index
        episodes = self._model["episodes"][seasons[index]["season"]]
        items = []
        for ep in episodes:
            item = xbmcgui.ListItem(label=ep["label"], label2=ep["duration"], offscreen=True)
            item.setArt({"thumb": ep["thumb"]})
            tag = item.getVideoInfoTag()
            tag.setTitle(ep["title"])
            tag.setPlot(ep["plot"] or "Pas de résumé pour cet épisode.")
            tag.setMediaType("episode")
            item.setProperty("episodeid", str(ep["episodeid"]))
            item.setProperty("code", ep["code"])
            item.setProperty("title", ep["title"])
            item.setProperty("status", ep["status"])
            item.setProperty("aired", ep["aired"])
            item.setProperty("bar", ep["bar"])
            item.setProperty("watched", "1" if ep["watched"] else "")
            item.setProperty("resume", str(ep["resume"]))
            items.append(item)
        container.reset()
        container.addItems(items)
        if 0 <= select < len(items):
            container.selectItem(select)

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
        if focus == SEASONS and action_id in SEASON_MOVES:
            # Kodi a déjà déplacé la sélection : on affiche la nouvelle saison.
            self._show_season(self.getControl(SEASONS).getSelectedPosition())
        elif focus == EPISODES and action_id in ui.MENU_ACTIONS:
            self._episode_menu()
        elif action_id in ui.PLAY_ACTIONS:
            if focus == EPISODES:
                self._play_selected()
            else:
                self._play_next()

    def onClick(self, controlId):
        if controlId == EPISODES:
            self._play_selected()
        elif controlId == SEASONS:
            self.setFocusId(EPISODES)
        elif controlId == BTN_PLAY:
            self._play_next()
        elif controlId == BTN_DETAIL:
            import detail_window

            detail_window.open_detail(dict(self._entry, kind="tvshow"))

    # ── Lecture et « vu » ───────────────────────────────────────────────────

    def _selected(self) -> dict | None:
        item = self.getControl(EPISODES).getSelectedItem()
        if not item or not item.getProperty("episodeid"):
            return None
        return {
            "episodeid": int(item.getProperty("episodeid")),
            "resume": int(item.getProperty("resume") or 0),
            "watched": bool(item.getProperty("watched")),
            "code": item.getProperty("code"),
        }

    def _play_selected(self, resume=None) -> None:
        episode = self._selected()
        if episode:
            kodi_library.play_episode(
                episode["episodeid"], self._raw, resume=resume, entry=self._entry
            )

    def _play_next(self) -> None:
        """« Lire la suite » : l'épisode à suivre, ou le tout premier si tout est vu."""
        if not self._raw:
            return
        next_id = self._model.get("next_id") or 0
        if next_id:
            kodi_library.play_episode(next_id, self._raw, entry=self._entry)
            return
        first = watch_data.sort_episodes(self._raw)
        regular = [e for e in first if e.get("season") != watch_data.SPECIALS] or first
        kodi_library.play_episode(
            regular[0]["episodeid"], self._raw, resume=False, entry=self._entry
        )

    def _episode_menu(self) -> None:
        """Appui long sur un épisode : petites actions, aucune n'est destructrice."""
        episode = self._selected()
        seasons = self._model.get("seasons") or []
        if not episode or not 0 <= self._season_index < len(seasons):
            return
        season = seasons[self._season_index]
        season_ids = [e["episodeid"] for e in self._model["episodes"][season["season"]]]
        season_done = season["watched"] == season["total"]
        choices = [("play", "Lire")]
        if episode["resume"]:
            choices.append(("restart", "Lire depuis le début"))
        choices.append(
            ("unseen", "Marquer comme non vu")
            if episode["watched"]
            else ("seen", "Marquer comme vu")
        )
        choices.append(
            ("season_unseen", f"Marquer la {season['label'].lower()} comme non vue")
            if season_done
            else ("season_seen", f"Marquer la {season['label'].lower()} comme vue")
        )
        index = xbmcgui.Dialog().contextmenu([label for _, label in choices])
        if index < 0:
            return
        op = choices[index][0]
        if op == "play":
            self._play_selected()
        elif op == "restart":
            self._play_selected(resume=False)
        elif op in ("seen", "unseen"):
            kodi_library.set_watched("episode", episode["episodeid"], op == "seen")
            self._load_async(keep_selection=True)
        else:
            changed = kodi_library.set_many_watched(season_ids, op == "season_seen")
            ui.notify(season["label"], f"{changed} épisode(s) mis à jour")
            self._load_async(keep_selection=True)


def open_series(entry: dict, tvshowid: int, season: int | None = None) -> None:
    """Ouvre l'écran Série et bloque jusqu'à sa fermeture (touche Retour)."""
    window = SeriesWindow(
        XML_FILE,
        ui.ADDON.getAddonInfo("path"),
        "Default",
        "1080i",
        entry=entry,
        tvshowid=tvshowid,
        season=season,
    )
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

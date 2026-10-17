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

Phase 4.4 : les épisodes que Sonarr connaît et que Kodi n'a pas s'intercalent
à leur place, grisés : « Manquant » (OK : recherche dans Sonarr), « Sur le
NAS » (OK : scan de la médiathèque Kodi), « À venir » (date de diffusion).

Télécommande :
  OK sur un épisode      le lire (« Reprendre à … » / « Depuis le début »)
  OK maintenu / Menu     Lire depuis le début, Marquer vu / non vu, toute la saison
  Lecture/Pause          lire l'épisode sélectionné (ou la suite)
  Gauche / Droite        sur les saisons : change de saison
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import kodi_library
import ui_common as ui
import watch_data
from api import ArrMadaAPI

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
        self._season_index = -1  # saison affichée (rang dans la liste)
        self._season_number = None  # son numéro (le rang change si une saison s'ajoute)
        self._positions: dict = {}  # n° de saison → n° de l'épisode sélectionné
        self._tvdb = str(self._entry.get("tvdb_id") or "")  # pour Sonarr (manquants)

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
            self._tvdb = str((show.get("uniqueid") or {}).get("tvdb") or self._tvdb or "")
            if self._tvdb and not self._stop.is_set():
                self._add_missing(model)
        finally:
            self._busy.release()

    def _add_missing(self, model: dict) -> None:
        """Épisodes connus de Sonarr et absents de Kodi : ajoutés, grisés (phase 4.4).

        Après le premier affichage : l'écran ne dépend jamais du serveur pour
        s'ouvrir, les manquants arrivent une fraction de seconde plus tard.
        """
        started = time.perf_counter()
        response = ArrMadaAPI.get_feed(f"/api/kodi/series/{self._tvdb}/episodes", timeout=6)
        if not isinstance(response, dict) or response.get("status") != "ok":
            return  # serveur injoignable, Sonarr absent, série inconnue : rien à ajouter
        full = watch_data.add_missing(model, response.get("episodes") or [])
        if not full.get("missing") or self._stop.is_set():
            return
        self._model = full
        try:
            focus = self.getFocusId()
        except RuntimeError:
            focus = 0
        try:
            self._render(full, keep_selection=True)
            if focus in (SEASONS, EPISODES):
                # Une liste vidée puis remplie perd le focus de Kodi (vu en 4.3)
                ui.focus_when_visible(self, focus)
        except RuntimeError:
            return
        ui.log(
            "Série",
            f"{full['missing']} épisode(s) absent(s) de Kodi ajouté(s) d'après Sonarr "
            f"en {ui.ms_since(started)} ms",
        )

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
        # Sélection gardée par NUMÉRO (saison, épisode), pas par rang : un
        # épisode manquant intercalé décale les rangs.
        keep_number = self._season_number if keep_selection else None
        keep_episode = self._selected_number() if keep_selection else None
        numbers = [season["season"] for season in model["seasons"]]
        items = []
        for season in model["seasons"]:
            item = xbmcgui.ListItem(
                label=season["label"], label2=season["progress"], offscreen=True
            )
            item.setProperty("bar", season["bar"])
            items.append(item)
        seasons.reset()
        seasons.addItems(items)

        if keep_number in numbers:
            index = numbers.index(keep_number)
            episodes = [e["episode"] for e in model["episodes"][keep_number]]
            episode = episodes.index(keep_episode) if keep_episode in episodes else 0
        else:
            index, episode = self._start_position(model)
            self._positions = {}
        seasons.selectItem(index)
        self._season_index = -1  # force le remplissage des épisodes
        self._show_season(index, episode)
        self.setProperty("loaded", "1")

    def _selected_number(self):
        """N° de l'épisode sélectionné dans la saison affichée (None : aucun)."""
        item = self.getControl(EPISODES).getSelectedItem()
        if not item or not item.getProperty("number"):
            return None
        return int(item.getProperty("number"))

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
        if self._season_number is not None:
            self._positions[self._season_number] = self._selected_number()
        number = seasons[index]["season"]
        episodes = self._model["episodes"][number]
        if select is None:
            start = self._model.get("start_episode", 0)
            select = start if index == self._model.get("start_season") else 0
            remembered = [e["episode"] for e in episodes]
            if self._positions.get(number) in remembered:
                select = remembered.index(self._positions[number])
        self._season_index, self._season_number = index, number
        items = []
        for ep in episodes:
            missing = ep.get("missing", "")
            item = xbmcgui.ListItem(
                label=ep["label"],
                label2=ep["status"] if missing else ep["duration"],
                offscreen=True,
            )
            item.setArt({"thumb": ep["thumb"]})
            tag = item.getVideoInfoTag()
            tag.setTitle(ep["title"])
            tag.setPlot(ep["plot"] or "Pas de résumé pour cet épisode.")
            tag.setMediaType("episode")
            item.setProperty("episodeid", str(ep["episodeid"]))
            item.setProperty("number", str(ep["episode"]))
            item.setProperty("detail", watch_data.detail_line(ep))
            item.setProperty("missing", missing)  # vide : épisode présent dans Kodi
            item.setProperty("badge", ep.get("badge", ""))
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
            "season": self._season_number,
            "episode": int(item.getProperty("number") or 0),
            "resume": int(item.getProperty("resume") or 0),
            "watched": bool(item.getProperty("watched")),
            "code": item.getProperty("code"),
            "title": item.getProperty("title"),
            "status": item.getProperty("status"),
            "missing": item.getProperty("missing"),
        }

    def _play_selected(self, resume=None) -> None:
        episode = self._selected()
        if episode and episode["missing"]:
            self._missing_action(episode)
        elif episode:
            kodi_library.play_episode(
                episode["episodeid"], self._raw, resume=resume, entry=self._entry
            )

    # ── Épisodes absents de Kodi (Sonarr, phase 4.4) ────────────────────────

    def _missing_action(self, episode: dict) -> None:
        """OK sur un épisode grisé : chercher, scanner ou dire quand il sort."""
        heading = f"{episode['code']} · {episode['title']}"
        if episode["missing"] == "aired":
            if xbmcgui.Dialog().yesno(
                heading,
                "Cet épisode n'est pas sur le NAS.[CR]Lancer une recherche dans Sonarr ?",
                nolabel="Annuler",
                yeslabel="Chercher",
            ):
                threading.Thread(
                    target=self._search, args=(episode,), name="arrmada-search", daemon=True
                ).start()
        elif episode["missing"] == "nas":
            # Fichier déjà téléchargé, Kodi ne l'a pas encore vu : on scanne
            xbmc.executebuiltin("UpdateLibrary(video)")
            ui.notify(heading, "Sur le NAS : mise à jour de la médiathèque Kodi lancée")
        else:
            ui.notify(heading, episode["status"] or "À venir")

    def _search(self, episode: dict) -> None:
        result = ArrMadaAPI.trigger_search(
            {
                "media_type": "episode",
                "tvdb_id": self._tvdb,
                "title": self._model.get("title") or self._entry.get("title") or "",
                "season": episode["season"],
                "episode": episode["episode"],
            }
        )
        ok = result.get("status") == "ok"
        ui.notify(
            "Recherche lancée" if ok else "Recherche impossible",
            result.get("message") or episode["code"],
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
        if episode["missing"]:
            self._missing_action(episode)  # rien d'autre à faire sur un épisode absent
            return
        season = seasons[self._season_index]
        season_ids = [
            e["episodeid"] for e in self._model["episodes"][season["season"]] if e["episodeid"]
        ]
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

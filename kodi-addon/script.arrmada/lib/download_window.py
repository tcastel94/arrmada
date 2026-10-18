# -*- coding: utf-8 -*-
"""Feuille « Télécharger » de l'appli Kodi ArrMada (ADR-005, lot 2).

Mise en page : resources/skins/Default/1080i/script-arrmada-download.xml.
Logique (testée sans Kodi) : lib/download_data.py.

Remplace l'ancien assistant en 3 listes (profil qualité, dossier, mode) :
  - film : un bouton, « Télécharger le film » ;
  - série : Toute la série / Une saison / Un épisode, la saison en pastilles,
    les épisodes à cocher (plusieurs possibles).
« Pour ce soir » (activé par défaut) : le serveur choisit une release Usenet
et la fait passer devant les autres téléchargements de SABnzbd.
Qualité et dossier : ceux de la médiathèque (le serveur s'en charge) ;
« Options avancées » rouvre l'ancien assistant pour les choisir à la main.

Aucun appel réseau dans le fil de l'interface (ADR-003) : saisons, épisodes
et envoi passent par des fils d'arrière-plan.
"""

from __future__ import annotations

import threading

import xbmc
import xbmcgui

import download_data as dd
import listing
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-download.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
SCOPES = 810
SEASONS = 830
EPISODES = 840
BTN_TONIGHT = 820
BTN_DOWNLOAD = 821
BTN_ADVANCED = 822

ACTION_BUTTONS = (BTN_TONIGHT, BTN_DOWNLOAD, BTN_ADVANCED)


class DownloadWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._entry: dict = dict(kwargs.get("entry") or {})
        self._kind = self._entry.get("kind", "movie")
        self._scope = "season"  # la plus demandée : « la saison qu'on regarde »
        self._season = None
        self._seasons: list = []
        self._episodes: dict = {}  # saison → épisodes (cache de la feuille)
        self._source = ""
        self._picked: set = set()
        self._tonight = True
        self._sending = False
        self._last_list = SCOPES
        self._prev = 0  # focus avant la dernière touche (voir onAction)
        self._initialized = False
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        entry = self._entry
        self.setProperty("kind", self._kind)
        self.setProperty("title", entry.get("title", ""))
        meta = [str(entry.get("year") or "")] if entry.get("year") else []
        meta.append("Film" if self._kind == "movie" else "Série")
        self.setProperty("meta", " · ".join(meta))
        self.setProperty("overview", entry.get("overview", ""))
        self.setProperty("poster", entry.get("poster", ""))
        self.setProperty("fanart", entry.get("fanart", ""))
        self.setProperty("in_library", "1" if entry.get("in_library") else "")
        self.setProperty(
            "library_label",
            "Déjà dans la médiathèque"
            if entry.get("in_library")
            else "Pas encore dans la médiathèque",
        )
        if self._kind == "movie":
            self.setProperty("sheet_title", "Prêt à télécharger")
            self.setProperty(
                "movie_text",
                "Le film est ajouté avec ta qualité habituelle, puis téléchargé.[CR][CR]"
                "Les sous-titres français arrivent avec lui.[CR][CR]"
                "Une notification te prévient sur cette TV.",
            )
        else:
            self.setProperty("sheet_title", "Que veux-tu télécharger ?")
            self.setProperty("loading", "1")
            self._render_scopes()
            ui.run_in_background(self._load_seasons, None)
        self.setProperty("summary", dd.summary(self._kind, []))
        self._render_actions()
        self._prev = BTN_DOWNLOAD if self._kind == "movie" else SCOPES
        ui.focus_when_visible(self, self._prev)

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Données ─────────────────────────────────────────────────────────────

    def _load_seasons(self, season) -> None:
        """Saisons et épisodes d'une saison (Sonarr, sinon TMDB), en arrière-plan."""
        entry = self._entry
        if season is not None and season in self._episodes:
            self._show_season(season)
            return
        self._set("loading", "1")
        data = ArrMadaAPI.get_seasons(
            title=entry.get("title", ""),
            tmdb_id=entry.get("tmdb_id"),
            tvdb_id=entry.get("tvdb_id"),
            season=season,
        )
        if self._stop.is_set():
            return
        self._set("loading", "")
        if not isinstance(data, dict) or data.get("status") != "ok":
            message = (data or {}).get("message") if isinstance(data, dict) else ""
            self._set("summary", f"Saisons indisponibles : {message or 'serveur injoignable'}")
            self._set("episodes_note", "Tu peux quand même demander toute la série.")
            return
        with self._lock:
            for key in ("tvdb_id", "tmdb_id", "arr_id"):
                if data.get(key) and not entry.get(key):
                    entry[key] = data[key]
            if data.get("in_library"):
                entry["in_library"] = True
            self._seasons = data.get("seasons") or self._seasons
            self._source = data.get("source") or ""
            chosen = data.get("season")
            if chosen is not None:
                self._episodes[chosen] = data.get("episodes") or []
        self._set("in_library", "1" if entry.get("in_library") else "")
        self._set(
            "library_label",
            "Déjà dans la médiathèque"
            if entry.get("in_library")
            else "Pas encore dans la médiathèque",
        )
        self._set("summary", dd.summary(self._kind, self._seasons, self._source))
        self._render_scopes()
        if chosen is not None:
            self._show_season(chosen)
        else:
            self._render_actions()

    def _show_season(self, season: int) -> None:
        with self._lock:
            changed = season != self._season
            self._season = season
            if changed:
                self._picked = set()
            episodes = list(self._episodes.get(season) or [])
        try:
            self._render_seasons()
            items = []
            for data in dd.episode_items(episodes, self._picked):
                item = xbmcgui.ListItem(label=data["label"], offscreen=True)
                for key in ("number", "code", "state", "note", "picked"):
                    item.setProperty(key, data[key])
                items.append(item)
            control = self.getControl(EPISODES)
            control.reset()
            control.addItems(items)
            self.setProperty("episodes_note", dd.episodes_note(self._source, episodes))
            self._render_actions()
        except RuntimeError:
            pass  # fenêtre fermée entre-temps

    # ── Rendu ───────────────────────────────────────────────────────────────

    def _set(self, key: str, value: str) -> None:
        try:
            self.setProperty(key, value)
        except RuntimeError:
            pass

    def _render_scopes(self) -> None:
        try:
            control = self.getControl(SCOPES)
            position = control.getSelectedPosition()
            control.reset()
            for data in dd.scope_items(self._scope, self._seasons):
                item = xbmcgui.ListItem(label=data["label"], label2=data["label2"], offscreen=True)
                item.setProperty("selected", data["selected"])
                item.setProperty("key", data["key"])
                control.addItem(item)
            if position < 0:  # 1er affichage : sur la portée sélectionnée
                position = [key for key, _ in dd.SCOPES].index(self._scope)
            control.selectItem(position)
            self.setProperty("scope", self._scope)
        except RuntimeError:
            pass

    def _render_seasons(self) -> None:
        control = self.getControl(SEASONS)
        position = control.getSelectedPosition()
        control.reset()
        for data in dd.season_items(self._seasons, self._season):
            item = xbmcgui.ListItem(label=data["label"], label2=data["label2"], offscreen=True)
            item.setProperty("selected", data["selected"])
            item.setProperty("number", data["number"])
            control.addItem(item)
        if position < 0:
            position = next(
                (i for i, s in enumerate(self._seasons) if s.get("number") == self._season), 0
            )
        control.selectItem(position)

    def _render_actions(self) -> None:
        self._set("tonight", "1" if self._tonight else "")
        self._set("tonight_hint", dd.tonight_hint(self._tonight))
        self._set(
            "button_label", dd.button_label(self._kind, self._scope, self._season, self._picked)
        )
        hints = {
            "series": "Toutes les saisons, au fur et à mesure de leur sortie.",
            "season": "Toute la saison choisie (OK sur une pastille pour en changer).",
            "episode": "OK sur un épisode pour le cocher, plusieurs possibles.",
        }
        self._set("list_hint", hints.get(self._scope, "") if self._kind == "series" else "")

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        """Redirections quand la rangée visée est masquée ou inactive.

        Kodi a DÉJÀ déplacé le focus quand ce code s'exécute : on compare donc
        avec le focus d'avant la touche (`_prev`). « Toujours au même endroit »
        après une flèche = la cible était masquée, on choisit la bonne.
        """
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self.close_window()
            return
        try:
            focus = self.getFocusId()
        except RuntimeError:
            return
        stuck = focus == self._prev
        if focus in (SCOPES, SEASONS, EPISODES):
            self._last_list = focus
        target = None
        if action_id == xbmcgui.ACTION_MOVE_DOWN and stuck:
            # Toute la série : pas de saisons ; une saison : épisodes non cochables
            if focus in (SCOPES, SEASONS):
                target = BTN_DOWNLOAD
        elif action_id == xbmcgui.ACTION_MOVE_LEFT and stuck and focus in ACTION_BUTTONS:
            if self._kind == "series":
                target = self._last_list
                if target == EPISODES and self._scope != "episode":
                    target = SEASONS if self._scope == "season" else SCOPES
                if target == SEASONS and self._scope == "series":
                    target = SCOPES
        if target is not None:
            self.setFocusId(target)
            focus = target
        self._prev = focus

    def onClick(self, controlId):
        if controlId == SCOPES:
            item = self.getControl(SCOPES).getSelectedItem()
            if item:
                self._choose_scope(item.getProperty("key"))
        elif controlId == SEASONS:
            item = self.getControl(SEASONS).getSelectedItem()
            if item and item.getProperty("number"):
                season = int(item.getProperty("number"))
                if season in self._episodes:
                    self._show_season(season)
                else:
                    self._season = season
                    self._picked = set()
                    self._render_seasons()
                    self._render_actions()
                    ui.run_in_background(self._load_seasons, season)
        elif controlId == EPISODES:
            item = self.getControl(EPISODES).getSelectedItem()
            if item and self._scope == "episode" and item.getProperty("number"):
                number = int(item.getProperty("number"))
                self._picked = dd.toggle_pick(self._picked, number)
                item.setProperty("picked", "1" if number in self._picked else "")
                self._render_actions()
        elif controlId == BTN_TONIGHT:
            self._tonight = not self._tonight
            self._render_actions()
        elif controlId == BTN_DOWNLOAD:
            self._send()
        elif controlId == BTN_ADVANCED:
            self._advanced()

    def _choose_scope(self, scope: str) -> None:
        if scope not in ("series", "season", "episode"):
            return
        self._scope = scope
        if scope != "episode":
            self._picked = set()
        self._render_scopes()
        if self._season is not None:
            self._show_season(self._season)
        else:
            self._render_actions()
        # La rangée visée vient peut-être d'apparaître (ou de s'activer) :
        # le focus ne s'y pose qu'à l'image suivante
        target = {"series": BTN_DOWNLOAD, "season": SEASONS, "episode": EPISODES}[scope]
        if target == EPISODES and not self._episodes.get(self._season):
            target = SEASONS  # rien à cocher (pas encore chargé, ou pas d'épisodes connus)
        self._prev = target
        ui.focus_when_visible(self, target)

    # ── Envoi ───────────────────────────────────────────────────────────────

    def _send(self) -> None:
        title = self._entry.get("title") or "Télécharger"
        if self._sending:
            return
        if not dd.ready(self._kind, self._scope, self._season, self._picked):
            ui.notify(title, dd.button_label(self._kind, self._scope, self._season, self._picked))
            return
        body = dd.payload(self._entry, self._scope, self._season, self._picked, self._tonight)
        self._sending = True
        self._set("sending", "1")
        ui.run_in_background(self._post, body)

    def _post(self, body: dict) -> None:
        result = dd.result_message(ArrMadaAPI.start_download(body))
        self._sending = False
        self._set("sending", "")
        ui.notify(result["title"], result["message"], 5000)
        ui.log("Télécharger", f"{body} → {result['message']}")
        if result["ok"] and not self._stop.is_set():
            self.close_window()

    def _advanced(self) -> None:
        """L'ancien assistant (profil qualité, dossier, release à la main), via le plugin."""
        entry = self._entry
        params = {
            "action": "media_advanced",
            "type": "series" if self._kind == "series" else "movie",
            "title": entry.get("title") or "",
            "tmdb_id": str(entry.get("tmdb_id") or ""),
            "tvdb_id": str(entry.get("tvdb_id") or ""),
            "arr_id": str(entry.get("arr_id") or ""),
            "in_library": "1" if entry.get("in_library") else "0",
            "year": str(entry.get("year") or ""),
            "overview": (entry.get("overview") or "")[:600],
        }
        self.close_window()
        xbmc.executebuiltin(f"RunPlugin({listing.plugin_url('plugin://script.arrmada/', params)})")


def open_download(entry: dict) -> None:
    """Ouvre la feuille et bloque jusqu'à sa fermeture (Retour, ou demande envoyée)."""
    window = DownloadWindow(
        XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", entry=entry
    )
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

# -*- coding: utf-8 -*-
"""Écran « Fiche média » de l'appli Kodi ArrMada (phase 2, ADR-003 § 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-detail.xml.

Ouverture en deux temps, sans jamais figer l'interface :
  1. ce que l'écran appelant connaît déjà (titre, affiche, fanart, logo,
     synopsis) s'affiche immédiatement ;
  2. un fil d'arrière-plan charge la fiche complète (Radarr/Sonarr + Bazarr :
     casting, fichier, notes, sous-titres, saisons) et complète l'écran.

Boîtier et disque (1.20.0, façon Aeon Nox en 1.20.1) : l'affiche est la jaquette
d'un vrai boîtier Blu-ray (bleu, bandeau « Blu-ray Disc »), 4K ULTRA HD (noir)
ou DVD (noir, plus haut), d'après le fichier ; le disque, rond imprimé de
fanart.tv ou dessiné à partir de l'affiche, en sort à l'ouverture, tourne,
rentre quand on lance la lecture et à la fermeture (animations du XML,
propriété disc_out).

Actions (aucune n'est destructrice, ADR-003 décision 1) :
  Lire               film : médiathèque Kodi de cet appareil + préréglage Yamaha de
                     la pièce, « Reprendre à … » s'il a été commencé (ADR-004) ;
                     série : l'écran Série d'ArrMada (saisons → épisodes)
  Appui long (Lire)  film : Lire depuis le début, Marquer comme vu / non vu
  Bande-annonce      add-on YouTube (films : Sonarr n'en connaît pas)
  Meilleure version  recherche Radarr/Sonarr
  Sous-titres        recherche Bazarr (films)
  Télécharger        feuille « Télécharger » (ADR-005) : une saison, un épisode,
                     toute la série, ou le film s'il n'a pas de fichier
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import screens_data
import ui_common as ui
import watch_data
from api import ArrMadaAPI

XML_FILE = "script-arrmada-detail.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
ACTIONS = 500
BTN_PLAY = 501
BTN_TRAILER = 502
BTN_UPGRADE = 503
BTN_SUBTITLES = 504
BTN_PHONE = 505  # phase 3 : page du titre dans la web app (QR code)
BTN_DOWNLOAD = 506  # feuille « Télécharger » (ADR-005) : série, ou film sans fichier
BADGES = 520
CAST = 600
SEASONS = 610


def _initials(name: str) -> str:
    """« Timothée Chalamet » → « TC » (pastille quand il n'y a pas de photo)."""
    return "".join(part[0] for part in name.split()[:2]).upper()


class DetailWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        # `entry` : {"kind", "arr_id", "title", "year", "tmdb_id", "tvdb_id",
        #            "poster", "fanart", "clearlogo", "discart", "plot", "meta"}
        self._entry: dict = dict(kwargs.get("entry") or {})
        self._opened_at = time.perf_counter()
        self._initialized = False
        self._stop = threading.Event()
        self._trailer = ""
        self._seasons: list = []  # saisons connues du serveur (numéros)
        self._movieid = 0  # film dans la médiathèque Kodi de cet appareil
        self._movie_state: dict = {}

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            # Retour d'une lecture : la reprise / le « vu » ont changé, et le
            # disque rangé au lancement de la lecture ressort du boîtier.
            self._disc_out(True)
            ui.run_in_background(self._load_kodi_state)
            return
        self._initialized = True
        entry = self._entry
        kind = entry.get("kind", "movie")
        self.setProperty("kind", kind)
        self.setProperty("play_label", "Lire" if kind == "movie" else "Ouvrir la série")
        self.setProperty("title", entry.get("title", ""))
        self.setProperty("meta", entry.get("meta", ""))
        self.setProperty("overview", entry.get("plot", ""))
        for art in ("poster", "fanart", "clearlogo", "discart"):
            self.setProperty(art, entry.get(art, ""))
        self.setProperty("rail_title", "Casting" if kind == "movie" else "Saisons")
        # Le disque sort du boîtier (après l'animation d'ouverture, cf. XML)
        self._disc_out(True)
        ui.focus_when_visible(self, BTN_PLAY)
        ui.log("Fiche", f"ouverture en {ui.ms_since(self._opened_at)} ms : {entry.get('title')}")
        threading.Thread(target=self._load, name="arrmada-detail", daemon=True).start()

    def close_window(self) -> None:
        self._stop.set()
        self.close()  # le disque rentre dans le boîtier : animation WindowClose du XML

    def _disc_out(self, out: bool) -> None:
        """Sort (True) ou range (False) le disque. Sans affiche ni rond imprimé,
        il n'y a rien à montrer : le disque reste rangé."""
        has_art = bool(self.getProperty("discart") or self.getProperty("poster"))
        try:
            self.setProperty("disc_out", "1" if out and has_art else "")
        except RuntimeError:
            pass  # fenêtre fermée entre-temps

    def _play(self, entry: dict) -> None:
        """Lire : le disque rentre dans le boîtier, puis la lecture démarre."""
        self._disc_out(False)
        ui.play_entry(entry)

    # ── Chargement de la fiche complète ─────────────────────────────────────

    def _load(self) -> None:
        try:
            self._load_detail()
        finally:
            # Identifiants complétés par la fiche : on cherche le titre dans Kodi
            if not self._stop.is_set():
                self._load_kodi_state()

    def _load_kodi_state(self) -> None:
        """Film : « Reprendre à 42:10 » / « Revoir » sur le bouton Lire (ADR-004)."""
        if self._entry.get("kind", "movie") != "movie":
            return
        import kodi_library

        found = ui.find_in_library(self._entry)
        if found is None or self._stop.is_set():
            return
        state = watch_data.movie_state(kodi_library.movie_details(found))
        self._movieid, self._movie_state = found, state
        if state["resume"]:
            label = f"Reprendre à {watch_data.clock(state['resume'])}"
        else:
            label = "Revoir" if state["watched"] else "Lire"
        try:
            self.setProperty("play_label", label)
        except RuntimeError:
            pass  # fenêtre fermée entre-temps

    def _load_detail(self) -> None:
        started = time.perf_counter()
        entry = self._entry
        raw = ArrMadaAPI.get_media_detail(entry.get("kind", "movie"), entry.get("arr_id"))
        if self._stop.is_set():
            return
        if not isinstance(raw, dict) or raw.get("status") == "error" or raw.get("error"):
            message = (raw or {}).get("message") or (raw or {}).get("error") or "fiche indisponible"
            ui.log("Fiche", f"échec : {message}", xbmc.LOGWARNING)
            try:
                self.setProperty("loaded", "1")
                self.setProperty("rail_title", "Fiche indisponible")
            except RuntimeError:
                pass
            ui.notify(entry.get("title", "ArrMada"), f"Fiche indisponible : {message}")
            return
        model = screens_data.build_detail(
            raw, "movie" if entry.get("kind") == "movie" else "series"
        )
        try:
            self._render(model)
        except RuntimeError:
            return  # fenêtre fermée pendant le chargement
        ui.log("Fiche", f"chargée en {ui.ms_since(started)} ms")

    def _render(self, model: dict) -> None:
        # Les données complètes priment, mais on garde l'existant si un champ manque.
        for key in ("poster", "fanart", "clearlogo", "discart"):
            if model[key]:
                self.setProperty(key, model[key])
        # Boîtier : Blu-ray bleu, 4K ULTRA HD noir, DVD noir, transparent sans fichier
        self.setProperty("case_format", model["case_format"])
        self.setProperty("case_label", model["case_label"])
        if not self.getProperty("disc_out"):
            self._disc_out(True)  # affiche arrivée avec la fiche complète
        if model["title"]:
            self.setProperty("title", model["title"])
        self.setProperty("meta", model["meta"] or self._entry.get("meta", ""))
        self.setProperty("notes", model["notes"])
        self.setProperty("overview", model["overview"])
        self.setProperty("crew", model["crew"])
        self.setProperty("status", model["status"])
        self.setProperty("can_download", "1" if model.get("can_download") else "")
        self.setProperty("file", "[CR]".join(model["file_lines"]) or "Aucun fichier pour l'instant")
        self.setProperty("subtitles", model["subtitles"])
        self._trailer = model["trailer"]
        # Identifiants et audio : utiles à « Lire » (médiathèque + préréglage ampli)
        for key in ("tmdb_id", "tvdb_id", "audio_codec", "audio_channels"):
            if model.get(key):
                self._entry[key] = model[key]
        if model["year"]:
            self._entry["year"] = model["year"]

        badges = self.getControl(BADGES)
        badges.reset()
        badges.addItems([xbmcgui.ListItem(label=b, offscreen=True) for b in model["badges"]])

        if model["kind"] == "movie":
            items = []
            for person in model["cast"]:
                item = xbmcgui.ListItem(label=person["name"], label2=person["role"], offscreen=True)
                item.setArt({"thumb": person["photo"]})
                item.setProperty("initials", _initials(person["name"]))
                items.append(item)
            cast = self.getControl(CAST)
            cast.reset()
            cast.addItems(items)
            if not items:
                self.setProperty("rail_title", "Casting non renseigné")
        else:
            self._seasons = model["seasons"]
            items = []
            for season in model["seasons"]:
                item = xbmcgui.ListItem(
                    label=season["label"], label2=season["progress"], offscreen=True
                )
                item.setProperty("bar", season["bar"])
                items.append(item)
            seasons = self.getControl(SEASONS)
            seasons.reset()
            seasons.addItems(items)
        self.setProperty("loaded", "1")

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            self.close_window()
        elif action_id in ui.PLAY_ACTIONS:
            self._play(self._entry)
        elif action_id in ui.MENU_ACTIONS and self._entry.get("kind", "movie") == "movie":
            try:
                on_play = self.getFocusId() == BTN_PLAY
            except RuntimeError:
                on_play = False
            if on_play:
                self._movie_menu()
        elif action_id == xbmcgui.ACTION_MOVE_DOWN and self._entry.get("kind") == "tvshow":
            # Le XML envoie la flèche bas vers le casting (masqué pour une
            # série) ; Kodi ne permet pas de changer la navigation d'un groupe
            # de boutons depuis Python : on redirige ici vers les saisons.
            try:
                if self.getFocusId() in (
                    BTN_PLAY,
                    BTN_TRAILER,
                    BTN_UPGRADE,
                    BTN_SUBTITLES,
                    BTN_PHONE,
                    BTN_DOWNLOAD,
                ):
                    self.setFocusId(SEASONS)
            except RuntimeError:
                pass

    def onClick(self, controlId):
        entry = self._entry
        if controlId == BTN_PLAY:
            self._play(entry)
        elif controlId == SEASONS:
            # Écran Série directement sur la saison choisie
            index = self.getControl(SEASONS).getSelectedPosition()
            season = self._seasons[index]["number"] if 0 <= index < len(self._seasons) else None
            ui.play_entry(dict(entry, season=season))
        elif controlId == BTN_TRAILER:
            ui.play_trailer(self._trailer, entry.get("title", ""))
        elif controlId == BTN_UPGRADE:
            ui.run_in_background(ui.search_release, dict(entry))
        elif controlId == BTN_SUBTITLES:
            ui.run_in_background(ui.search_subtitles, dict(entry))
        elif controlId == BTN_PHONE:
            self._show_on_phone(entry)
        elif controlId == BTN_DOWNLOAD:
            self._open_download(entry)
        elif controlId == CAST:
            item = self.getControl(CAST).getSelectedItem()
            if item:
                ui.notify(item.getLabel(), item.getLabel2() or "Casting")

    def _movie_menu(self) -> None:
        """Appui long : Lire depuis le début, Marquer comme vu / non vu (film dans Kodi)."""
        if not self._movieid:
            ui.notify(
                self._entry.get("title") or "ArrMada",
                "Pas dans la médiathèque Kodi de cet appareil",
            )
            return
        import kodi_library

        state = self._movie_state
        choices = []
        if state.get("resume"):
            choices.append(("restart", "Lire depuis le début"))
        choices.append(
            ("unseen", "Marquer comme non vu")
            if state.get("watched")
            else ("seen", "Marquer comme vu")
        )
        index = xbmcgui.Dialog().contextmenu([label for _, label in choices])
        if index < 0:
            return
        op = choices[index][0]
        if op == "restart":
            self._disc_out(False)
            ui.play_entry(self._entry, resume=False)
        else:
            kodi_library.set_watched("movie", self._movieid, op == "seen")
            ui.run_in_background(self._load_kodi_state)

    def _open_download(self, entry: dict) -> None:
        """Feuille « Télécharger » du titre (déjà suivi : saisons et épisodes de Sonarr)."""
        import download_window

        download_window.open_download(
            {
                "kind": "movie" if entry.get("kind", "movie") == "movie" else "series",
                "title": entry.get("title") or "",
                "year": entry.get("year") or "",
                "tmdb_id": entry.get("tmdb_id") or None,
                "tvdb_id": entry.get("tvdb_id") or None,
                "arr_id": entry.get("arr_id") or None,
                "in_library": True,
                "overview": self.getProperty("overview"),
                "poster": self.getProperty("poster"),
                "fanart": self.getProperty("fanart"),
            }
        )

    @staticmethod
    def _show_on_phone(entry: dict) -> None:
        """QR code vers la fiche complète du titre dans la web app (phase 3)."""
        import links_data
        import qr_window

        path = links_data.media_path(entry.get("kind", ""), entry.get("arr_id"))
        if not path:
            ui.notify(entry.get("title") or "ArrMada", "Fiche web indisponible pour ce titre")
            return
        qr_window.show_qr(
            entry.get("title") or "Sur ton téléphone",
            "La fiche complète dans la web app : historique, fichiers, profil de qualité, "
            "suppression (impossible depuis la TV).",
            path=path,
        )


def open_detail(entry: dict) -> None:
    """Ouvre la fiche et bloque jusqu'à sa fermeture (touche Retour)."""
    window = DetailWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i", entry=entry)
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

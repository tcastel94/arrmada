# -*- coding: utf-8 -*-
"""Écran « Fiche média » de l'appli Kodi ArrMada (phase 2, ADR-003 § 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-detail.xml.

Ouverture en deux temps, sans jamais figer l'interface :
  1. ce que l'écran appelant connaît déjà (titre, affiche, fanart, logo,
     synopsis) s'affiche immédiatement ;
  2. un fil d'arrière-plan charge la fiche complète (Radarr/Sonarr + Bazarr :
     casting, fichier, notes, sous-titres, saisons) et complète l'écran.

Actions (aucune n'est destructrice, ADR-003 décision 1) :
  Lire               médiathèque Kodi de cet appareil + préréglage Yamaha de la pièce
  Bande-annonce      add-on YouTube (films : Sonarr n'en connaît pas)
  Meilleure version  recherche Radarr/Sonarr
  Sous-titres        recherche Bazarr (films)
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import screens_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-detail.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
ACTIONS = 500
BTN_PLAY = 501
BTN_TRAILER = 502
BTN_UPGRADE = 503
BTN_SUBTITLES = 504
BTN_PHONE = 505  # phase 3 : page du titre dans la web app (QR code)
BADGES = 520
CAST = 600
SEASONS = 610


def _initials(name: str) -> str:
    """« Timothée Chalamet » → « TC » (pastille quand il n'y a pas de photo)."""
    return "".join(part[0] for part in name.split()[:2]).upper()


class DetailWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        # `entry` : {"kind", "arr_id", "title", "year", "tmdb_id", "tvdb_id",
        #            "poster", "fanart", "clearlogo", "plot", "meta"}
        self._entry: dict = dict(kwargs.get("entry") or {})
        self._opened_at = time.perf_counter()
        self._initialized = False
        self._stop = threading.Event()
        self._trailer = ""

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        if self._initialized:
            return  # retour depuis la lecture ou la médiathèque : rien à refaire
        self._initialized = True
        entry = self._entry
        kind = entry.get("kind", "movie")
        self.setProperty("kind", kind)
        self.setProperty("title", entry.get("title", ""))
        self.setProperty("meta", entry.get("meta", ""))
        self.setProperty("overview", entry.get("plot", ""))
        for art in ("poster", "fanart", "clearlogo"):
            self.setProperty(art, entry.get(art, ""))
        self.setProperty("rail_title", "Casting" if kind == "movie" else "Saisons")
        ui.focus_when_visible(self, BTN_PLAY)
        ui.log("Fiche", f"ouverture en {ui.ms_since(self._opened_at)} ms : {entry.get('title')}")
        threading.Thread(target=self._load, name="arrmada-detail", daemon=True).start()

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Chargement de la fiche complète ─────────────────────────────────────

    def _load(self) -> None:
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
        for key in ("poster", "fanart", "clearlogo"):
            if model[key]:
                self.setProperty(key, model[key])
        if model["title"]:
            self.setProperty("title", model["title"])
        self.setProperty("meta", model["meta"] or self._entry.get("meta", ""))
        self.setProperty("notes", model["notes"])
        self.setProperty("overview", model["overview"])
        self.setProperty("crew", model["crew"])
        self.setProperty("status", model["status"])
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
            ui.play_entry(self._entry)
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
                ):
                    self.setFocusId(SEASONS)
            except RuntimeError:
                pass

    def onClick(self, controlId):
        entry = self._entry
        if controlId in (BTN_PLAY, SEASONS):
            ui.play_entry(entry)
        elif controlId == BTN_TRAILER:
            ui.play_trailer(self._trailer, entry.get("title", ""))
        elif controlId == BTN_UPGRADE:
            ui.run_in_background(ui.search_release, dict(entry))
        elif controlId == BTN_SUBTITLES:
            ui.run_in_background(ui.search_subtitles, dict(entry))
        elif controlId == BTN_PHONE:
            self._show_on_phone(entry)
        elif controlId == CAST:
            item = self.getControl(CAST).getSelectedItem()
            if item:
                ui.notify(item.getLabel(), item.getLabel2() or "Casting")

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

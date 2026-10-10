# -*- coding: utf-8 -*-
"""Écran « Accueil » de l'appli Kodi ArrMada (prototype phase 0, ADR-003).

Fenêtre sur mesure (WindowXML) : la mise en page vit dans
resources/skins/Default/1080i/script-arrmada-home.xml, ce module ne fait que
la remplir.

Règle d'or (ADR-003 § 1) : AUCUN appel réseau dans le fil de l'interface.
  1. À l'ouverture, on affiche le dernier état connu (cache disque) → instantané.
  2. Un fil d'arrière-plan (thread) interroge le backend, puis met l'écran à
     jour ; il recommence toutes les REFRESH_SECONDS tant que la fenêtre est
     ouverte (progression des téléchargements en direct).
  Analogie infra : l'écran lit un « miroir local », un démon le resynchronise.

Les temps mesurés (ouverture, réseau, rendu) sont affichés dans le panneau
« Diagnostic » et écrits dans kodi.log (préfixe [ArrMada]) : c'est le critère
« performances » de la phase 0.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import home_data
from api import ArrMadaAPI

ADDON = xbmcaddon.Addon("script.arrmada")
XML_FILE = "script-arrmada-home.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML.
# (Vérifié automatiquement par kodi-addon/tests/test_home_window_xml.py.)
RAIL = 100  # rangée d'affiches « Ajouts récents »
SERVICES = 300  # pastilles d'état des services
BUTTONS = 400  # boutons du bandeau (groupe)
BTN_REFRESH = 401
BTN_DIAG = 402
DIAG_CLOSE = 901
DL_PROGRESS = (211, 221, 231)  # barres des 3 emplacements de téléchargement
STORAGE_PROGRESS = 251

REFRESH_SECONDS = 20  # le backend met déjà le tableau de bord en cache 15 s
BACK_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] Accueil : {message}", level=level)


def _ms(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


def _fmt_ms(value: int) -> str:
    return f"{value} ms" if value else "< 1 ms"


def _cache_dir() -> str:
    """special://profile/addon_data/script.arrmada/cache/ en chemin réel."""
    return os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")), "cache")


class HomeWindow(xbmcgui.WindowXML):
    """Fenêtre plein écran. Kodi appelle onInit() une fois le XML chargé."""

    def __init__(self, *args, **kwargs):
        # Pas d'accès aux contrôles ici : le XML n'est pas encore chargé.
        self._opened_at = time.perf_counter()
        self._initialized = False
        self._stop = threading.Event()  # levé à la fermeture → arrête le fil
        self._busy = threading.Lock()  # un seul rafraîchissement à la fois
        self._rail_ids: list[str] = []
        self._last_fetch = ""  # horodatage des dernières données affichées
        self._monitor = xbmc.Monitor()

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        # onInit est rappelé quand on revient d'une autre fenêtre : ne pas
        # tout refaire (ni relancer un second fil).
        if self._initialized:
            return
        self._initialized = True

        self.setProperty("icon", ADDON.getAddonInfo("icon"))
        self.setProperty("version", ADDON.getAddonInfo("version"))
        self.setProperty("skin", xbmc.getSkinDir())
        self.setProperty("server_url", ArrMadaAPI.get_config()["url"])
        self.setProperty("greeting", home_data.greeting(datetime.now().hour))

        cached = home_data.load_cache(_cache_dir())
        if cached:
            started = time.perf_counter()
            self._render(cached, source="cache")
            self.setProperty("perf_cache", _fmt_ms(_ms(started)))
        else:
            self.setProperty("perf_cache", "aucun cache (1re ouverture)")
        open_ms = _ms(self._opened_at)
        self.setProperty("perf_open", _fmt_ms(open_ms))
        _log(f"ouverture en {open_ms} ms ({'cache' if cached else 'sans cache'})")

        threading.Thread(target=self._loop, name="arrmada-home", daemon=True).start()

    def _loop(self) -> None:
        """Fil d'arrière-plan : rafraîchit, attend, recommence."""
        while not self._stop.is_set() and not self._monitor.abortRequested():
            self._refresh()
            # wait() rend la main tout de suite si la fenêtre se ferme.
            if self._stop.wait(REFRESH_SECONDS):
                break

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Données ─────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._busy.acquire(blocking=False):
            return  # un rafraîchissement est déjà en cours
        try:
            self.setProperty("loading", "1")
            started = time.perf_counter()
            dashboard = ArrMadaAPI.get_dashboard()
            recent = ArrMadaAPI.get_recent_media()
            net_ms = _ms(started)
            if self._stop.is_set():
                return

            if not isinstance(dashboard, dict) or dashboard.get("status") == "error":
                message = dashboard.get("message") if isinstance(dashboard, dict) else ""
                self.setProperty("error", message or "Serveur ArrMada injoignable")
                # Âge des données encore affichées (cache), recalculé à chaque essai.
                self.setProperty(
                    "updated", home_data.age_label(self._last_fetch, datetime.now(timezone.utc))
                )
                if not self._rail_ids:
                    # Rien à afficher (ni cache ni serveur) : la rangée vide ne
                    # peut pas prendre le focus, on le donne à « Actualiser »
                    # pour que la télécommande ne soit pas bloquée.
                    self.setProperty("ready", "1")
                    self._ensure_focus(BTN_REFRESH)
                _log(f"échec réseau en {net_ms} ms : {message}", xbmc.LOGWARNING)
                return
            self.clearProperty("error")

            model = home_data.build_model(dashboard, recent, datetime.now(timezone.utc))
            started = time.perf_counter()
            self._render(model, source="serveur")
            render_ms = _ms(started)
            self.setProperty("perf_net", _fmt_ms(net_ms))
            self.setProperty("perf_render", _fmt_ms(render_ms))
            _log(f"réseau {net_ms} ms, rendu {render_ms} ms, {len(model['recent'])} affiches")

            try:
                home_data.save_cache(_cache_dir(), model)
            except OSError as exc:
                _log(f"cache non écrit : {exc}", xbmc.LOGWARNING)
        except RuntimeError as exc:
            # Fenêtre fermée pendant la mise à jour : rien à faire.
            _log(f"rafraîchissement interrompu : {exc}", xbmc.LOGDEBUG)
        finally:
            self.clearProperty("loading")
            self._busy.release()

    # ── Affichage ───────────────────────────────────────────────────────────

    def _render(self, model: dict, source: str) -> None:
        kpis = model.get("kpis") or {}
        for key in (
            "movies",
            "movies_hint",
            "series",
            "series_hint",
            "storage",
            "storage_hint",
            "downloads",
            "downloads_hint",
        ):
            self.setProperty(f"kpi_{key}", str(kpis.get(key, "")))
        self.setProperty("summary", model.get("summary", ""))
        self.setProperty("source", source)
        self._last_fetch = model.get("fetched_at", "")
        self.setProperty(
            "updated",
            home_data.age_label(model.get("fetched_at", ""), datetime.now(timezone.utc)),
        )
        self.getControl(STORAGE_PROGRESS).setPercent(float(kpis.get("storage_pct") or 0))

        self._render_downloads(model.get("downloads") or [], int(model.get("downloads_more") or 0))
        self._render_services(model.get("services") or [], int(model.get("services_active") or 0))
        self._render_rail(model.get("recent") or [])
        self.setProperty("ready", "1")

    def _render_downloads(self, downloads: list[dict], more: int) -> None:
        self.setProperty("dl_count", str(len(downloads)))
        self.setProperty("dl_more", f"+ {more} autre(s)" if more else "")
        for index, control_id in enumerate(DL_PROGRESS):
            slot = f"dl{index + 1}"
            if index < len(downloads):
                self.setProperty(f"{slot}_title", downloads[index]["title"])
                self.setProperty(f"{slot}_meta", downloads[index]["meta"])
                self.getControl(control_id).setPercent(float(downloads[index]["pct"]))
            else:
                self.clearProperty(f"{slot}_title")
                self.clearProperty(f"{slot}_meta")

    def _render_services(self, services: list[dict], active: int) -> None:
        self.setProperty("services_summary", f"{active}/{len(services)} actifs" if services else "")
        container = self.getControl(SERVICES)
        container.reset()
        items = []
        for service in services:
            item = xbmcgui.ListItem(label=service["name"], offscreen=True)
            item.setProperty("status", service["status"])
            items.append(item)
        container.addItems(items)

    def _render_rail(self, recent: list[dict]) -> None:
        """Affiches « Ajouts récents ». Reconstruite seulement si la liste change.

        Reconstruire à chaque rafraîchissement ferait « sauter » la sélection
        et recharger les images : on compare d'abord les identifiants.
        """
        ids = [entry["id"] for entry in recent]
        self.setProperty("recent_count", str(len(ids)))
        if ids == self._rail_ids:
            return
        self._rail_ids = ids

        rail = self.getControl(RAIL)
        position = rail.getSelectedPosition()
        items = []
        for entry in recent:
            item = xbmcgui.ListItem(label=entry["title"], offscreen=True)
            item.setArt(
                {
                    "poster": entry["poster"],
                    "thumb": entry["poster"],
                    "fanart": entry["fanart"],
                    "clearlogo": entry["clearlogo"],
                }
            )
            # API Kodi 20+ (setInfo est déprécié) : le skin lit ces champs
            # via ListItem.Title, ListItem.Year, ListItem.Plot…
            tag = item.getVideoInfoTag()
            tag.setTitle(entry["title"])
            tag.setMediaType(entry["type"])
            tag.setPlot(entry["plot"])
            if entry["year"]:
                tag.setYear(int(entry["year"]))
            item.setProperty("meta", entry["meta"])
            item.setProperty("badge", entry["badge"])
            item.setProperty("arrmada_id", entry["id"])
            items.append(item)
        rail.reset()
        rail.addItems(items)
        if 0 <= position < len(items):
            rail.selectItem(position)
        self._ensure_focus()

    def _ensure_focus(self, target: int = RAIL) -> None:
        """Une liste vide ne peut pas avoir le focus : on le pose dès qu'elle se remplit."""
        try:
            focused = self.getFocusId()
        except RuntimeError:
            focused = 0
        if focused not in (RAIL, BTN_REFRESH, BTN_DIAG, DIAG_CLOSE):
            self.setFocusId(target)

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            if self.getProperty("diag"):
                self._show_diag(False)
            else:
                self.close_window()

    def onClick(self, controlId):
        if controlId == RAIL:
            item = self.getControl(RAIL).getSelectedItem()
            title = item.getLabel() if item else "ArrMada"
            xbmcgui.Dialog().notification(
                title, "Fiche média : arrive en phase 2", ADDON.getAddonInfo("icon"), 2500
            )
        elif controlId == BTN_REFRESH:
            threading.Thread(target=self._refresh, name="arrmada-refresh", daemon=True).start()
        elif controlId == BTN_DIAG:
            self._show_diag(True)
        elif controlId == DIAG_CLOSE:
            self._show_diag(False)

    def _show_diag(self, visible: bool) -> None:
        """Panneau « Diagnostic » : polices, système, temps mesurés."""
        self.setProperty("diag", "1" if visible else "")
        target = DIAG_CLOSE if visible else BTN_DIAG
        # La visibilité est réévaluée à l'image suivante : on réessaie
        # brièvement, sinon le bouton encore masqué refuse le focus.
        for _ in range(10):
            self.setFocusId(target)
            xbmc.sleep(20)
            try:
                if self.getFocusId() == target:
                    return
            except RuntimeError:
                pass


def open_home() -> None:
    """Ouvre l'Accueil et bloque jusqu'à sa fermeture (touche Retour)."""
    window = HomeWindow(XML_FILE, ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

# -*- coding: utf-8 -*-
"""Écran « Téléchargements » de l'appli Kodi ArrMada (phase 2, ADR-003 § 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-downloads.xml.

  - File Radarr + Sonarr rafraîchie toutes les REFRESH_SECONDS par un fil
    d'arrière-plan ; les lignes existantes sont mises à jour sur place (pas
    de clignotement ni de perte de la sélection).
  - Débit estimé d'un passage à l'autre (cf. screens_data.build_downloads).
  - « Tout mettre en pause » / « Tout reprendre » : le backend pilote SABnzbd
    en entier (il ne sait pas mettre UN élément en pause). Pas de suppression
    depuis la TV (ADR-003, décision 1).
  - OK sur une ligne : fiche du titre téléchargé.
"""

from __future__ import annotations

import threading
import time

import xbmc
import xbmcgui

import screens_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-downloads.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
QUEUE = 700
BUTTONS = 710
BTN_PAUSE_ALL = 711
BTN_RESUME_ALL = 712

REFRESH_SECONDS = 5


class DownloadsWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._initialized = False
        self._stop = threading.Event()
        self._busy = threading.Lock()
        self._speeds: dict = {}  # état du passage précédent (débit estimé)
        self._keys: list[str] = []
        self._rows: list[dict] = []
        self._monitor = xbmc.Monitor()

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        self.setProperty("summary", "Chargement de la file…")
        threading.Thread(target=self._loop, name="arrmada-queue", daemon=True).start()

    def _loop(self) -> None:
        while not self._stop.is_set() and not self._monitor.abortRequested():
            self._refresh()
            if self._stop.wait(REFRESH_SECONDS):
                break

    def close_window(self) -> None:
        self._stop.set()
        self.close()

    # ── Données ─────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            self.setProperty("loading", "1")
            started = time.perf_counter()
            items = ArrMadaAPI.get_downloads()
            if self._stop.is_set():
                return
            model, self._speeds = screens_data.build_downloads(items, self._speeds, time.time())
            self._render(model)
            ui.log(
                "Téléchargements", f"{len(model['rows'])} élément(s) en {ui.ms_since(started)} ms"
            )
        except RuntimeError:
            pass  # fenêtre fermée pendant la mise à jour
        finally:
            try:
                self.clearProperty("loading")
            except RuntimeError:
                pass
            self._busy.release()

    def _render(self, model: dict) -> None:
        rows = model["rows"]
        self._rows = rows
        self.setProperty("summary", model["summary"])
        self.setProperty("empty", "" if rows else "Aucun téléchargement dans la file")
        queue = self.getControl(QUEUE)
        keys = [row["key"] for row in rows]
        if keys == self._keys:
            # Même file : mise à jour sur place (pas de clignotement).
            for index, row in enumerate(rows):
                self._fill(queue.getListItem(index), row)
            return
        selected = self._selected_key()
        self._keys = keys
        items = []
        for row in rows:
            item = xbmcgui.ListItem(label=row["title"], offscreen=True)
            self._fill(item, row)
            items.append(item)
        queue.reset()
        queue.addItems(items)
        if selected in keys:
            queue.selectItem(keys.index(selected))
        if items:
            try:
                focused = self.getFocusId()
            except RuntimeError:
                focused = 0
            if focused not in (QUEUE, BTN_PAUSE_ALL, BTN_RESUME_ALL):
                self.setFocusId(QUEUE)
        else:
            ui.focus_when_visible(self, BTN_RESUME_ALL)

    @staticmethod
    def _fill(item: xbmcgui.ListItem, row: dict) -> None:
        item.setLabel(row["title"])
        for key in ("meta", "pct", "bar", "sizes", "eta", "speed", "status", "family", "detail"):
            item.setProperty(key, str(row[key]))

    def _selected_key(self) -> str:
        position = self.getControl(QUEUE).getSelectedPosition()
        return self._keys[position] if 0 <= position < len(self._keys) else ""

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close_window()

    def onClick(self, controlId):
        if controlId == QUEUE:
            self._open_selected()
        elif controlId in (BTN_PAUSE_ALL, BTN_RESUME_ALL):
            ui.run_in_background(self._pause_resume_all, controlId == BTN_PAUSE_ALL)

    def _open_selected(self) -> None:
        position = self.getControl(QUEUE).getSelectedPosition()
        if not 0 <= position < len(self._rows):
            return
        row = self._rows[position]
        if row["family"] == "error" and row["detail"]:
            ui.notify(row["status"], row["detail"], 6000)
        if not row.get("arr_id"):
            return
        import detail_window  # import local : évite une dépendance circulaire

        detail_window.open_detail(
            {
                "kind": row["kind"],
                "arr_id": row["arr_id"],
                "title": row["title"],
                "meta": row["meta"],
            }
        )

    def _pause_resume_all(self, pause: bool) -> None:
        """Pause ou reprise de TOUTE la file SABnzbd (seul mode géré par le backend)."""
        service = (self._rows[0]["service"] if self._rows else "") or "radarr"
        if pause:
            result = ArrMadaAPI.pause_queue_item(service, 0)
        else:
            result = ArrMadaAPI.resume_queue_item(service, 0)
        if result.get("status") != "ok":
            ui.notify("Téléchargements", result.get("message") or "Échec")
        elif pause:
            # Radarr/Sonarr ne relisent SABnzbd qu'environ une fois par minute :
            # les lignes passent à « En pause » avec ce délai, c'est normal.
            ui.notify("SABnzbd en pause", "Toute la file est suspendue", 6000)
        else:
            ui.notify("SABnzbd relancé", "Toute la file reprend", 6000)
        self._refresh()


def open_downloads() -> None:
    window = DownloadsWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
    finally:
        window._stop.set()
        del window

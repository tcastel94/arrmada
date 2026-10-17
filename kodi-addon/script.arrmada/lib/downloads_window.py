# -*- coding: utf-8 -*-
"""Écran « Téléchargements » de l'appli Kodi ArrMada (ADR-005 lot 3 ; ADR-003 § 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-downloads.xml
(générée par kodi-addon/tools/make_downloads_xml.py).

  - « Pour ce soir » (720) : une carte par demande lancée depuis une TV,
    avec l'heure à laquelle ce sera prêt et les étapes du parcours ;
  - la file (700) : le reste des téléchargements Radarr + Sonarr ;
  - tout vient d'un seul appel (GET /api/kodi/downloads/board), refait toutes
    les REFRESH_SECONDS par un fil d'arrière-plan ; les éléments existants sont
    mis à jour sur place (pas de clignotement, la sélection reste) ;
  - OK : menu d'actions (Passer en tête, Pause / Reprendre, Débloquer, Fiche,
    Annuler ma demande, Relancer la recherche) ;
  - « Pause sauf ce soir » / « Tout reprendre » : pause de SABnzbd entier ; les
    demandes TV (priorité Force) continuent pendant la pause.
Débit estimé d'un passage à l'autre (screens_data.build_downloads).
Serveur pas encore à jour (pas de tableau) : l'ancienne file seule.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime

import xbmc
import xbmcgui

import board_data
import screens_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-downloads.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML (vérifié par les tests).
QUEUE = 700
TONIGHT = 720
BUTTONS = 710
BTN_PAUSE_ALL = 711
BTN_RESUME_ALL = 712

REFRESH_SECONDS = 5

_CARD_KEYS = (
    "who", "headline", "detail", "phase", "bar", "poster", "fanart", "hint", "mine",
    "s1", "s1_state", "s2", "s2_state", "s3", "s3_state", "s4", "s4_state",
)  # fmt: skip
_ROW_KEYS = (
    "meta", "pct", "bar", "sizes", "eta_speed", "status", "family", "detail", "hint", "poster",
)  # fmt: skip


class DownloadsWindow(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self._initialized = False
        self._stop = threading.Event()
        self._busy = threading.Lock()
        self._speeds: dict = {}  # état du passage précédent (débit estimé)
        self._row_keys: list = []
        self._card_keys: list = []
        self._rows: list = []
        self._cards: list = []  # cartes brutes du serveur (pour les actions)
        self._prev = 0  # focus avant la dernière touche (voir onAction)
        self._monitor = xbmc.Monitor()

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        self.setProperty("summary", "Chargement de la file…")
        self.setProperty("loading_first", "1")
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

    def _fetch(self) -> dict:
        """Le tableau du serveur ; ancien serveur (404) : la file seule, sans cartes."""
        board = ArrMadaAPI.get_board()
        if isinstance(board, dict) and board.get("code") == 404:
            return {"tonight": [], "queue": ArrMadaAPI.get_downloads(), "sab": None}
        if not isinstance(board, dict) or board.get("status") == "error":
            raise ConnectionError((board or {}).get("message") or "serveur injoignable")
        return board

    def _refresh(self) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            self.setProperty("loading", "1")
            started = time.perf_counter()
            try:
                board = self._fetch()
            except ConnectionError as exc:
                self.setProperty("summary", f"Serveur injoignable : {exc}")
                return
            if self._stop.is_set():
                return
            items = list(board.get("queue") or [])
            model, self._speeds = screens_data.build_downloads(items, self._speeds, time.time())
            board_data.decorate_rows(model["rows"], items)
            now = datetime.now()
            self._cards = list(board.get("tonight") or [])
            cards = [board_data.card_model(card, now) for card in self._cards]
            summary = board_data.summary(self._cards, model["rows"], board.get("sab"))
            self._render(cards, model["rows"], summary)
            ui.log(
                "Téléchargements",
                f"{len(cards)} pour ce soir, {len(model['rows'])} en file "
                f"en {ui.ms_since(started)} ms",
            )
        except RuntimeError:
            pass  # fenêtre fermée pendant la mise à jour
        finally:
            try:
                self.clearProperty("loading")
                self.clearProperty("loading_first")
            except RuntimeError:
                pass
            self._busy.release()

    def _render(self, cards: list, rows: list, summary: str) -> None:
        self._rows = rows
        self.setProperty("summary", summary)
        self.setProperty("empty", "" if rows else "Rien d'autre dans la file")
        self.setProperty(
            "queue_hint", f"{len(rows)} élément(s), après ceux de ce soir" if rows else ""
        )
        self._card_keys = self._fill_list(TONIGHT, cards, self._card_keys, _CARD_KEYS)
        self._row_keys = self._fill_list(
            QUEUE, [dict(r, label=r["title"]) for r in rows], self._row_keys, _ROW_KEYS
        )
        try:
            focused = self.getFocusId()
        except RuntimeError:
            focused = 0
        if focused not in (QUEUE, TONIGHT, BTN_PAUSE_ALL, BTN_RESUME_ALL):
            target = TONIGHT if cards else QUEUE if rows else BTN_RESUME_ALL
            self._prev = target
            ui.focus_when_visible(self, target)

    def _fill_list(self, control_id: int, models: list, old_keys: list, keys: tuple) -> list:
        """Remplit une liste ; même contenu qu'avant : mise à jour sur place."""
        control = self.getControl(control_id)
        new_keys = [m["key"] for m in models]
        if new_keys == old_keys:
            for index, model in enumerate(models):
                self._fill(control.getListItem(index), model, keys)
            return new_keys
        position = control.getSelectedPosition()
        selected = old_keys[position] if 0 <= position < len(old_keys) else ""
        items = []
        for model in models:
            item = xbmcgui.ListItem(label=model["label"], offscreen=True)
            self._fill(item, model, keys)
            items.append(item)
        control.reset()
        control.addItems(items)
        if selected in new_keys:
            control.selectItem(new_keys.index(selected))
        return new_keys

    @staticmethod
    def _fill(item: xbmcgui.ListItem, model: dict, keys: tuple) -> None:
        item.setLabel(model["label"])
        for key in keys:
            item.setProperty(key, str(model.get(key, "")))

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        """Retour ; et la voie « Pour ce soir » vide (masquée) n'arrête pas les flèches.

        Kodi a DÉJÀ déplacé le focus quand ce code s'exécute : « toujours au
        même endroit » après une flèche = la cible était masquée.
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
        target = None
        buttons = (BTN_PAUSE_ALL, BTN_RESUME_ALL)
        if stuck and action_id == xbmcgui.ACTION_MOVE_DOWN and focus in buttons:
            target = QUEUE
        elif stuck and action_id == xbmcgui.ACTION_MOVE_UP and focus == QUEUE:
            target = BTN_RESUME_ALL
        if target is not None:
            self.setFocusId(target)
            focus = target
        self._prev = focus

    def onClick(self, controlId):
        if controlId == TONIGHT:
            self._card_menu()
        elif controlId == QUEUE:
            self._row_menu()
        elif controlId in (BTN_PAUSE_ALL, BTN_RESUME_ALL):
            ui.run_in_background(self._pause_resume_all, controlId == BTN_PAUSE_ALL)

    def _selected(self, control_id: int, data: list):
        position = self.getControl(control_id).getSelectedPosition()
        return data[position] if 0 <= position < len(data) else None

    def _card_menu(self) -> None:
        card = self._selected(TONIGHT, self._cards)
        if not card:
            return
        actions = board_data.card_actions(card)
        op = self._choose(card.get("title") or "", actions)
        if op == "detail":
            self._open_detail(
                "movie" if card.get("service_type") == "radarr" else "tvshow",
                card.get("arr_id"),
                card.get("title") or "",
            )
        elif op == "unstick":
            target = card.get("blocked_download") or {}
            self._unstick(target.get("service_type"), target.get("download_id"), card["title"])
        elif op == "cancel":
            question = (
                f"Annuler « {card.get('title')} » ?[CR]Le téléchargement est retiré de la file. "
                "Rien n'est effacé de la médiathèque."
            )
            if xbmcgui.Dialog().yesno("Annuler ma demande", question):
                ui.run_in_background(self._call, ArrMadaAPI.cancel_request, card["id"])
        elif op == "search":
            ui.run_in_background(self._call, ArrMadaAPI.retry_request, card["id"])

    def _row_menu(self) -> None:
        row = self._selected(QUEUE, self._rows)
        if not row:
            return
        if row["family"] == "error" and row.get("detail"):
            ui.notify(row["status"], row["detail"], 6000)
        op = self._choose(row["title"], row.get("actions") or [])
        if op == "detail":
            self._open_detail(row["kind"], row.get("arr_id"), row["title"])
        elif op == "unstick":
            self._unstick(row["service"], row["download_id"], row["title"])
        elif op in ("top", "pause", "resume"):
            ui.run_in_background(self._call, ArrMadaAPI.queue_action, row["download_id"], op)

    @staticmethod
    def _choose(title: str, actions: list) -> str:
        """Menu des actions possibles (une seule : on la lance directement)."""
        if not actions:
            return ""
        if len(actions) == 1 and actions[0][0] == "detail":
            return "detail"
        index = xbmcgui.Dialog().contextmenu([label for _, label in actions])
        return actions[index][0] if index >= 0 else ""

    def _call(self, func, *args) -> None:
        """Action réseau en arrière-plan, notification, puis rafraîchissement."""
        result = func(*args)
        ok = isinstance(result, dict) and result.get("status") == "ok"
        message = result.get("message") if isinstance(result, dict) else ""
        ui.notify("Téléchargements", message or ("C'est fait" if ok else "Échec"))
        self._refresh()

    def _unstick(self, service_type, download_id, title: str) -> None:
        if not service_type or not download_id:
            ui.notify(title or "Débloquer", "Téléchargement introuvable dans la file")
            return
        import unstick_window  # import local : écran ouvert à la demande

        if unstick_window.open_unstick(service_type, download_id, title) is not None:
            ui.run_in_background(self._refresh)

    @staticmethod
    def _open_detail(kind: str, arr_id, title: str) -> None:
        if not arr_id:
            return
        import detail_window  # import local : évite une dépendance circulaire

        detail_window.open_detail({"kind": kind, "arr_id": arr_id, "title": title})

    def _pause_resume_all(self, pause: bool) -> None:
        """Pause ou reprise de TOUT SABnzbd (les demandes TV, en Force, continuent)."""
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
            ui.notify("SABnzbd en pause", "Sauf ce qui est lancé pour ce soir", 6000)
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

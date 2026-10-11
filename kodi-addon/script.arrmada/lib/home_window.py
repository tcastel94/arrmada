# -*- coding: utf-8 -*-
"""Écran « Accueil » de l'appli Kodi ArrMada (ADR-003, phases 0 et 2).

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
« Diagnostic » et écrits dans kodi.log (préfixe [ArrMada]).

Télécommande (Shield et toute télécommande Android TV) :
  OK                 fiche du titre (écran « Fiche média »)
  OK maintenu / Menu actions rapides : lire, fiche, chercher une meilleure version
                     (Kodi traduit l'appui long sur OK en « menu contextuel »)
  Lecture/Pause      lit le film (ou ouvre la série) dans la médiathèque Kodi
  Bandeau            Rechercher, Téléchargements, Salon, Actualiser, Diagnostic
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import xbmc
import xbmcgui

import home_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-home.xml"

# Identifiants des contrôles : DOIVENT correspondre au XML.
# (Vérifié automatiquement par kodi-addon/tests/test_home_window_xml.py.)
RAIL = 100  # rangée d'affiches « Ajouts récents »
SERVICES = 300  # pastilles d'état des services
BUTTONS = 400  # boutons du bandeau (groupe)
BTN_REFRESH = 401
BTN_DIAG = 402
BTN_SEARCH = 403
BTN_DOWNLOADS = 404
BTN_SALON = 405
DIAG_CLOSE = 901
DL_PROGRESS = (211, 221, 231)  # barres des 3 emplacements de téléchargement
STORAGE_PROGRESS = 251
FOCUSABLE = (RAIL, BTN_SEARCH, BTN_DOWNLOADS, BTN_SALON, BTN_REFRESH, BTN_DIAG, DIAG_CLOSE)

REFRESH_SECONDS = 20  # le backend met déjà le tableau de bord en cache 15 s
ANIM_FRAMES = 22  # compteurs et barres : 22 images × 33 ms ≈ 0,7 s
ANIM_FRAME_MS = 33
INTRO_SECONDS = 2.4  # durée de l'intro (logo qui se construit), cf. XML
# Propriété globale (fenêtre Home de Kodi, id 10000) : l'intro ne se joue
# qu'une fois par session Kodi ; les ouvertures suivantes vont droit au but.
INTRO_SEEN = "ArrMada.IntroSeen"


def _log(message: str, level: int = xbmc.LOGINFO) -> None:
    ui.log("Accueil", message, level)


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
        # Dernières valeurs affichées, point de départ des animations suivantes.
        self._shown: dict[str, float] = {}
        self._anim_gen = 0  # chaque nouvelle animation annule la précédente
        self._intro_running = False
        self._revealed = threading.Event()  # levé quand l'accueil est visible

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def onInit(self):
        # onInit est rappelé quand on revient d'une autre fenêtre (fiche,
        # lecture…) : ne pas tout refaire (ni relancer un second fil).
        if self._initialized:
            return
        self._initialized = True

        self.setProperty("icon", ui.ADDON.getAddonInfo("icon"))
        self.setProperty("version", ui.ADDON.getAddonInfo("version"))
        self.setProperty("skin", xbmc.getSkinDir())
        self.setProperty("server_url", ArrMadaAPI.get_config()["url"])
        self.setProperty("greeting", home_data.greeting(datetime.now().hour))
        self.setProperty("device_label", _device_label())

        if xbmcgui.Window(10000).getProperty(INTRO_SEEN):
            self._revealed.set()  # pas d'intro : la cascade « WindowOpen » suffit
        else:
            self._intro_running = True
            threading.Thread(target=self._intro, name="arrmada-intro", daemon=True).start()

        cached = home_data.load_cache(ui.cache_dir())
        if cached:
            started = time.perf_counter()
            self._render(cached, source="cache")
            self.setProperty("perf_cache", ui.fmt_ms(ui.ms_since(started)))
        else:
            self.setProperty("perf_cache", "aucun cache (1re ouverture)")
        open_ms = ui.ms_since(self._opened_at)
        self.setProperty("perf_open", ui.fmt_ms(open_ms))
        _log(f"ouverture en {open_ms} ms ({'cache' if cached else 'sans cache'})")

        threading.Thread(target=self._loop, name="arrmada-home", daemon=True).start()

    def _loop(self) -> None:
        """Fil d'arrière-plan : rafraîchit, attend, recommence."""
        while not self._stop.is_set() and not self._monitor.abortRequested():
            self._refresh()
            # wait() rend la main tout de suite si la fenêtre se ferme.
            if self._stop.wait(REFRESH_SECONDS):
                break

    def _intro(self) -> None:
        """Laisse l'intro se jouer, puis dévoile l'accueil (sauf fermeture avant)."""
        if not self._stop.wait(INTRO_SECONDS):
            self._end_intro()

    def _end_intro(self) -> None:
        """Fin de l'intro (minuterie ou touche) : la surimpression s'efface et
        les sections de l'accueil apparaissent en cascade (« revealed »)."""
        if not self._intro_running:
            return
        self._intro_running = False
        try:
            self.setProperty("intro_done", "1")
            self.setProperty("revealed", "1")
            xbmcgui.Window(10000).setProperty(INTRO_SEEN, "1")
        except RuntimeError:
            pass  # fenêtre déjà fermée
        self._revealed.set()

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
            recent = ArrMadaAPI.get_recent_media_or_none()
            net_ms = ui.ms_since(started)
            if self._stop.is_set():
                return

            # Les DEUX appels doivent réussir pour remplacer l'affichage (et le
            # cache) : sinon une panne entre les deux viderait la rangée.
            failed = not isinstance(dashboard, dict) or dashboard.get("status") == "error"
            if failed or recent is None:
                message = dashboard.get("message") if isinstance(dashboard, dict) else ""
                if not failed:
                    message = "ajouts récents indisponibles"
                self.setProperty("error", message or "Serveur ArrMada injoignable")
                described = home_data.describe_error(dashboard if failed else None)
                for key in ("title", "short", "hint"):
                    self.setProperty(f"error_{key}", described[key])
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
            render_ms = ui.ms_since(started)
            self.setProperty("perf_net", ui.fmt_ms(net_ms))
            self.setProperty("perf_render", ui.fmt_ms(render_ms))
            _log(f"réseau {net_ms} ms, rendu {render_ms} ms, {len(model['recent'])} affiches")

            try:
                home_data.save_cache(ui.cache_dir(), model)
            except OSError as exc:
                _log(f"cache non écrit : {exc}", xbmc.LOGWARNING)
        except RuntimeError as exc:
            # Fenêtre fermée pendant la mise à jour : rien à faire.
            _log(f"rafraîchissement interrompu : {exc}", xbmc.LOGDEBUG)
        finally:
            try:
                self.clearProperty("loading")
            except RuntimeError:
                pass
            self._busy.release()

    # ── Affichage ───────────────────────────────────────────────────────────

    def _render(self, model: dict, source: str) -> None:
        kpis = model.get("kpis") or {}
        raw = model.get("kpis_raw") or {}
        for key in ("movies_hint", "series_hint", "storage_hint", "downloads_hint"):
            self.setProperty(f"kpi_{key}", str(kpis.get(key, "")))

        # Compteurs qui défilent jusqu'à leur valeur (comme sur la web app).
        tweens = [
            self._tween_label(key, raw.get(key), str(kpis.get(key, "")))
            for key in ("movies", "series", "downloads")
        ]
        if raw.get("storage") is not None:  # 42.1 (+ unité « To »)
            tweens.append(
                self._tween_label(
                    "storage", raw["storage"], str(kpis["storage"]), unit=raw["storage_unit"]
                )
            )
        else:
            self.setProperty("kpi_storage", str(kpis.get("storage", "")))
        tweens.append(self._tween_bar(STORAGE_PROGRESS, raw.get("storage_pct")))
        self.setProperty("summary", model.get("summary", ""))
        self.setProperty("source", source)
        self._last_fetch = model.get("fetched_at", "")
        self.setProperty(
            "updated",
            home_data.age_label(model.get("fetched_at", ""), datetime.now(timezone.utc)),
        )
        tweens += self._render_downloads(
            model.get("downloads") or [], int(model.get("downloads_more") or 0)
        )
        self._render_services(model.get("services") or [], int(model.get("services_active") or 0))
        self._render_rail(model.get("recent") or [])
        self.setProperty("ready", "1")
        self._animate([tw for tw in tweens if tw])

    # ── Animations (compteurs, barres) ──────────────────────────────────────
    # Kodi n'anime pas un texte ni une barre de progression depuis le XML :
    # un petit fil pose ~22 valeurs intermédiaires (courbe « ease-out »).

    def _tween_label(self, key: str, value, final_text: str, unit: str = "") -> dict | None:
        """Prépare l'animation d'un compteur ; None si la valeur n'a pas changé."""
        target = float(value or 0)
        start = self._shown.get(key, 0.0)
        self._shown[key] = target
        if start == target:
            self.setProperty(f"kpi_{key}", final_text)
            return None
        return {
            "kind": "label",
            "target": f"kpi_{key}",
            "from": start,
            "to": target,
            "text": final_text,
            "unit": unit,
        }

    def _tween_bar(self, control_id: int, pct) -> dict | None:
        """Prépare le remplissage animé d'une barre de progression."""
        target = float(pct or 0)
        start = self._shown.get(f"bar{control_id}", 0.0)
        self._shown[f"bar{control_id}"] = target
        if start == target:
            self.getControl(control_id).setPercent(target)
            return None
        return {"kind": "bar", "target": control_id, "from": start, "to": target}

    def _animate(self, tweens: list[dict]) -> None:
        self._anim_gen += 1
        if tweens:
            threading.Thread(
                target=self._run_tweens, args=(self._anim_gen, tweens), daemon=True
            ).start()

    def _run_tweens(self, generation: int, tweens: list[dict]) -> None:
        # Pendant l'intro, les compteurs attendent d'être visibles pour défiler,
        # en même temps que les tuiles apparaissent.
        if not self._revealed.is_set():
            self._revealed.wait(INTRO_SECONDS + 1)
            xbmc.sleep(250)
        try:
            for frame in range(1, ANIM_FRAMES + 1):
                if generation != self._anim_gen or self._stop.is_set():
                    return  # remplacée par une animation plus récente, ou fenêtre fermée
                progress = home_data.ease_out_cubic(frame / ANIM_FRAMES)
                last = frame == ANIM_FRAMES
                for tween in tweens:
                    value = tween["from"] + (tween["to"] - tween["from"]) * progress
                    if tween["kind"] == "bar":
                        self.getControl(tween["target"]).setPercent(value)
                    elif last:
                        self.setProperty(tween["target"], tween["text"])  # texte exact
                    elif tween["unit"]:
                        text = f"{home_data.fmt_decimal(value)}{home_data.NBSP}{tween['unit']}"
                        self.setProperty(tween["target"], text)
                    else:
                        self.setProperty(tween["target"], home_data.fmt_int(round(value)))
                xbmc.sleep(ANIM_FRAME_MS)
        except RuntimeError:
            pass  # fenêtre fermée pendant l'animation

    def _render_downloads(self, downloads: list[dict], more: int) -> list:
        self.setProperty("dl_count", str(len(downloads)))
        self.setProperty("dl_more", f"+ {more} autre(s)" if more else "")
        tweens = []
        for index, control_id in enumerate(DL_PROGRESS):
            slot = f"dl{index + 1}"
            if index < len(downloads):
                self.setProperty(f"{slot}_title", downloads[index]["title"])
                self.setProperty(f"{slot}_meta", downloads[index]["meta"])
                tweens.append(self._tween_bar(control_id, downloads[index]["pct"]))
            else:
                self.clearProperty(f"{slot}_title")
                self.clearProperty(f"{slot}_meta")
        return tweens

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
            item.setProperty("kind", entry["type"])  # movie | tvshow
            item.setProperty("tmdb_id", entry.get("tmdb_id", ""))
            item.setProperty("tvdb_id", entry.get("tvdb_id", ""))
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
        if focused not in FOCUSABLE:
            self.setFocusId(target)

    # ── Télécommande ────────────────────────────────────────────────────────

    def onAction(self, action):
        if self._intro_running:
            self._end_intro()  # n'importe quelle touche passe l'intro
            return
        action_id = action.getId()
        if action_id in ui.BACK_ACTIONS:
            if self.getProperty("diag"):
                self._show_diag(False)
            else:
                self.close_window()
            return
        try:
            on_rail = self.getFocusId() == RAIL and not self.getProperty("diag")
        except RuntimeError:
            on_rail = False
        if on_rail and action_id in ui.MENU_ACTIONS:
            self._quick_actions()
        elif on_rail and action_id in ui.PLAY_ACTIONS:
            entry = self._selected()
            if entry:
                ui.play_entry(entry)

    def onClick(self, controlId):
        if controlId == RAIL:
            self._open_detail()
        elif controlId == BTN_SEARCH:
            ui.open_search()
        elif controlId == BTN_DOWNLOADS:
            import downloads_window  # import à la demande : ouverture de l'accueil plus rapide

            downloads_window.open_downloads()
        elif controlId == BTN_SALON:
            import salon_window

            salon_window.open_salon()
        elif controlId == BTN_REFRESH:
            threading.Thread(target=self._refresh, name="arrmada-refresh", daemon=True).start()
        elif controlId == BTN_DIAG:
            self._show_diag(True)
        elif controlId == DIAG_CLOSE:
            self._show_diag(False)

    # ── Actions sur l'affiche sélectionnée ─────────────────────────────────

    def _selected(self) -> dict | None:
        """Titre, année, identifiants et visuels de l'affiche sélectionnée."""
        item = self.getControl(RAIL).getSelectedItem()
        if not item:
            return None
        kind_prefix, _, arr_id = item.getProperty("arrmada_id").partition(":")
        return {
            "title": item.getLabel(),
            "year": item.getVideoInfoTag().getYear(),
            "kind": item.getProperty("kind") or "movie",
            "arr_id": arr_id,
            "tmdb_id": item.getProperty("tmdb_id"),
            "tvdb_id": item.getProperty("tvdb_id"),
            "poster": item.getArt("poster"),
            "fanart": item.getArt("fanart"),
            "clearlogo": item.getArt("clearlogo"),
            "plot": item.getVideoInfoTag().getPlot(),
            "meta": item.getProperty("meta"),
        }

    def _open_detail(self) -> None:
        entry = self._selected()
        if not entry or not entry["arr_id"]:
            return
        import detail_window  # import à la demande : ouverture de l'accueil plus rapide

        detail_window.open_detail(entry)

    def _quick_actions(self) -> None:
        """Appui long sur OK : petit menu d'actions (aucune action destructrice, ADR-003)."""
        entry = self._selected()
        if not entry:
            return
        is_movie = entry["kind"] == "movie"
        choices = [
            ("play", "Lire" if is_movie else "Ouvrir la série"),
            ("details", "Fiche détaillée"),
            ("search", "Chercher une meilleure version"),
        ]
        index = xbmcgui.Dialog().contextmenu([label for _, label in choices])
        if index < 0:
            return
        action = choices[index][0]
        if action == "play":
            ui.play_entry(entry)
        elif action == "details":
            self._open_detail()
        else:
            ui.run_in_background(ui.search_release, entry)

    def _show_diag(self, visible: bool) -> None:
        """Panneau « Diagnostic » : polices, système, temps mesurés."""
        self.setProperty("diag", "1" if visible else "")
        ui.focus_when_visible(self, DIAG_CLOSE if visible else BTN_DIAG)


def _device_label() -> str:
    """Ligne « Appareil » du Diagnostic : TV appairée ou ancien mode."""
    import device
    import pairing_data

    info = device.load()
    if not device.token_for(ArrMadaAPI.get_config()["url"]):
        return "non appairé (mot de passe admin)"
    return pairing_data.device_summary(info) or "appairé"


def open_home() -> None:
    """Ouvre l'Accueil et bloque jusqu'à sa fermeture (touche Retour)."""
    window = HomeWindow(XML_FILE, ui.ADDON.getAddonInfo("path"), "Default", "1080i")
    try:
        window.doModal()
    finally:
        window._stop.set()
        xbmcgui.Window(10000).setProperty(INTRO_SEEN, "1")
        del window

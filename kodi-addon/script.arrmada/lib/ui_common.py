# -*- coding: utf-8 -*-
"""Briques communes aux écrans sur mesure de l'appli Kodi (ADR-003).

Accueil, Fiche média, Téléchargements et Salon partagent ici :
  - les touches de la télécommande (Retour, menu contextuel, Lecture) ;
  - les notifications, le journal et les appels JSON-RPC à Kodi ;
  - la lecture d'un titre depuis la médiathèque Kodi DE CET APPAREIL, en
    appliquant d'abord le préréglage audio Yamaha de sa pièce (ADR § 6) ;
  - la bande-annonce (add-on YouTube), la recherche d'une meilleure version
    et des sous-titres (Radarr / Sonarr / Bazarr via le backend).

Les appels réseau (backend) sont faits dans des fils d'arrière-plan par les
appelants : rien ici ne doit figer l'interface.
"""

from __future__ import annotations

import json
import os
import threading
import time

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

import home_data
from api import ArrMadaAPI

ADDON = xbmcaddon.Addon("script.arrmada")

BACK_ACTIONS = (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU)
# « Menu contextuel » : appui long sur OK (Android TV) ou touche Menu.
MENU_ACTIONS = (xbmcgui.ACTION_CONTEXT_MENU,)
# Touche Lecture/Pause (selon le modèle : lecture seule, pause seule, ou les deux).
PLAY_ACTIONS = (xbmcgui.ACTION_PLAYER_PLAY, xbmcgui.ACTION_PLAYER_PLAYPAUSE, xbmcgui.ACTION_PAUSE)


# ─────────────────────────────────────────────────────────────────────────────
# Journal, mesures, notifications
# ─────────────────────────────────────────────────────────────────────────────


def log(screen: str, message: str, level: int = xbmc.LOGINFO) -> None:
    xbmc.log(f"[ArrMada] {screen} : {message}", level=level)


def ms_since(since: float) -> int:
    return round((time.perf_counter() - since) * 1000)


def fmt_ms(value: int) -> str:
    return f"{value} ms" if value else "< 1 ms"


def notify(title: str, message: str, ms: int = 3500) -> None:
    """Bulle : en bas à droite sur un écran ArrMada, bulle Kodi ailleurs (lib/toast.py)."""
    import toast

    toast.post(title, message, ms=ms)


def platform_name() -> str:
    """« Kodi 21.1 · Android » : aide à reconnaître la TV dans la web app."""
    import pairing_data

    name = next(
        (
            label
            for key, label in pairing_data.PLATFORMS
            if xbmc.getCondVisibility(f"System.Platform.{key}")
        ),
        "",
    )
    return pairing_data.platform_label(xbmc.getInfoLabel("System.BuildVersion"), name)


def cache_dir() -> str:
    """special://profile/addon_data/script.arrmada/cache/ en chemin réel."""
    return os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")), "cache")


def jsonrpc(method: str, params: dict) -> dict:
    """Appel JSON-RPC local à Kodi (médiathèque, lecteur) ; {} en cas d'erreur."""
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    except ValueError:
        return {}
    if "error" in response:
        log("JSON-RPC", f"{method} refusé : {response['error']}", xbmc.LOGWARNING)
    return response.get("result") or {}


def focus_when_visible(window: xbmcgui.Window, control_id: int) -> None:
    """Pose le focus sur un contrôle qui vient d'apparaître.

    La visibilité est réévaluée à l'image suivante : on réessaie brièvement,
    sinon le contrôle encore masqué refuse le focus.
    """
    for _ in range(10):
        window.setFocusId(control_id)
        xbmc.sleep(20)
        try:
            if window.getFocusId() == control_id:
                return
        except RuntimeError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Lecture depuis la médiathèque Kodi + préréglage audio de la pièce
# ─────────────────────────────────────────────────────────────────────────────
# `entry` : {"title", "year", "kind" (movie|tvshow), "tmdb_id", "tvdb_id",
#            "audio_codec"?, "audio_channels"?}


def find_in_library(entry: dict) -> int | None:
    """ID Kodi (movieid / tvshowid) du titre, ou None s'il n'est pas importé ici."""
    is_movie = entry.get("kind", "movie") == "movie"
    method, key, unique, list_key = (
        ("VideoLibrary.GetMovies", "movieid", "tmdb", "movies")
        if is_movie
        else ("VideoLibrary.GetTVShows", "tvshowid", "tvdb", "tvshows")
    )
    result = jsonrpc(
        method,
        {
            "filter": home_data.library_filter(entry["title"], entry.get("year") or 0),
            "properties": ["title", "year", "uniqueid"],
        },
    )
    return home_data.pick_library_match(
        result.get(list_key) or [],
        entry["title"],
        entry.get("year") or 0,
        key,
        unique,
        entry.get("tmdb_id" if is_movie else "tvdb_id") or "",
    )


def room() -> str:
    """Pièce de cet appareil : « salon », « cinema » ou « bureau ».

    Celle choisie à l'appairage dans la web app si la TV est appairée,
    sinon le réglage « Profil de la pièce » de l'add-on.
    """
    import device  # import local : ui_common reste léger à charger

    paired = device.room()
    if paired:
        return paired
    value = (ADDON.getSetting("room_profile") or "cinema").strip().lower()
    return value if value in ("salon", "cinema") else "cinema"


def apply_room_preset(entry: dict) -> None:
    """Préréglage Yamaha de la pièce, en arrière-plan (l'ampli peut être lent).

    Rien au bureau (1.19.1) : pas d'ampli. Sans ce test, le serveur aurait
    réglé le premier ampli actif, celui du salon.
    """
    import device

    if not device.has_amp():
        return

    def _apply() -> None:
        result = ArrMadaAPI.yamaha_apply_preset(
            room(),
            "movie" if entry.get("kind") == "movie" else "series",
            entry.get("audio_codec") or None,
            entry.get("audio_channels") or None,
        )
        if result.get("status") == "error":
            log(
                "Salon",
                f"préréglage non appliqué : {result.get('message') or result}",
                xbmc.LOGWARNING,
            )

    threading.Thread(target=_apply, name="arrmada-preset", daemon=True).start()


def play_entry(entry: dict, resume=None) -> bool:
    """Lit le film ou ouvre l'écran Série d'ArrMada (ADR-004, phase 4.1).

    Film : « Reprendre à … » / « Depuis le début » s'il a été commencé
    (`resume` : True / False pour ne pas demander). Série : l'écran Série
    (saisons → épisodes) remplace l'écran Vidéos de SiLVO ; `entry["season"]`
    y sélectionne une saison.

    Renvoie False (et prévient) si le titre n'est pas dans la médiathèque
    Kodi de cet appareil : mieux vaut ne rien lancer que le mauvais film.
    """
    found = find_in_library(entry)
    if found is None:
        notify(entry["title"], "Pas (encore) dans la médiathèque Kodi de cet appareil")
        return False
    if entry.get("kind", "movie") == "movie":
        import kodi_library  # import local : évite un import circulaire

        return kodi_library.play_movie(found, entry, resume=resume)
    import series_window

    series_window.open_series(entry, found, season=entry.get("season"))
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Bande-annonce, recherche, sous-titres
# ─────────────────────────────────────────────────────────────────────────────


def play_trailer(youtube_id: str, title: str) -> None:
    """Bande-annonce via l'add-on YouTube (ADR-003, décision 2)."""
    if not youtube_id:
        notify(title, "Pas de bande-annonce connue pour ce titre")
        return
    if not xbmc.getCondVisibility("System.HasAddon(plugin.video.youtube)"):
        # Pas d'add-on YouTube sur cette TV : la bande-annonce sur le téléphone
        # (QR code, phase 3), et ce qu'il faut pour la voir ici.
        import qr_window

        qr_window.show_qr(
            f"Bande-annonce · {title}" if title else "Bande-annonce",
            "Vise le QR code pour la voir sur ton téléphone. Pour la lire sur la TV : "
            "installe l'add-on YouTube de Kodi, avec ta propre clé API Google.",
            youtube=youtube_id,
        )
        return
    xbmc.executebuiltin(f"PlayMedia(plugin://plugin.video.youtube/play/?video_id={youtube_id})")


def search_release(entry: dict) -> None:
    """Demande à Radarr/Sonarr une meilleure version (à lancer dans un fil)."""
    notify(entry["title"], "Recherche d'une meilleure version…", 2500)
    payload = {
        "title": entry["title"],
        "media_type": "movie" if entry.get("kind", "movie") == "movie" else "series",
    }
    for key in ("tmdb_id", "tvdb_id"):
        if entry.get(key):
            payload[key] = entry[key]
    result = ArrMadaAPI.trigger_search(payload)
    ok = result.get("status") == "ok"
    notify(
        entry["title"],
        result.get("message") or ("Recherche lancée" if ok else "Échec de la recherche"),
    )


def search_subtitles(entry: dict) -> None:
    """Demande à Bazarr des sous-titres (films ; à lancer dans un fil)."""
    notify(entry["title"], "Recherche de sous-titres…", 2500)
    payload = {"title": entry["title"], "media_type": "movie"}
    if entry.get("tmdb_id"):
        payload["tmdb_id"] = entry["tmdb_id"]
    result = ArrMadaAPI.trigger_subtitles(payload)
    ok = result.get("status") == "ok"
    notify(
        entry["title"], result.get("message") or ("Sous-titres demandés" if ok else "Échec Bazarr")
    )


def ask_query(heading: str = "ArrMada : rechercher un film ou une série") -> str:
    """Clavier de Kodi (sur Android, son bouton micro permet de dicter)."""
    return (xbmcgui.Dialog().input(heading) or "").strip()


def open_search() -> None:
    """Recherche : résultats dans la grille ArrMada (ADR-004, phase 4.3), plus dans SiLVO."""
    query = ask_query()
    if query:
        import grid_window  # import local : évite un import circulaire

        grid_window.open_grid("search", query=query)


def run_in_background(target, *args) -> None:
    threading.Thread(target=target, args=args, daemon=True).start()


# Levé à la fin du script : les fils qui attendent quelque chose (début de
# lecture…) s'arrêtent au lieu d'attendre leur délai.
SHUTDOWN = threading.Event()


def join_threads(timeout: float = 8.0) -> None:
    """Attend la fin des fils d'arrière-plan avant de rendre la main à Kodi.

    Kodi peut se fermer brutalement (erreur de segmentation) quand un script
    se termine alors qu'un de ses fils tourne encore : incident 1.7.0, et
    reproduit sur le banc le 11/10/2026 à la fin de l'appairage (le fil qui
    ferme la fenêtre vivait encore ; journal : « waiting on thread », puis
    plantage, deux passages sur trois). Analogie : un `wait` en fin de script
    shell pour ne pas laisser de processus orphelins.
    """
    SHUTDOWN.set()
    deadline = time.time() + timeout
    current = threading.current_thread()
    for thread in threading.enumerate():
        if thread is current or thread is threading.main_thread() or not thread.is_alive():
            continue
        thread.join(max(0.0, deadline - time.time()))
    left = [
        t.name
        for t in threading.enumerate()
        if t is not current and t is not threading.main_thread() and t.is_alive()
    ]
    if left:
        log("Fils", f"encore actifs à la fin du script : {left}", xbmc.LOGWARNING)

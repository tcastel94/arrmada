# -*- coding: utf-8 -*-
"""ArrMada Video Plugin & Overseerr Discovery for Kodi."""

from __future__ import annotations

import sys
import os
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import show_notification, confirm_dialog
import search_media

ADDON = xbmcaddon.Addon("script.arrmada")
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
PLUGIN_URL = sys.argv[0] if len(sys.argv) > 0 else "plugin://script.arrmada/"


def add_dir(name: str, action: str, icon: str = "", fanart: str = "", params: dict = None, is_folder: bool = True):
    """Add a directory folder item."""
    query = {"action": action}
    if params:
        query.update(params)
    url = f"{PLUGIN_URL}?{urllib.parse.urlencode(query)}"
    li = xbmcgui.ListItem(label=name)
    art = {}
    if icon:
        art["icon"] = icon
        art["thumb"] = icon
    if fanart:
        art["fanart"] = fanart
    if art:
        li.setArt(art)
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=is_folder)


def add_media_item(item: dict):
    """Add a rich media card item with poster, synopsis, fanart, rating."""
    title = item.get("title") or "Sans titre"
    year = item.get("year")
    mtype = item.get("type", "movie")
    in_lib = item.get("in_library", False)
    plot = item.get("overview") or "Aucun synopsis disponible."
    poster = item.get("poster_url") or ""
    backdrop = item.get("backdrop_url") or poster
    rating = item.get("rating") or 0.0

    # Badge in title
    badge = " [✅ En médiathèque]" if in_lib else " [➕ Demander]"
    year_str = f" ({year})" if year else ""
    display_title = f"{title}{year_str}{badge}"

    li = xbmcgui.ListItem(label=display_title)

    # Set Posters, Fanart & Thumbnails
    art_dict = {}
    if poster:
        art_dict["poster"] = poster
        art_dict["thumb"] = poster
        art_dict["icon"] = poster
    if backdrop:
        art_dict["fanart"] = backdrop
    if art_dict:
        li.setArt(art_dict)

    # Set Video Info (synopsis, year, rating, mediatype)
    video_info = {
        "title": title,
        "plot": plot,
        "mediatype": "movie" if mtype == "movie" else "tvshow",
    }
    if year:
        try:
            video_info["year"] = int(year)
        except Exception:
            pass
    if rating:
        try:
            video_info["rating"] = float(rating)
        except Exception:
            pass

    try:
        li.setInfo("video", video_info)
    except Exception:
        pass

    params = {
        "action": "media_details",
        "title": title,
        "type": mtype,
        "tmdb_id": str(item.get("tmdb_id") or ""),
        "tvdb_id": str(item.get("tvdb_id") or ""),
        "in_library": "1" if in_lib else "0",
        "arr_id": str(item.get("arr_id") or ""),
        "overview": plot,
        "poster_url": poster,
        "year": str(year or ""),
    }
    url = f"{PLUGIN_URL}?{urllib.parse.urlencode(params)}"
    xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=False)


def show_root_menu():
    """Build the main category menu."""
    xbmcplugin.setPluginCategory(HANDLE, "ArrMada")
    xbmcplugin.setContent(HANDLE, "files")

    # Aperçu de la future appli (ADR-003, phase 0) : fenêtre sur mesure.
    # Raccourci possible depuis le menu de SiLVO :
    #   RunPlugin(plugin://script.arrmada/?action=home)
    add_dir("[NOUVEAU]        Accueil ArrMada (apercu v2)", "home", is_folder=False)
    add_dir("[RECHERCHE]      Rechercher un film ou une serie...", "search_input", is_folder=False)
    add_dir("[DECOUVERTE]     Tendances TMDB & Ajout 1-Clic", "discovery", is_folder=False)
    add_dir("[FILMS]          Films Tendances & Populaires", "trending_movies")
    add_dir("[SERIES]         Series Tendances & Populaires", "trending_series")
    add_dir("[SUGGESTIONS]    Recommandations intelligentes", "recommendations")
    add_dir("[MISSION CTRL]   Console & Sante de la Stack (HUD)", "dashboard_popup", is_folder=False)
    add_dir("[TELECHARG.]     Telechargements actifs (Gestion / Annulation)", "downloads", is_folder=False)
    add_dir("[MAINTENANCE]    Assistant Maintenance du NAS (Orphelins / Scan / Clean)", "maintenance", is_folder=False)
    add_dir("[PARAMETRES]     Parametres ArrMada", "settings", is_folder=False)

    xbmcplugin.endOfDirectory(HANDLE)





def show_trending_movies():
    """Show trending movies with covers and plots."""
    xbmcplugin.setPluginCategory(HANDLE, "Films Tendances")
    xbmcplugin.setContent(HANDLE, "movies")

    data = ArrMadaAPI.get_recommendations()
    movies = data.get("trending_movies", [])

    if not movies:
        show_notification("ArrMada", "Aucun film tendance récupéré", is_error=True)
    else:
        for m in movies:
            add_media_item(m)

    xbmcplugin.endOfDirectory(HANDLE)


def show_trending_series():
    """Show trending series with covers and plots."""
    xbmcplugin.setPluginCategory(HANDLE, "Séries Tendances")
    xbmcplugin.setContent(HANDLE, "tvshows")

    data = ArrMadaAPI.get_recommendations()
    series = data.get("trending_series", [])

    if not series:
        show_notification("ArrMada", "Aucune série tendance récupérée", is_error=True)
    else:
        for s in series:
            add_media_item(s)

    xbmcplugin.endOfDirectory(HANDLE)


def show_recommendations():
    """Show library-based recommendations with covers."""
    xbmcplugin.setPluginCategory(HANDLE, "Recommandations")
    xbmcplugin.setContent(HANDLE, "movies")

    data = ArrMadaAPI.get_recommendations()
    because = data.get("because_you_have", [])

    items_added = 0
    for block in because:
        rec_items = block.get("recommendations", [])
        for it in rec_items:
            add_media_item(it)
            items_added += 1

    if items_added == 0:
        # Fallback to wanted list
        wanted = data.get("wanted", [])
        for w in wanted:
            add_media_item(w)

    xbmcplugin.endOfDirectory(HANDLE)


def handle_search_results(query: str):
    """Display media search results with rich posters and metadata."""
    xbmcplugin.setPluginCategory(HANDLE, f"Résultats pour : {query}")
    xbmcplugin.setContent(HANDLE, "movies")

    results = ArrMadaAPI.lookup_media(query)
    if not results:
        show_notification("ArrMada", f"Aucun résultat pour '{query}'", is_error=False)
    else:
        for it in results:
            add_media_item(it)

    xbmcplugin.endOfDirectory(HANDLE)


def show_media_details_dialog(params: dict):
    """Handle click on a poster: show detail popup and launch 3-step wizard or release picker."""
    title = params.get("title", "")
    mtype = params.get("type", "movie")
    in_lib = params.get("in_library") == "1"
    arr_id_str = params.get("arr_id", "")
    arr_id = int(arr_id_str) if arr_id_str.isdigit() else None
    plot = params.get("overview", "Aucun synopsis.")
    year = params.get("year", "")
    tmdb_id = params.get("tmdb_id") or None
    tvdb_id = params.get("tvdb_id") or None

    header = f"{title}"
    if year:
        header += f" ({year})"

    status_tag = "✅ Déjà dans votre médiathèque" if in_lib else "➕ Non possédé"

    options = []
    if in_lib and arr_id:
        options.append(("🎯 Choisir une Release manuellement (Torrent vs Usenet)", "pick_release"))
        options.append(("🚀 Forcer la recherche automatique d'une meilleure release", "auto_search"))
        options.append(("📖 Lire le synopsis complet", "show_plot"))
    else:
        options.append(("🎛️ Demander & Télécharger (Qualité 1080p/4K, Dossier, Releases)", "add_wizard"))
        options.append(("📖 Lire le synopsis complet", "show_plot"))

    choice = xbmcgui.Dialog().select(f"🏴‍☠️ {header} — {status_tag}", [o[0] for o in options])
    if choice < 0:
        return

    action = options[choice][1]

    if action == "show_plot":
        xbmcgui.Dialog().textviewer(f"Synopsis : {title}", plot)

    elif action == "pick_release" and arr_id:
        search_media.pick_and_grab_release(mtype, arr_id, title)

    elif action == "auto_search":
        show_notification("ArrMada", f"Recherche en cours pour {title}...", time_ms=2500)
        res = ArrMadaAPI.trigger_search({"title": title, "media_type": mtype})
        if res.get("status") == "ok":
            show_notification("ArrMada", res.get("message") or "Recherche lancée !", is_error=False, time_ms=4500)
        else:
            show_notification("ArrMada", res.get("message") or "Erreur", is_error=True, time_ms=5000)

    elif action == "add_wizard":
        # 3-step wizard
        opts = ArrMadaAPI.get_media_options(mtype)
        profiles = opts.get("profiles", [])
        folders = opts.get("root_folders", [])

        if not profiles:
            show_notification("ArrMada", "Aucun profil de qualité configuré", is_error=True)
            return
        if not folders:
            show_notification("ArrMada", "Aucun dossier de destination configuré", is_error=True)
            return

        # Step 1: Quality
        prof_choice = xbmcgui.Dialog().select(f"Étape 1/3 — Choisir la Qualité pour {title}", [p['name'] for p in profiles])
        if prof_choice < 0:
            return
        chosen_profile = profiles[prof_choice]

        # Step 2: Folder
        folder_choice = xbmcgui.Dialog().select(f"Étape 2/3 — Dossier de destination", [f"{f['path']} ({search_media._format_size(f.get('free_space'))} libres)" for f in folders])
        if folder_choice < 0:
            return
        chosen_folder = folders[folder_choice]['path']

        # Step 3: Mode
        mode_choice = xbmcgui.Dialog().select(f"Étape 3/3 — Mode de téléchargement", [
            "🚀 Téléchargement Automatique (Meilleure release)",
            "🎯 Choisir la Release manuellement (Torrent vs Usenet)",
        ])
        if mode_choice < 0:
            return

        if mode_choice == 0:
            show_notification("ArrMada", f"Ajout et recherche de {title}...", time_ms=3000)
            add_res = ArrMadaAPI.add_media({
                "type": mtype,
                "title": title,
                "tmdb_id": tmdb_id,
                "tvdb_id": tvdb_id,
                "quality_profile_id": chosen_profile.get("id"),
                "root_folder_path": chosen_folder,
                "search_now": True,
            })
            if add_res.get("status") == "ok":
                show_notification("ArrMada", f"'{title}' ajouté ! Téléchargement en cours...", is_error=False, time_ms=5000)
            else:
                show_notification("ArrMada", add_res.get("message") or "Erreur", is_error=True, time_ms=5000)
        else:
            show_notification("ArrMada", f"Ajout de {title}...", time_ms=2500)
            add_res = ArrMadaAPI.add_media({
                "type": mtype,
                "title": title,
                "tmdb_id": tmdb_id,
                "tvdb_id": tvdb_id,
                "quality_profile_id": chosen_profile.get("id"),
                "root_folder_path": chosen_folder,
                "search_now": False,
            })
            if add_res.get("status") != "ok":
                show_notification("ArrMada", add_res.get("message") or "Erreur", is_error=True, time_ms=5000)
                return
            new_id = add_res.get("arr_id")
            if new_id:
                search_media.pick_and_grab_release(mtype, new_id, title)


def show_downloads_dialog():
    """Show active downloads list with interactive management (Retry, Cancel, Blocklist)."""
    res = ArrMadaAPI.get_addon_status()
    if res.get("status") != "ok":
        msg = res.get("message") or "Impossible de contacter ArrMada"
        show_notification("ArrMada", msg, is_error=True)
        return

    downloads = res.get("downloads", [])
    if not downloads:
        xbmcgui.Dialog().ok("ArrMada : Telechargements", "Aucun telechargement en cours dans SABnzbd / Torrent.")
        return

    items = []
    for d in downloads:
        title = d.get("title", "")
        progress = d.get("progress", 0)
        timeleft = d.get("timeleft") or ""
        service = (d.get("service") or "").upper()
        items.append(f"[{progress}%] [{service}] {title} (ETA: {timeleft})")

    idx = xbmcgui.Dialog().select("ArrMada -- Telechargements actifs (Selectionnez pour agir)", items)
    if idx < 0:
        return

    selected = downloads[idx]
    title = selected.get("title", "Telechargement")
    svc_type = (selected.get("service") or "radarr").lower()
    item_id = selected.get("id") or idx + 1

    actions = [
        "▶️ Reprendre le telechargement (Resume)",
        "⏸️ Mettre en pause (Pause)",
        "🗑️ Annuler et supprimer du client",
        "⛔ Supprimer et bloquer cette version (Blocklist)",
    ]

    action_idx = xbmcgui.Dialog().select(f"Action pour : {title[:50]}...", actions)
    if action_idx == 0:
        res = ArrMadaAPI.resume_queue_item(svc_type, item_id)
        msg = res.get("message", "Reprise envoyee")
        show_notification("ArrMada", msg, is_error=(res.get("status") != "ok"))
    elif action_idx == 1:
        res = ArrMadaAPI.pause_queue_item(svc_type, item_id)
        msg = res.get("message", "Mise en pause envoyee")
        show_notification("ArrMada", msg, is_error=(res.get("status") != "ok"))
    elif action_idx == 2:
        res = ArrMadaAPI.remove_queue_item(svc_type, item_id, remove_from_client=True, blocklist=False)
        msg = res.get("message", "Suppression effectuee")
        show_notification("ArrMada", msg, is_error=(res.get("status") != "ok"))
    elif action_idx == 3:
        res = ArrMadaAPI.remove_queue_item(svc_type, item_id, remove_from_client=True, blocklist=True)
        msg = res.get("message", "Supprime et bloque")
        show_notification("ArrMada", msg, is_error=(res.get("status") != "ok"))



def show_widget_recent():
    """Output recent additions directory for Kodi home screen widgets."""
    xbmcplugin.setPluginCategory(HANDLE, "Derniers ajouts")
    xbmcplugin.setContent(HANDLE, "movies")

    media_items = ArrMadaAPI.get_recent_media()
    for m in media_items:
        add_media_item(m)

    xbmcplugin.endOfDirectory(HANDLE)


def show_widget_downloads():
    """Output active downloads list for Kodi home screen widgets."""
    xbmcplugin.setPluginCategory(HANDLE, "Telechargements actifs")
    xbmcplugin.setContent(HANDLE, "files")

    res = ArrMadaAPI.get_addon_status()
    downloads = res.get("downloads", [])
    for d in downloads:
        title = d.get("title", "")
        pct = d.get("progress", 0)
        svc = (d.get("service") or "").upper()
        li = xbmcgui.ListItem(label=f"[{pct}%] [{svc}] {title}")
        li.setInfo("video", {"plot": f"Progression : {pct}%\nService : {svc}\nTemps restant : {d.get('timeleft', '')}"})
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=f"{PLUGIN_URL}?action=downloads", listitem=li, isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


def show_dashboard_dialog():
    """Display interactive Stack Health, Storage, and Activity Dashboard."""
    import dashboard
    dashboard.show_dashboard()


def main():
    """Router."""
    params = {}
    if len(sys.argv) > 2 and sys.argv[2]:
        raw_query = sys.argv[2].lstrip("?")
        params = dict(urllib.parse.parse_qsl(raw_query))

    action = params.get("action")

    if not action:
        show_root_menu()
    elif action == "home":
        import home_window
        home_window.open_home()
    elif action == "search_input":
        query = xbmcgui.Dialog().input("ArrMada : Rechercher un film ou une serie")
        if query:
            xbmc.executebuiltin(f"ActivateWindow(videos,{PLUGIN_URL}?action=search_results&q={urllib.parse.quote(query)},return)")
    elif action == "search_results":
        handle_search_results(params.get("q", ""))
    elif action == "trending_movies":
        show_trending_movies()
    elif action == "trending_series":
        show_trending_series()
    elif action == "recommendations":
        show_recommendations()
    elif action == "discovery":
        import discovery
        discovery.show_discovery_menu()
    elif action == "maintenance":
        import maintenance
        maintenance.show_maintenance_menu()
    elif action == "widget_recent":
        show_widget_recent()
    elif action == "widget_downloads":
        show_widget_downloads()
    elif action == "widget_trending":
        show_trending_movies()
    elif action == "dashboard" or action == "dashboard_popup":
        show_dashboard_dialog()
    elif action == "media_details":
        show_media_details_dialog(params)
    elif action == "downloads":
        show_downloads_dialog()
    elif action == "sync":
        show_notification("ArrMada", "Scan de la mediatheque demande...", time_ms=2500)
        ArrMadaAPI.trigger_sync()
        show_notification("ArrMada", "Scan demarre !", is_error=False)
    elif action == "clean":
        import maintenance
        maintenance._run_kodi_clean()
    elif action == "clean_orphans":
        import maintenance
        maintenance._run_orphan_clean()
    elif action == "settings":
        ADDON.openSettings()


if __name__ == "__main__":
    main()


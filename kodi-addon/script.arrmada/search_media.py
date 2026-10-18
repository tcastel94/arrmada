# -*- coding: utf-8 -*-
"""Media Search, Discovery, and Interactive Release Picker for Kodi."""

from __future__ import annotations

import sys
import os
import xbmc
import xbmcgui

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import show_notification, confirm_dialog


def _format_size(size_bytes: int | None) -> str:
    if not size_bytes:
        return "0 Mo"
    gb = size_bytes / (1024 * 1024 * 1024)
    if gb >= 1.0:
        return f"{gb:.1f} Go"
    mb = size_bytes / (1024 * 1024)
    return f"{mb:.0f} Mo"


def pick_and_grab_release(media_type: str, arr_id: int, title: str):
    """Fetch releases from indexers and let user choose Torrent or Usenet release."""
    p_dialog = xbmcgui.DialogProgress()
    p_dialog.create("🏴‍☠️ ArrMada", f"Recherche des releases pour {title}...\n(Interrogation Prowlarr / Usenet / Torrent)")
    p_dialog.update(30)

    res = ArrMadaAPI.get_releases(media_type, arr_id)
    p_dialog.close()

    if res.get("status") != "ok":
        msg = res.get("message") or "Erreur lors de la recherche de releases."
        show_notification("ArrMada", msg, is_error=True, time_ms=5000)
        return

    releases = res.get("releases", [])
    if not releases:
        xbmcgui.Dialog().ok("ArrMada", f"Aucune release trouvée pour '{title}' sur vos indexeurs.")
        return

    # Build labels
    labels = []
    for r in releases:
        proto_icon = r.get("protocol_icon", "")
        qual = r.get("quality", "")
        size = r.get("size_human", "")
        indexer = r.get("indexer", "")
        rel_title = r.get("title", "")
        rejected_mark = " ⚠️ [Rejeté]" if r.get("rejected") else ""
        labels.append(f"[{proto_icon} | {qual} | {size} | {indexer}]{rejected_mark}\n{rel_title}")

    choice = xbmcgui.Dialog().select(f"Releases pour {title} ({len(releases)})", labels)
    if choice < 0:
        return

    chosen_release = releases[choice]
    rel_title = chosen_release.get("title", "")
    proto = chosen_release.get("protocol", "torrent").upper()

    confirm = confirm_dialog(
        f"Lancer le téléchargement ({proto})",
        f"Voulez-vous envoyer cette release au client de téléchargement ?\n\n{rel_title}\n\nTaille : {chosen_release.get('size_human')} | Indexeur : {chosen_release.get('indexer')}"
    )
    if not confirm:
        return

    show_notification("ArrMada", "Envoi au client de téléchargement...", time_ms=2500)

    grab_res = ArrMadaAPI.grab_release(media_type, arr_id, {
        "guid": chosen_release.get("guid"),
        "indexer_id": chosen_release.get("indexer_id"),
        "release_title": rel_title,
        "media_title": title,
    })

    if grab_res.get("status") == "ok":
        show_notification("ArrMada", f"Téléchargement lancé : {rel_title}", is_error=False, time_ms=5000)
    else:
        err = grab_res.get("message") or "Erreur lors de l'envoi"
        show_notification("ArrMada", err, is_error=True, time_ms=5000)


def main():
    query = xbmcgui.Dialog().input("🏴‍☠️ ArrMada : Rechercher un film ou une série")
    if not query:
        return

    p_dialog = xbmcgui.DialogProgress()
    p_dialog.create("🏴‍☠️ ArrMada", f"Recherche de '{query}'...")
    p_dialog.update(50)

    results = ArrMadaAPI.lookup_media(query)
    p_dialog.close()

    if not results:
        xbmcgui.Dialog().ok("ArrMada", f"Aucun résultat trouvé pour '{query}'.")
        return

    # Build result list labels
    labels = []
    for item in results:
        mtype = "🎬 Film" if item.get("type") == "movie" else "📺 Série"
        year = f" ({item.get('year')})" if item.get("year") else ""
        in_lib = " [✅ Déjà dans la médiathèque]" if item.get("in_library") else " [➕ Non possédé]"
        labels.append(f"{mtype} : {item.get('title')}{year}{in_lib}")

    choice = xbmcgui.Dialog().select(f"Résultats ({len(results)})", labels)
    if choice < 0:
        return

    item = results[choice]
    title = item.get("title", "")
    media_type = item.get("type", "movie")
    in_library = item.get("in_library", False)
    arr_id = item.get("arr_id")

    # Case A: Already in library
    if in_library and arr_id:
        action_choice = xbmcgui.Dialog().select(
            f"🎬 {title} (Déjà possédé)",
            [
                "🎯 Choisir une Release manuellement (Torrent vs Usenet)",
                "🚀 Forcer la recherche automatique d'une meilleure version",
            ]
        )
        if action_choice == 0:
            pick_and_grab_release(media_type, arr_id, title)
        elif action_choice == 1:
            show_notification("ArrMada", "Recherche automatique lancée...", time_ms=3000)
            res = ArrMadaAPI.trigger_search({"title": title, "media_type": media_type})
            if res.get("status") == "ok":
                show_notification("ArrMada", res.get("message") or "Recherche lancée !", is_error=False, time_ms=4500)
            else:
                show_notification("ArrMada", res.get("message") or "Erreur", is_error=True, time_ms=5000)
        return

    # Case B: Not in library -> 3-step wizard
    opts = ArrMadaAPI.get_media_options(media_type)
    profiles = opts.get("profiles", [])
    folders = opts.get("root_folders", [])

    if not profiles:
        show_notification("ArrMada", "Aucun profil de qualité configuré", is_error=True)
        return
    if not folders:
        show_notification("ArrMada", "Aucun dossier de destination configuré", is_error=True)
        return

    # Step 1: Quality Profile (1080p, 2160p Ultra-HD, etc.)
    prof_labels = [p.get("name", "") for p in profiles]
    prof_choice = xbmcgui.Dialog().select(f"Étape 1/3 — Choisir la Qualité pour {title}", prof_labels)
    if prof_choice < 0:
        return
    chosen_profile = profiles[prof_choice]

    # Step 2: Root Folder
    folder_labels = [f"{f.get('path')} ({_format_size(f.get('free_space'))} libres)" for f in folders]
    folder_choice = xbmcgui.Dialog().select(f"Étape 2/3 — Dossier de destination", folder_labels)
    if folder_choice < 0:
        return
    chosen_folder = folders[folder_choice].get("path")

    # Step 3: Download Mode
    mode_options = [
        "🚀 Téléchargement Automatique (ArrMada choisit la meilleure release)",
        "🎯 Choisir la Release manuellement (Sélection Torrent / Usenet)",
    ]
    mode_choice = xbmcgui.Dialog().select(f"Étape 3/3 — Mode de recherche", mode_options)
    if mode_choice < 0:
        return

    if mode_choice == 0:  # Auto
        show_notification("ArrMada", f"Ajout et recherche auto de {title}...", time_ms=3000)
        add_res = ArrMadaAPI.add_media({
            "type": media_type,
            "title": title,
            "tmdb_id": item.get("tmdb_id"),
            "tvdb_id": item.get("tvdb_id"),
            "quality_profile_id": chosen_profile.get("id"),
            "root_folder_path": chosen_folder,
            "search_now": True,
        })
        if add_res.get("status") == "ok":
            show_notification("ArrMada", f"'{title}' ajouté ! Recherche en cours...", is_error=False, time_ms=5000)
        else:
            err = add_res.get("message") or "Erreur lors de l'ajout"
            show_notification("ArrMada", err, is_error=True, time_ms=5000)

    else:  # Manual Release Picker
        show_notification("ArrMada", f"Ajout de {title}...", time_ms=2500)
        add_res = ArrMadaAPI.add_media({
            "type": media_type,
            "title": title,
            "tmdb_id": item.get("tmdb_id"),
            "tvdb_id": item.get("tvdb_id"),
            "quality_profile_id": chosen_profile.get("id"),
            "root_folder_path": chosen_folder,
            "search_now": False,
        })
        if add_res.get("status") != "ok":
            err = add_res.get("message") or "Erreur lors de l'ajout"
            show_notification("ArrMada", err, is_error=True, time_ms=5000)
            return

        new_arr_id = add_res.get("arr_id")
        if not new_arr_id:
            show_notification("ArrMada", "Ajouté, mais impossible d'obtenir l'ID média", is_error=True)
            return

        # Prompt release picker
        pick_and_grab_release(media_type, new_arr_id, title)


if __name__ == "__main__":
    main()

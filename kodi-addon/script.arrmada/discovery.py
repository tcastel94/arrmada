# -*- coding: utf-8 -*-
"""ArrMada — Discovery & 1-Click Add for Kodi.

Allows users to browse trending movies and TV shows from TMDB/Trakt,
and add them directly to Radarr/Sonarr from their TV with a choice
of quality profile (4K HDR, 1080p MULTI, etc.).
"""

from __future__ import annotations

import sys
import os
import xbmcgui
import xbmcplugin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import show_notification


def show_discovery_menu():
    """Interactive discovery menu on Kodi."""
    pd = xbmcgui.DialogProgress()
    pd.create("ArrMada - Decouverte", "Chargement des tendances & nouveautes...")
    pd.update(30)

    try:
        data = ArrMadaAPI.get_recommendations()
    except Exception as exc:
        data = {}
    finally:
        pd.close()

    trending_movies = data.get("trending_movies", []) or data.get("movies", [])
    trending_series = data.get("trending_series", []) or data.get("series", [])

    if not trending_movies and not trending_series:
        xbmcgui.Dialog().ok("Decouverte ArrMada", "Aucune recommandation disponible actuellement.")
        return

    while True:
        cat_choices = [
            f"[FILMS TENDANCES]      ({len(trending_movies)} titres)",
            f"[SERIES TENDANCES]     ({len(trending_series)} titres)",
        ]
        choice = xbmcgui.Dialog().select("ArrMada -- Tendances & Decouverte", cat_choices)
        if choice < 0:
            break

        if choice == 0:
            _browse_items(trending_movies, "movie")
        elif choice == 1:
            _browse_items(trending_series, "series")


def _browse_items(items: list, media_type: str):
    """Browse a list of trending items and handle 1-click addition."""
    if not items:
        xbmcgui.Dialog().ok("Decouverte", "Aucun titre dans cette categorie.")
        return

    while True:
        list_items = []
        for it in items:
            title = it.get("title") or it.get("name") or "Inconnu"
            year = it.get("year") or it.get("release_date", "")[:4] or ""
            in_lib = it.get("in_library") or it.get("exists", False)
            downloading = it.get("is_downloading", False)

            if in_lib:
                status_tag = "[COLOR lime][EN COLLECTION][/COLOR]"
            elif downloading:
                status_tag = "[COLOR cyan][EN TELECHARGEMENT][/COLOR]"
            else:
                status_tag = "[COLOR gold][+ AJOUTER][/COLOR]"

            year_str = f" ({year})" if year else ""
            list_items.append(f"{status_tag} {title}{year_str}")

        idx = xbmcgui.Dialog().select(f"Tendances ({'Films' if media_type == 'movie' else 'Series'})", list_items)
        if idx < 0:
            break

        selected = items[idx]
        _handle_item_action(selected, media_type)


def _handle_item_action(item: dict, media_type: str):
    """Show details and prompt for quality profile addition if missing."""
    title = item.get("title") or item.get("name") or "Titre"
    year = item.get("year") or item.get("release_date", "")[:4] or ""
    overview = item.get("overview") or item.get("summary") or "Aucun resume disponible."
    in_lib = item.get("in_library") or item.get("exists", False)

    dialog_text = f"[B]{title}[/B] ({year})\n\n{overview}"

    if in_lib:
        xbmcgui.Dialog().textviewer(f"ArrMada - {title}", dialog_text + "\n\n[COLOR lime][Ce media est deja present dans votre collection.][/COLOR]")
        return

    # Prompt to add to library
    confirm = xbmcgui.Dialog().yesno(
        f"Ajouter {title}",
        f"{dialog_text}\n\n[COLOR gold]Souhaitez-vous envoyer ce titre en telechargement ?[/COLOR]",
        yeslabel="Telecharger",
        nolabel="Annuler"
    )
    if not confirm:
        return

    # Fetch quality profile options
    options = ArrMadaAPI.get_media_options(media_type)
    profiles = options.get("profiles", [])
    root_folders = options.get("root_folders", [])

    selected_profile_id = 1
    if profiles:
        profile_names = [f"Qualite : {p.get('name')}" for p in profiles]
        p_idx = xbmcgui.Dialog().select(f"Choisir la qualite pour {title}", profile_names)
        if p_idx >= 0:
            selected_profile_id = profiles[p_idx].get("id", 1)

    root_path = root_folders[0].get("path") if root_folders else None

    # Call ArrMada backend to add media
    payload = {
        "type": media_type,
        "title": title,
        "tmdb_id": item.get("tmdb_id") or item.get("id"),
        "tvdb_id": item.get("tvdb_id"),
        "quality_profile_id": selected_profile_id,
        "root_folder_path": root_path,
        "search_now": True,
    }

    res = ArrMadaAPI.add_media(payload)
    if res.get("status") == "ok":
        show_notification("ArrMada", f"{title} ajoute avec succes !", is_error=False, time_ms=5000)
        item["in_library"] = True
    else:
        err = res.get("message") or "Erreur lors de l'ajout"
        show_notification("ArrMada", err, is_error=True, time_ms=6000)


if __name__ == "__main__":
    show_discovery_menu()

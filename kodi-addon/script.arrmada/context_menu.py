# -*- coding: utf-8 -*-
"""Unified Context Menu for ArrMada."""

from __future__ import annotations

import sys
import os
import xbmcgui

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import get_current_item_info, show_notification, confirm_dialog


def main():
    info = get_current_item_info()
    title = info.get("title") or "Média"

    label = f"{title}"
    if info.get("season") is not None and info.get("episode") is not None:
        label += f" S{info['season']:02d}E{info['episode']:02d}"
    elif info.get("season") is not None:
        label += f" Saison {info['season']}"

    options = [
        ("Télécharger sous-titres (Bazarr)", "download_sub"),
        ("Re-synchroniser sous-titres (FFsubsync)", "sync_sub"),
        ("Re-chercher / Upgrader release (Radarr/Sonarr)", "search_release"),
        ("Tableau de bord & Santé de la Stack", "dashboard"),
    ]

    choice = xbmcgui.Dialog().select(f"ArrMada : {label}", [opt[0] for opt in options])
    if choice < 0:
        return

    action = options[choice][1]

    if action == "dashboard":
        import dashboard
        dashboard.show_dashboard()


    elif action == "download_sub":
        show_notification("ArrMada : Bazarr", f"Recherche pour {label}...", time_ms=2500)
        res = ArrMadaAPI.trigger_subtitles(info)
        if res.get("status") == "ok":
            msg = res.get("message") or "Sous-titres trouvés et téléchargés !"
            show_notification("ArrMada : Bazarr", msg, is_error=False, time_ms=4500)
        else:
            err = res.get("message") or "Erreur lors de la recherche"
            show_notification("ArrMada : Bazarr", err, is_error=True, time_ms=5000)

    elif action == "sync_sub":
        show_notification("ArrMada : FFsubsync", f"Synchronisation pour {label}...", time_ms=3000)
        res = ArrMadaAPI.trigger_subtitles_sync(info)
        if res.get("status") == "ok":
            msg = res.get("message") or "Synchronisation FFsubsync lancée avec succès !"
            show_notification("ArrMada : FFsubsync", msg, is_error=False, time_ms=5000)
        else:
            err = res.get("message") or "Erreur lors de la synchronisation"
            show_notification("ArrMada : FFsubsync", err, is_error=True, time_ms=5000)

    elif action == "search_release":
        confirm = confirm_dialog("ArrMada : Re-chercher release", f"Lancer la recherche d'une release pour :\n{label} ?")
        if not confirm:
            return
        show_notification("ArrMada", f"Recherche en cours pour {label}...", time_ms=2500)
        res = ArrMadaAPI.trigger_search(info)
        if res.get("status") == "ok":
            msg = res.get("message") or "Recherche lancée avec succès !"
            show_notification("ArrMada", msg, is_error=False, time_ms=4500)
        else:
            err = res.get("message") or "Erreur lors du lancement de la recherche"
            show_notification("ArrMada", err, is_error=True, time_ms=5000)



if __name__ == "__main__":
    main()

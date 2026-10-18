# -*- coding: utf-8 -*-
"""Context menu item: Trigger Radarr / Sonarr release search / upgrade."""

from __future__ import annotations

import sys
import os

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import get_current_item_info, show_notification, confirm_dialog


def main():
    info = get_current_item_info()
    title = info.get("title")

    if not title:
        show_notification("ArrMada", "Impossible d'identifier le média sélectionné", is_error=True)
        return

    label = f"{title}"
    if info.get("season") is not None and info.get("episode") is not None:
        label += f" S{info['season']:02d}E{info['episode']:02d}"
    elif info.get("season") is not None:
        label += f" Saison {info['season']}"

    # Ask confirmation
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

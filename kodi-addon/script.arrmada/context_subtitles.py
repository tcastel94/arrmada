# -*- coding: utf-8 -*-
"""Context menu item: Download subtitles via Bazarr."""

from __future__ import annotations

import sys
import os

# Add lib directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import get_current_item_info, show_notification


def main():
    info = get_current_item_info()
    title = info.get("title")

    if not title:
        show_notification("ArrMada", "Impossible d'identifier le média sélectionné", is_error=True)
        return

    label = f"{title}"
    if info.get("season") is not None and info.get("episode") is not None:
        label += f" S{info['season']:02d}E{info['episode']:02d}"

    show_notification("ArrMada : Bazarr", f"Recherche pour {label}...", time_ms=2500)

    res = ArrMadaAPI.trigger_subtitles(info)

    if res.get("status") == "ok":
        msg = res.get("message") or "Sous-titres trouvés et téléchargés !"
        show_notification("ArrMada : Bazarr", msg, is_error=False, time_ms=4500)
    else:
        err = res.get("message") or "Erreur lors de la recherche"
        show_notification("ArrMada : Bazarr", err, is_error=True, time_ms=5000)


if __name__ == "__main__":
    main()

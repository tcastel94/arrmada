# -*- coding: utf-8 -*-
"""« Prêt à regarder » : logique pure (ADR-005, lot 4, testée en CI).

Quand une demande lancée depuis une TV est importée (et ses sous-titres
cherchés), le serveur publie l'événement `tv_ready` avec le numéro de la TV
qui l'a lancée. Le service de CETTE TV ouvre alors une pop-up avec un bouton
« Regarder » ; les autres TV l'ignorent. Pendant un film, la pop-up attend la
fin de la lecture.

Même adressage que « Lire sur la TV » (remote_data) : numéro d'appareil +
date de l'événement (une TV qui se rallume ne rejoue pas une vieille annonce).
« Regarder » réutilise d'ailleurs sa lecture (kodi_library.remote_play).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

import remote_data

EVENT = "tv_ready"
ACTION = "ready"  # plugin://script.arrmada/?action=ready&…
DISPLAY_SECONDS = 60  # la pop-up se referme seule (« Plus tard »)

_SUBTITLES = {
    "fr": "sous-titres français",
    "en": "sous-titres anglais seulement",
    "missing": "sous-titres pas encore trouvés",
}


def for_me(data: Mapping[str, Any], my_id: Any, now: datetime) -> bool:
    """L'annonce vise cette TV et date de moins de 2 min (règle de remote_data)."""
    return remote_data.for_me(data, my_id, now)


def subtitles_label(code: Any) -> str:
    """« fr » → « sous-titres français » ; « off » / vide → ""."""
    return _SUBTITLES.get(str(code or ""), "")


def popup_params(data: Mapping[str, Any]) -> Dict[str, str]:
    """Paramètres de `RunPlugin(…?action=ready&…)` (pop-up hors de la boucle du service)."""
    play = remote_data.plugin_params(dict(data, resume=True))
    params = {key: value for key, value in play.items() if key != "action"}
    params.update(
        action=ACTION,
        poster=str(data.get("poster") or ""),
        quality=str(data.get("quality") or ""),
        subtitles=str(data.get("subtitles") or ""),
    )
    return params


def texts(params: Mapping[str, Any]) -> Dict[str, str]:
    """Titre et ligne de détail de la pop-up."""
    title = remote_data.describe(params) if params.get("media_type") else ""
    details = [str(params.get("quality") or ""), subtitles_label(params.get("subtitles"))]
    return {
        "title": title or str(params.get("title") or "Ton titre"),
        "details": " · ".join(d for d in details if d),
    }


def play_params(params: Mapping[str, Any]) -> Dict[str, str]:
    """Paramètres de kodi_library.remote_play pour le bouton « Regarder »."""
    keys = ("media_type", "id_type", "id", "title", "season", "episode")
    play = {key: str(params[key]) for key in keys if params.get(key) not in (None, "")}
    play.update(action=remote_data.ACTION, resume="1")
    return play


def can_play(params: Mapping[str, Any]) -> bool:
    """Assez d'informations pour retrouver le titre dans la médiathèque de la TV."""
    if params.get("media_type") == "movie":
        return bool(params.get("id"))
    return params.get("media_type") == "episode" and bool(params.get("id"))

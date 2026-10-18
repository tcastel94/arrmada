# -*- coding: utf-8 -*-
"""Encart « Épisode suivant » : logique pure, sans Kodi (testée en CI).

ADR-004, phase 4.4. Quelques secondes avant la fin d'un épisode de la
médiathèque (réglage, 20 s par défaut), un encart s'affiche en bas à droite :
vignette de l'épisode suivant, « S01E05 · Titre », compte à rebours.

  - Lancer maintenant : passe tout de suite à l'épisode suivant ;
  - Annuler           : la lecture s'arrêtera à la fin de cet épisode ;
  - Retour / rien     : l'encart disparaît, l'épisode suivant démarre à la
                        fin comme d'habitude.

L'épisode suivant est celui que Kodi a déjà en file (liste de lecture
vidéo, remplie par ArrMada au lancement). S'il n'y a rien en file (épisode
lancé depuis l'interface de Kodi), le service y ajoute le suivant de la
série, comme le ferait « Lire la suite ».
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

ACTION = "upnext"  # plugin://script.arrmada/?action=upnext&…
POPUP_PROP = "arrmada.upnext_open"  # « 1 » tant que l'encart est ouvert
DEFAULT_SECONDS = 20
CHOICES = (0, 10, 20, 30, 45, 60)  # valeurs du réglage (0 : jamais)
MIN_DURATION = 60  # s : pas d'encart sur un extrait de quelques secondes
PLAYLIST_PROPS = ["title", "season", "episode", "showtitle", "art", "runtime"]


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def seconds_setting(value: Any) -> int:
    """Réglage « secondes avant la fin » → nombre (0 : encart désactivé)."""
    seconds = _int(value) if str(value or "").strip() else DEFAULT_SECONDS
    return seconds if seconds in CHOICES else DEFAULT_SECONDS


def should_offer(
    remaining: float, total: float, threshold: int, already: bool, is_episode: bool
) -> bool:
    """Vrai au moment d'ouvrir l'encart (une seule fois par épisode)."""
    return (
        threshold > 0
        and is_episode
        and not already
        and total >= MIN_DURATION
        and 0 < remaining <= threshold
    )


def next_in_playlist(items: List[Mapping[str, Any]], position: int) -> Optional[Mapping[str, Any]]:
    """Élément qui suit `position` dans la liste de lecture de Kodi, ou None."""
    if position < 0 or position + 1 >= len(items or []):
        return None
    return items[position + 1]


def code(season: Any, episode: Any) -> str:
    season, episode = _int(season), _int(episode)
    if season < 0 or episode <= 0:
        return ""
    return f"S{season:02d}E{episode:02d}"


def popup_params(item: Mapping[str, Any]) -> Dict[str, str]:
    """Élément de la liste de lecture → paramètres de l'encart (texte seulement)."""
    art = item.get("art") or {}
    title = str(item.get("title") or item.get("label") or "").strip()
    number = code(item.get("season"), item.get("episode"))
    return {
        "action": ACTION,
        "show": str(item.get("showtitle") or "").strip(),
        "code": number,
        "title": title,
        "line": " · ".join(part for part in (number, title) if part),
        "thumb": str(art.get("thumb") or art.get("fanart") or art.get("tvshow.fanart") or ""),
    }


def countdown_label(remaining: float) -> str:
    """« Dans 18 s » ; « Maintenant » à la toute fin."""
    seconds = int(remaining + 0.5)
    return f"Dans {seconds} s" if seconds > 0 else "Maintenant"


def bar(remaining: float, threshold: float) -> str:
    """Barre du compte à rebours (textures arrmada/progress/bar-000 … bar-100)."""
    if threshold <= 0:
        return "bar-000"
    share = max(0.0, min(1.0, remaining / threshold))
    step = int(round(share * 50)) * 2  # textures de 2 en 2 %
    return f"bar-{step:03d}"


def positions_to_remove(count: int, position: int) -> List[int]:
    """Positions à retirer de la liste de lecture pour s'arrêter après l'épisode
    en cours (de la fin vers le début : les numéros ne se décalent pas)."""
    if position < 0:
        return []
    return list(range(count - 1, position, -1))

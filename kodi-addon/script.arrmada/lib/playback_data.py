# -*- coding: utf-8 -*-
"""Suivi de lecture envoyé au serveur (add-on 1.10.0) — logique pure, sans Kodi.

Le service prévient ArrMada de ce que la TV lit : « play », « pause »,
« resume », « stop », et la position toutes les 30 s. Le serveur s'en sert
pour l'historique… et, depuis la 1.10, pour l'écran d'appoint du salon (la
tablette sous la TV) : titre, épisode, affiche, heure de début et de fin.

Deux pièges corrigés ici :

  - les infos viennent du LECTEUR (VideoPlayer.*, Player.Art), jamais de
    l'élément sélectionné dans une liste (ListItem.*) : à l'épisode suivant
    enchaîné tout seul, la liste montre encore l'ancien ;
  - en pause, Kodi reste « en lecture » et le relevé des 30 s continue :
    chaque envoi dit maintenant s'il est en pause (`paused`).

Les images : Kodi les connaît parfois enveloppées (« image://https%3a… / »)
ou locales (smb://, special://). Seules les adresses web passent : la
tablette ne saurait pas ouvrir les autres (le serveur prend alors celles de
la médiathèque).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from urllib.parse import unquote

# Libellés Kodi lus par le service (clé courte → infolabel). DOIT rester
# synchronisé avec playing_item() (vérifié par les tests).
LABELS: Dict[str, str] = {
    "title": "VideoPlayer.Title",
    "tvshow": "VideoPlayer.TVShowTitle",
    "season": "VideoPlayer.Season",
    "episode": "VideoPlayer.Episode",
    "year": "VideoPlayer.Year",
    "tmdb": "VideoPlayer.UniqueID(tmdb)",
    "label": "Player.Title",
    "poster": "Player.Art(poster)",
    "tvshow.poster": "Player.Art(tvshow.poster)",
    "fanart": "Player.Art(fanart)",
    "tvshow.fanart": "Player.Art(tvshow.fanart)",
}

PROGRESS_EVERY = 30  # s entre deux relevés de position


def web_image(value: Any) -> str:
    """Adresse http(s) d'une image Kodi, ou "" (locale, vide, illisible)."""
    text = str(value or "").strip()
    if text.startswith("image://"):
        # « image://https%3a%2f%2fimage.tmdb.org%2f…jpg/ » → adresse d'origine
        text = unquote(text[len("image://") :].rstrip("/"))
    return text if text.startswith(("http://", "https://")) else ""


def _int(value: Any) -> Optional[int]:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def playing_item(labels: Mapping[str, str], media_type: str = "") -> Dict[str, Any]:
    """Ce que lit le lecteur, d'après les libellés LABELS.

    `media_type` : celui de l'étiquette vidéo du lecteur (« movie »,
    « episode », « » pour un fichier non identifié).
    """
    tvshow = (labels.get("tvshow") or "").strip()
    title = (labels.get("title") or "").strip() or (labels.get("label") or "").strip()
    season, episode = _int(labels.get("season")), _int(labels.get("episode"))
    is_episode = (
        media_type == "episode"
        or bool(tvshow)
        or (season is not None and episode is not None and media_type != "movie")
    )
    tmdb = (labels.get("tmdb") or "").strip()
    item: Dict[str, Any] = {
        "media_type": "episode" if is_episode else "movie",
        "title": (tvshow or title) if is_episode else title,
        "tmdb_id": tmdb if tmdb.isdigit() else None,
        "year": _int(labels.get("year")) or None,
        "season": season if is_episode else None,
        "episode": episode if is_episode else None,
        "episode_title": title if is_episode and tvshow and title != tvshow else "",
    }
    if is_episode:
        item["poster"] = web_image(labels.get("tvshow.poster")) or web_image(labels.get("poster"))
        item["fanart"] = web_image(labels.get("fanart")) or web_image(labels.get("tvshow.fanart"))
    else:
        item["poster"] = web_image(labels.get("poster"))
        item["fanart"] = web_image(labels.get("fanart"))
    return item


def scrobble_payload(
    event: str,
    item: Mapping[str, Any],
    position: float = 0.0,
    total: float = 0.0,
    paused: bool = False,
    ended: bool = False,
) -> Dict[str, Any]:
    """Corps de POST /api/kodi/scrobble (champs historiques + ceux de l'écran d'appoint).

    « stop » : `ended` si la vidéo est allée au bout ; sinon pourcentage de
    la dernière position connue (le serveur note « vu » à partir de 90 %).
    """
    position = max(0.0, float(position or 0))
    total = max(0.0, float(total or 0))
    payload: Dict[str, Any] = {
        "event": event,
        "title": item.get("title") or "",
        "media_type": item.get("media_type") or "movie",
        "tmdb_id": item.get("tmdb_id"),
        "season": item.get("season"),
        "episode": item.get("episode"),
        "episode_title": item.get("episode_title") or "",
        "year": item.get("year"),
        "poster": item.get("poster") or "",
        "fanart": item.get("fanart") or "",
    }
    if event == "stop":
        if ended:
            payload["percentage"] = 100
        else:
            payload["percentage"] = round(position / total * 100, 1) if total > 0 else 0
        return payload
    payload.update(
        {
            "percentage": round(position / total * 100, 1) if total > 0 else 0,
            "position": int(position),
            "total": int(total),
            "paused": bool(paused) or event == "pause",
        }
    )
    return payload

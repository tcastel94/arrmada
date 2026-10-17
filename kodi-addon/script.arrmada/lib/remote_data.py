# -*- coding: utf-8 -*-
"""« Lire sur la TV » depuis la web app : logique pure (1.19.0, testée en CI).

La web app demande au serveur de lancer un titre sur UNE TV appairée. Le
serveur publie l'événement `play_request`, que toutes les TV relèvent toutes
les 5 s (comme les autres événements). Chaque TV vérifie :

  1. que la demande lui est adressée (`device_id` = son numéro d'appareil) ;
  2. qu'elle est récente (moins de 2 min) : une TV qui se rallume, ou un
     serveur qui redémarre et rejoue son historique, ne lance jamais un film
     « surprise » demandé il y a longtemps.

Puis elle cherche le titre dans SA médiathèque Kodi (TMDB pour un film, TVDB
de la série + saison + épisode : les numéros internes de Kodi diffèrent d'une
TV à l'autre) et le lance par la logique d'ArrMada (reprise, épisodes
enchaînés, préréglage de l'ampli).

Analogie : un message déposé sur un bus avec l'adresse du destinataire et
une date d'expiration ; aucune connexion entrante vers la TV.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional

EVENT = "play_request"
ACTION = "remote_play"  # plugin://script.arrmada/?action=remote_play&…
MAX_AGE = 120  # s : au-delà, la demande est ignorée
CLOCK_SKEW = 60  # s : horloges TV / serveur légèrement décalées


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _moment(value: Any) -> Optional[datetime]:
    """« 2026-10-11T20:00:00+00:00 » → date avec fuseau ; None si illisible."""
    try:
        moment = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _flag(value: Any, default: bool = True) -> bool:
    """Vrai / faux venu du JSON (booléen) ou d'une URL (« 0 », « false »)."""
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "non")
    return bool(value)


def for_me(data: Mapping[str, Any], my_id: Any, now: datetime) -> bool:
    """La demande vise cette TV et date de moins de 2 min."""
    mine = _int(my_id)
    if not mine or _int((data or {}).get("device_id")) != mine:
        return False
    sent = _moment((data or {}).get("at"))
    if sent is None:
        return False
    age = (now - sent).total_seconds()
    return -CLOCK_SKEW <= age <= MAX_AGE


def plugin_params(data: Mapping[str, Any]) -> Dict[str, str]:
    """Paramètres de `RunPlugin(…?action=remote_play&…)` (lecture hors de la boucle du service)."""
    params = {
        "action": ACTION,
        "media_type": str(data.get("media_type") or ""),
        "id_type": str(data.get("id_type") or ""),
        "id": str(data.get("id") or ""),
        "resume": "1" if _flag(data.get("resume")) else "0",
        "title": str(data.get("title") or "")[:200],
    }
    if params["media_type"] == "episode":
        params["season"] = str(_int(data.get("season")))
        params["episode"] = str(_int(data.get("episode")))
    return params


def find_by_id(items: Iterable[Mapping[str, Any]], id_type: str, value: Any, key: str) -> int:
    """Numéro Kodi (`key` : movieid / tvshowid) du titre dont l'id `id_type` vaut `value`."""
    wanted = str(value or "").strip()
    if not wanted or id_type not in ("tmdb", "tvdb", "imdb"):
        return 0
    for item in items or []:
        if str((item.get("uniqueid") or {}).get(id_type) or "").strip() == wanted:
            return _int(item.get(key))
    return 0


def find_episode(episodes: Iterable[Mapping[str, Any]], season: Any, episode: Any) -> int:
    """episodeid de S`season`E`episode` dans la liste Kodi d'une série (0 si absent)."""
    for item in episodes or []:
        if _int(item.get("season")) == _int(season) and _int(item.get("episode")) == _int(episode):
            return _int(item.get("episodeid"))
    return 0


def describe(params: Mapping[str, Any]) -> str:
    """« Severance S02E05 » / « Dune » (bulles et journal)."""
    title = str(params.get("title") or "").strip() or "Ce titre"
    if params.get("media_type") == "episode":
        return f"{title} S{_int(params.get('season')):02d}E{_int(params.get('episode')):02d}"
    return title

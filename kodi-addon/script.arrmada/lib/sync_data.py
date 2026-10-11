# -*- coding: utf-8 -*-
"""Vu / reprise partagés entre les TV : logique pure, sans Kodi (testée en CI).

ADR-004, phase 4.4. Chaque Kodi garde « vu » et position de reprise dans SA
médiathèque. Le serveur sert de point de rendez-vous (table watch_states) :

  - une TV dépose l'état d'un titre quand il change chez elle (fin ou arrêt
    de lecture, « marquer vu / non vu ») ;
  - les autres relisent ce qui a changé depuis leur dernier passage (un
    curseur, comme la position de lecture d'un `tail -f`) et l'appliquent.

Un titre est repéré par ses identifiants publics (TMDB, TVDB, IMDb) : le
numéro interne d'un film dans Kodi diffère d'une TV à l'autre. Un épisode =
identifiant de la série + saison + numéro.

Premier passage d'une TV (jamais synchronisée) : prudence. On ne fait
qu'AJOUTER (un « vu », une reprise là où il n'y en a pas), on ne défait
rien de ce que la TV sait déjà. Ensuite, le geste le plus récent gagne.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

EVENT = "watch_state"  # événement publié par le serveur à chaque changement
STATE_PATH = "/api/kodi/watch-state"
TOLERANCE = 10  # s : deux reprises à moins de 10 s l'une de l'autre sont « la même »
PAGE = 50  # états relus et appliqués par tour de boucle du service
UPLOAD_BATCH = 200  # états envoyés par requête au premier passage
REPORT_DELAY = 3  # s après l'arrêt : Kodi a enregistré vu / reprise
RETRY_AFTER = 60  # s avant de renvoyer un état refusé (serveur injoignable)
MAX_PENDING = 200  # garde-fou de la file d'envoi

# Ordre de préférence des identifiants (le premier présent sert de clé)
ID_ORDER = {
    "movie": ("tmdb", "imdb", "tvdb"),
    "episode": ("tvdb", "tmdb", "imdb"),  # identifiant de la SÉRIE
}

# Filtre Kodi : titres vus ou commencés (le reste n'a rien à partager)
SEEN_OR_STARTED = {
    "or": [
        {"field": "playcount", "operator": "greaterthan", "value": "0"},
        {"field": "inprogress", "operator": "true", "value": ""},
    ]
}


def _int(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _clean_id(value: Any) -> str:
    text = str(value or "").strip()
    return text if text and text not in ("0", "-1") else ""


def pick_id(kind: str, uniqueid: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    """(type, valeur) de l'identifiant qui sert de clé ; None si aucun."""
    for id_type in ID_ORDER.get(kind, ()):
        value = _clean_id((uniqueid or {}).get(id_type))
        if value:
            return id_type, value
    return None


def index_keys(uniqueid: Mapping[str, Any]) -> List[str]:
    """Toutes les clés « tmdb:438631 » d'un titre (pour le retrouver quel que
    soit l'identifiant choisi par l'autre TV)."""
    keys = []
    for id_type in ("tmdb", "tvdb", "imdb"):
        value = _clean_id((uniqueid or {}).get(id_type))
        if value:
            keys.append(f"{id_type}:{value}")
    return keys


def state_key(state: Mapping[str, Any]) -> str:
    """Clé d'un état (même forme que celle du serveur)."""
    key = f"{state.get('media_type')}:{state.get('id_type')}:{state.get('id')}"
    if state.get("media_type") == "episode":
        key += f":{_int(state.get('season'))}:{_int(state.get('episode'))}"
    return key


def resume_position(details: Mapping[str, Any]) -> Tuple[int, int]:
    """(position, durée) de reprise d'un élément Kodi (durée : celle annoncée si besoin)."""
    resume = details.get("resume") or {}
    position = _int(resume.get("position"))
    total = _int(resume.get("total")) or _int(details.get("runtime"))
    return position, total


def local_state(
    kind: str, details: Mapping[str, Any], show_uniqueid: Optional[Mapping[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Film ou épisode de la médiathèque Kodi → état à déposer sur le serveur.

    `show_uniqueid` : identifiants de la SÉRIE (un épisode n'a pas les siens
    dans Kodi). None si le titre n'a aucun identifiant public.
    """
    if kind not in ID_ORDER or not details:
        return None
    ids = pick_id(kind, show_uniqueid if kind == "episode" else details.get("uniqueid") or {})
    if ids is None:
        return None
    position, total = resume_position(details)
    state: Dict[str, Any] = {
        "media_type": kind,
        "id_type": ids[0],
        "id": ids[1],
        "title": str(details.get("showtitle") or details.get("title") or "")[:300],
        "watched": _int(details.get("playcount")) > 0,
        "position": position,
        "total": total,
        "last_played": str(details.get("lastplayed") or ""),
    }
    if kind == "episode":
        state["season"] = _int(details.get("season"))
        state["episode"] = _int(details.get("episode"))
    return state


def same(a: Optional[Mapping[str, Any]], b: Optional[Mapping[str, Any]]) -> bool:
    """Même « vu » et même reprise (à 10 s près)."""
    if not a or not b:
        return False
    return (
        bool(a.get("watched")) == bool(b.get("watched"))
        and abs(_int(a.get("position")) - _int(b.get("position"))) < TOLERANCE
    )


def plan(
    details: Mapping[str, Any], remote: Mapping[str, Any], prudent: bool = False
) -> Optional[Dict[str, Any]]:
    """Changements à appliquer à un élément Kodi pour suivre l'état `remote`.

    Renvoie les paramètres de VideoLibrary.Set{Movie,Episode}Details (sans
    l'identifiant), ou None si l'élément est déjà à jour.
    `prudent` : premier passage, on n'ajoute qu'un « vu » ou une reprise.
    """
    watched = _int(details.get("playcount")) > 0
    position, total = resume_position(details)
    remote_watched = bool(remote.get("watched"))
    remote_position = _int(remote.get("position"))
    remote_total = _int(remote.get("total")) or total
    changes: Dict[str, Any] = {}

    if remote_watched and not watched:
        changes["playcount"] = 1
    elif not remote_watched and watched and not prudent:
        changes["playcount"] = 0

    if abs(remote_position - position) >= TOLERANCE:
        if not prudent:
            changes["resume"] = {"position": remote_position, "total": remote_total}
        elif remote_watched and not watched:
            # Fini sur l'autre TV : la reprise d'ici n'a plus lieu d'être
            changes["resume"] = {"position": remote_position, "total": remote_total}
        elif not watched and not position and remote_position:
            changes["resume"] = {"position": remote_position, "total": remote_total}

    if not changes:
        return None
    last_played = str(remote.get("last_played") or "")
    if last_played and last_played > str(details.get("lastplayed") or ""):
        # « Vu le » de l'autre TV : la rangée « Reprendre » trie là-dessus
        changes["lastplayed"] = last_played
    return changes


def describe(state: Mapping[str, Any]) -> str:
    """« The Expanse S02E05 (reprise 25:00) » pour le journal de Kodi."""
    title = str(state.get("title") or "?")
    if state.get("media_type") == "episode":
        title += f" S{_int(state.get('season')):02d}E{_int(state.get('episode')):02d}"
    if state.get("watched"):
        return f"{title} (vu)"
    position = _int(state.get("position"))
    if position:
        return f"{title} (reprise {position // 60}:{position % 60:02d})"
    return f"{title} (non vu)"


def batches(items: List[Any], size: int = UPLOAD_BATCH) -> Iterable[List[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


# ─────────────────────────────────────────────────────────────────────────────
# Mémoire de la TV : curseur et premier passage (fichier du profil de l'add-on)
# ─────────────────────────────────────────────────────────────────────────────


def load_memory(text: str) -> Dict[str, Any]:
    """{"cursor": "…", "uploaded": bool} ; valeurs par défaut si illisible."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return {"cursor": str(data.get("cursor") or ""), "uploaded": bool(data.get("uploaded"))}


def dump_memory(cursor: str, uploaded: bool) -> str:
    return json.dumps({"cursor": cursor, "uploaded": bool(uploaded)})


def is_first_pass(memory: Mapping[str, Any]) -> bool:
    """Jamais synchronisée : ni curseur, ni médiathèque déposée."""
    return not memory.get("cursor") and not memory.get("uploaded")


def library_update(method: str, data: Any) -> Optional[Tuple[str, int]]:
    """Notification Kodi « VideoLibrary.OnUpdate » → (type, n°) à déposer, ou None.

    Seuls les changements de « vu » comptent (`playcount` présent) : un scan
    de médiathèque (`added`) ou une mise à jour d'informations ne disent rien
    de ce qu'on a regardé, et risqueraient d'écraser l'état d'une autre TV.
    """
    if method != "VideoLibrary.OnUpdate":
        return None
    if isinstance(data, str):
        try:
            data = json.loads(data or "{}")
        except ValueError:
            return None
    if not isinstance(data, dict) or data.get("added") or "playcount" not in data:
        return None
    item = data.get("item") or {}
    kind, dbid = item.get("type"), _int(item.get("id"))
    if kind not in ID_ORDER or not dbid:
        return None
    return kind, dbid

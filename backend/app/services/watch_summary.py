"""Vu / reprise dans la web app et « Lire sur la TV » (add-on Kodi 1.19.0).

Les TV partagent déjà leur vu / reprise par la table `watch_states`
(phase 4.4). Ce module en tire ce qu'affiche la web app :

  - **badges** de la bibliothèque : film vu ou commencé (clé TMDB), série
    avec N épisodes vus (clé TVDB, celle que Sonarr donne) ;
  - **page Reprendre** : ce qui est commencé, le plus récent d'abord, avec
    l'affiche et le lien vers la fiche (médiathèque en cache) ;
  - **« Lire sur la TV »** : la web app demande à UNE TV appairée de lancer
    un titre. Le serveur ne parle pas à Kodi : il publie un événement
    `play_request` qui porte l'identifiant de la TV visée ; toutes les TV
    relèvent les événements toutes les 5 s, seule celle-là le prend.
    Analogie : un message sur un bus avec une adresse de destinataire,
    plutôt qu'une connexion entrante vers la TV (aucun port à ouvrir).

Garde-fou : une demande porte son heure (`at`) ; une TV qui la reçoit plus
de 2 min après (TV éteinte, redémarrage du serveur qui rejoue l'historique)
l'ignore. Jamais de lecture surprise.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services import watch_sync

CONTINUE_LIMIT = 40  # titres de la page Reprendre
REQUEST_TTL = 120  # s : au-delà, la TV ignore la demande de lecture
# s : une TV relève les événements toutes les 5 s, mais le serveur ne note
# son passage qu'une fois par minute (deps._LAST_SEEN_EVERY) : 2 min 30 de marge
ONLINE_SECONDS = 150


def progress(position: int, total: int) -> int | None:
    """Avancement en % (1-99), ou None sans reprise ni durée."""
    if position <= 0 or total <= 0:
        return None
    return max(1, min(99, round(position * 100 / total)))


def _library_index(library: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """{("movie", tmdb) / ("series", tvdb) → élément de la médiathèque}.

    Piège : dans la liste de la médiathèque, `tmdb_id` d'une SÉRIE contient
    son numéro TVDB (Sonarr ne connaît que lui) — c'est justement la clé des
    épisodes partagés par les TV.
    """
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for item in library or []:
        key = item.get("tmdb_id")
        if key and item.get("type") in ("movie", "series"):
            index.setdefault((item["type"], str(key)), item)
    return index


def _row_for(state: dict[str, Any], item: dict[str, Any] | None) -> dict[str, Any]:
    """État partagé + élément de la médiathèque → ligne de la page Reprendre."""
    is_movie = state["media_type"] == "movie"
    item = item or {}
    return {
        "media_type": state["media_type"],
        "id_type": state["id_type"],
        "id": state["id"],
        "season": state.get("season"),
        "episode": state.get("episode"),
        "title": item.get("title") or state.get("title") or "",
        "year": item.get("year") if is_movie else None,
        "poster_url": item.get("poster_url"),
        "fanart_url": item.get("fanart_url"),
        # Lien vers la fiche (/media/<type>/<id>) : absent si le titre n'est
        # plus dans Radarr / Sonarr
        "media_kind": item.get("type"),
        "media_id": item.get("external_id"),
        "position": state["position"],
        "total": state["total"],
        "progress": progress(state["position"], state["total"]),
        "device": state.get("device") or "",
        "updated_at": state["updated_at"],
    }


def summarize(states: list[dict[str, Any]], library: list[dict[str, Any]]) -> dict[str, Any]:
    """États partagés (`watch_sync.public`) + médiathèque → données de la web app.

    - `movies` : {tmdb → {watched, position, total, progress, device, updated_at}} ;
    - `series` : {tvdb → {watched_episodes, in_progress, last}} (`last` : le
      dernier épisode touché, pour « Reprendre S02E05 ») ;
    - `continue` : films et épisodes commencés, non finis, du plus récent au
      plus ancien (CONTINUE_LIMIT au plus).
    """
    movies: dict[str, dict[str, Any]] = {}
    series: dict[str, dict[str, Any]] = {}
    started: list[dict[str, Any]] = []
    for state in states or []:
        watched, position = bool(state.get("watched")), int(state.get("position") or 0)
        if state.get("media_type") == "movie":
            if state.get("id_type") == "tmdb":
                movies[str(state["id"])] = {
                    "watched": watched,
                    "position": position,
                    "total": int(state.get("total") or 0),
                    "progress": None
                    if watched
                    else progress(position, int(state.get("total") or 0)),
                    "device": state.get("device") or "",
                    "updated_at": state.get("updated_at") or "",
                }
        elif state.get("id_type") == "tvdb":
            entry = series.setdefault(
                str(state["id"]), {"watched_episodes": 0, "in_progress": 0, "last": None}
            )
            entry["watched_episodes"] += 1 if watched else 0
            entry["in_progress"] += 1 if position and not watched else 0
            last = entry["last"]
            if last is None or (state.get("updated_at") or "") > last["updated_at"]:
                entry["last"] = {
                    "season": state.get("season"),
                    "episode": state.get("episode"),
                    "watched": watched,
                    "position": position,
                    "total": int(state.get("total") or 0),
                    "device": state.get("device") or "",
                    "updated_at": state.get("updated_at") or "",
                }
        # Page Reprendre de la web app : films et épisodes (une vidéo de l'écran
        # Vidéos n'a ni fiche ni lien à ouvrir)
        if position and not watched and state.get("media_type") in ("movie", "episode"):
            started.append(state)

    index = _library_index(library)
    started.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
    rows = []
    for state in started[:CONTINUE_LIMIT]:
        kind = "movie" if state["media_type"] == "movie" else "series"
        id_ok = state.get("id_type") == ("tmdb" if kind == "movie" else "tvdb")
        rows.append(_row_for(state, index.get((kind, str(state["id"]))) if id_ok else None))
    return {"movies": movies, "series": series, "continue": rows}


# ─────────────────────────────────────────────────────────────────────────────
# « Lire sur la TV »
# ─────────────────────────────────────────────────────────────────────────────


# Jeton d'une vidéo de l'écran Vidéos (base64 d'URL, voir video_files)
FILE_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,2000}")


def play_request(device: dict[str, Any], raw: Any, now: datetime) -> dict[str, Any] | None:
    """Demande de la web app → données de l'événement `play_request` ; None si invalide.

    `device` : {id, name, room} de la TV visée. Le titre est désigné comme
    dans le vu partagé (TMDB pour un film, TVDB + saison + épisode pour un
    épisode) : la TV le retrouve dans SA médiathèque Kodi.
    """
    if not isinstance(raw, dict):
        return None
    state = watch_sync.normalize(
        {
            "media_type": raw.get("media_type"),
            "id_type": raw.get("id_type")
            or ("tmdb" if raw.get("media_type") == "movie" else "tvdb"),
            "id": raw.get("id"),
            "season": raw.get("season"),
            "episode": raw.get("episode"),
            "title": raw.get("title"),
        }
    )
    if state is None:
        return None
    extra: dict[str, Any] = {}
    if state["media_type"] == "file":
        # Vidéo d'un dossier (série maison) : la TV la lit par son jeton
        # (chemin opaque, vérifié par le serveur à la lecture) ; l'empreinte
        # ne sert qu'au vu / à la reprise
        token = str(raw.get("file") or "")
        if not FILE_TOKEN.fullmatch(token):
            return None
        extra["file"] = token
        try:
            extra["local_series"] = max(0, int(raw.get("local_series") or 0))
            extra["start"] = max(0, min(int(raw.get("start") or 0), 86_400))
        except (TypeError, ValueError):
            return None
    return {
        **extra,
        "device_id": int(device["id"]),
        "device": str(device.get("name") or ""),
        "room": str(device.get("room") or ""),
        "media_type": state["media_type"],
        "id_type": state["id_type"],
        "id": state["external_id"],
        "season": state["season"],
        "episode": state["episode"],
        "title": state["title"],
        # True : reprendre où on en était ; False : depuis le début
        "resume": raw.get("resume") is not False,
        "at": now.astimezone(UTC).isoformat(),
        "request_id": secrets.token_hex(6),
    }


def is_online(last_seen: datetime | None, now: datetime) -> bool:
    """La TV s'est manifestée récemment (elle recevra la demande dans les 5 s)."""
    if last_seen is None:
        return False
    return now - watch_sync.as_utc(last_seen) <= timedelta(seconds=ONLINE_SECONDS)


async def load_summary(db: Any) -> dict[str, Any]:
    """Toutes les lignes `watch_states` + médiathèque en cache → `summarize`."""
    from sqlalchemy import select

    from app.models.watch_state import WatchState
    from app.services.media_aggregator import cached_library

    # Profil « Famille » (celui des TV sous Kodi) : les autres profils ont
    # leur propre « Reprendre » dans l'appli TV (ADR-008)
    rows = (
        (await db.execute(select(WatchState).where(WatchState.profile_id.is_(None))))
        .scalars()
        .all()
    )
    states = [watch_sync.public(row) for row in rows]
    try:
        library = await cached_library(db)
    except Exception:  # *arr injoignables : badges quand même, sans affiches
        library = []
    return summarize(states, library)

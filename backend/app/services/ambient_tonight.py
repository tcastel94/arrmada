"""« Ce soir » : ce que la tablette propose quand rien ne passe sur la TV.

Entre deux films, l'écran d'appoint n'affiche plus seulement l'heure : il
aide à choisir quoi regarder, et lance le titre sur la TV de SA pièce d'un
simple toucher. Trois rangées, sans doublon :

  - **Reprendre** : films et épisodes commencés (vu partagé « Famille »,
    celui des TV), le plus récent d'abord ;
  - **Ma liste** : les titres de la liste « À voir » du profil Famille déjà
    sur le NAS ;
  - **Nouveaux films** : films arrivés ces 14 derniers jours, pas encore vus.

Chaque vignette porte sa demande de lecture (`play`), au format de « Lire
sur la TV » (watch_summary.play_request). Une série de « Ma liste » jamais
commencée n'en a pas : sans Sonarr, on ne sait pas quel épisode est sur le
disque — elle se lance depuis la TV.

Le calcul est une fonction pure (`build`) : testable sans base ni *arr.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

MAX_PER_ROW = 8
FRESH_DAYS = 14  # « Nouveaux films » : arrivés depuis moins de deux semaines


def _web(value: Any) -> str:
    """Image affichable par le navigateur de la tablette (http/https), sinon ""."""
    text = str(value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def _parse(value: Any) -> datetime | None:
    """Date ISO 8601 de Radarr (« 2026-10-20T18:03:11Z ») → datetime UTC."""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def play_key(play: dict[str, Any]) -> tuple[str, str, int, int]:
    """Identité d'une demande de lecture (pour vérifier ce que la tablette envoie)."""
    return (
        str(play.get("media_type") or ""),
        str(play.get("id") or ""),
        int(play.get("season") or 0),
        int(play.get("episode") or 0),
    )


def _movie_play(tmdb: Any, title: str, resume: bool) -> dict[str, Any]:
    return {"media_type": "movie", "id": str(tmdb), "season": None, "episode": None,
            "title": title, "resume": resume}  # fmt: skip


def _episode_play(tvdb: Any, season: int, episode: int, title: str) -> dict[str, Any]:
    return {"media_type": "episode", "id": str(tvdb), "season": int(season),
            "episode": int(episode), "title": title, "resume": True}  # fmt: skip


def _resume_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Ligne « Reprendre » du vu partagé → vignette ; None si la TV ne la trouverait pas."""
    if not row.get("media_id"):
        return None  # plus dans Radarr / Sonarr : la TV ne la retrouverait pas
    title = str(row.get("title") or "")
    if row.get("media_type") == "movie":
        play = _movie_play(row["id"], title, True)
        subtitle = str(row.get("year") or "")
        kind = "movie"
    else:
        season, episode = row.get("season"), row.get("episode")
        if not isinstance(season, int) or not isinstance(episode, int):
            return None
        play = _episode_play(row["id"], season, episode, title)
        subtitle = f"S{season:02d}E{episode:02d}"
        kind = "episode"
    return {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "poster": _web(row.get("poster_url")),
        "fanart": _web(row.get("fanart_url")),
        "progress": row.get("progress"),
        "play": play,
    }


def build(
    summary: dict[str, Any],
    library: list[dict[str, Any]],
    watchlist: list[dict[str, Any]],
    now: datetime,
) -> dict[str, list[dict[str, Any]]]:
    """Vu partagé (`watch_summary.summarize`) + médiathèque + liste Famille → 3 rangées."""
    seen: set[str] = set()  # « movie:<tmdb> » / « series:<tvdb> » déjà proposés

    resume: list[dict[str, Any]] = []
    for row in summary.get("continue") or []:
        tile = _resume_row(row)
        if tile is None:
            continue
        ref = f"{'movie' if tile['kind'] == 'movie' else 'series'}:{row['id']}"
        if ref in seen:
            continue  # deux épisodes commencés de la même série : le plus récent
        seen.add(ref)
        resume.append(tile)
        if len(resume) >= MAX_PER_ROW:
            break

    movies = summary.get("movies") or {}
    series = summary.get("series") or {}
    mine: list[dict[str, Any]] = []
    for item in watchlist or []:
        if not item.get("has_file"):
            continue  # pas encore sur le NAS : rien à lancer ce soir
        ext = str(item.get("external_id") or "")
        ref = f"{item.get('media_type')}:{ext}"
        if ref in seen:
            continue
        title = str(item.get("title") or "")
        if item.get("media_type") == "movie":
            if (movies.get(ext) or {}).get("watched"):
                continue  # déjà vu : il n'a plus sa place dans « à voir » ce soir
            play: dict[str, Any] | None = _movie_play(ext, title, True)
            subtitle = str(item.get("year") or "")
            kind = "movie"
        else:
            last = (series.get(ext) or {}).get("last")
            # Série déjà commencée : l'épisode en cours ; sinon lancée depuis la TV
            play = (
                _episode_play(ext, last["season"], last["episode"], title)
                if last and not last.get("watched")
                and isinstance(last.get("season"), int) and isinstance(last.get("episode"), int)
                else None
            )  # fmt: skip
            subtitle = "Série"
            kind = "series"
        seen.add(ref)
        mine.append({
            "kind": kind, "title": title, "subtitle": subtitle,
            "poster": _web(item.get("poster_url")), "fanart": _web(item.get("fanart_url")),
            "progress": None, "play": play,
        })  # fmt: skip
        if len(mine) >= MAX_PER_ROW:
            break

    since = now - timedelta(days=FRESH_DAYS)
    candidates = []
    for item in library or []:
        if item.get("type") != "movie" or not item.get("has_file") or not item.get("tmdb_id"):
            continue
        added = _parse(item.get("added"))
        tmdb = str(item["tmdb_id"])
        state = movies.get(tmdb) or {}
        if added is None or added < since or state.get("watched") or state.get("position"):
            continue  # ancien, déjà vu ou commencé (il est alors dans « Reprendre »)
        if f"movie:{tmdb}" in seen:
            continue
        candidates.append((added, item))
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    fresh = [
        {
            "kind": "movie",
            "title": str(item.get("title") or ""),
            "subtitle": str(item.get("year") or ""),
            "poster": _web(item.get("poster_url")),
            "fanart": _web(item.get("fanart_url")),
            "progress": None,
            "play": _movie_play(item["tmdb_id"], str(item.get("title") or ""), False),
        }
        for _added, item in candidates[:MAX_PER_ROW]
    ]
    return {"resume": resume, "watchlist": mine, "fresh": fresh}


def offered(tonight: dict[str, list[dict[str, Any]]]) -> set[tuple[str, str, int, int]]:
    """Toutes les lectures proposées : la tablette ne peut lancer que celles-là."""
    return {play_key(tile["play"]) for row in tonight.values() for tile in row if tile.get("play")}

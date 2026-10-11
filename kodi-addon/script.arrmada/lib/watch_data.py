# -*- coding: utf-8 -*-
"""Vu, en cours, à suivre : d'après la médiathèque Kodi (ADR-004, phase 4.1).

Logique pure, sans Kodi (testée en CI). Elle reçoit les réponses JSON-RPC de
la médiathèque Kodi (VideoLibrary.GetEpisodes, GetMovies…) et prépare ce que
les écrans affichent :

  - l'écran Série : saisons, épisodes (vu, progression, résumé), l'épisode
    à lancer en premier (« Lire la suite ») ;
  - la rangée « Reprendre » : films et épisodes commencés, plus l'épisode
    suivant de chaque série en cours, du plus récent au plus ancien ;
  - l'état des films et séries dans les listes (coche « vu », barre de
    progression) et dans la Fiche (« Reprendre à 42:10 »).

Pourquoi Kodi et pas le serveur : c'est Kodi qui a le fichier, la position
de reprise et le compteur de lectures de CET appareil (ADR-004 § 1).
"""

from __future__ import annotations

from datetime import date, datetime, timezone, tzinfo
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SPECIALS = 0  # saison 0 de Kodi : épisodes spéciaux
MIN_RESUME = 10  # s : en dessous, ce n'est pas une vraie reprise
CHAIN_LIMIT = 30  # épisodes enchaînés au plus après celui qu'on lance
CONTINUE_LIMIT = 20  # éléments de la rangée « Reprendre »

MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip


# ─────────────────────────────────────────────────────────────────────────────
# Petits formats
# ─────────────────────────────────────────────────────────────────────────────


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def clock(seconds: Any) -> str:
    """Position lisible : 754 → « 12:34 », 3723 → « 1:02:03 »."""
    total = max(0, _int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def duration_label(seconds: Any) -> str:
    """Durée : 3120 → « 52 min », 9300 → « 2 h 35 », 0 → ''."""
    minutes = round(max(0, _int(seconds)) / 60)
    if minutes <= 0:
        return ""
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest:02d}" if rest else f"{hours} h"


def bar_name(position: Any, total: Any) -> str:
    """Barre pré-rendue (pas de 2 %) : 30 s sur 90 → « bar-034 » ; '' sans durée."""
    pos, tot = max(0, _int(position)), _int(total)
    if tot <= 0 or pos <= 0:
        return ""
    pct = min(100.0, pos * 100 / tot)
    return f"bar-{int(round(pct / 2)) * 2:03d}"


def aired_label(value: Any) -> str:
    """« 2022-02-18 » → « 18 février 2022 » ; '' si illisible."""
    text = str(value or "").strip()[:10]
    try:
        day = date.fromisoformat(text)
    except ValueError:
        return ""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _known_year(year: int) -> bool:
    """Kodi renvoie 1970 (ou 0) quand l'année d'une série est inconnue."""
    return year > 1900 and year != 1970


def season_label(number: int) -> str:
    return "Épisodes spéciaux" if number == SPECIALS else f"Saison {number}"


def episode_code(season: Any, episode: Any) -> str:
    """« S01E04 » (ce que l'écran d'appoint et la web app affichent aussi)."""
    return f"S{_int(season):02d}E{_int(episode):02d}"


def resume_of(item: Mapping[str, Any]) -> Tuple[int, int]:
    """(position, durée) de reprise d'un élément Kodi ; (0, durée) s'il n'y en a pas.

    Kodi donne `resume: {position, total}` ; `total` peut valoir 0 (fichier
    jamais ouvert jusqu'au bout) : on prend alors la durée annoncée.
    """
    resume = item.get("resume") or {}
    position = _int(resume.get("position"))
    total = _int(resume.get("total")) or _int(item.get("runtime"))
    if position < MIN_RESUME or (total and position >= total):
        position = 0
    return position, total


def is_watched(item: Mapping[str, Any]) -> bool:
    return _int(item.get("playcount")) > 0


def state_label(watched: bool, position: int) -> str:
    """Ce qu'on dit d'un titre : « Reprendre à 12:34 », « Vu » ou rien."""
    if position:
        return f"Reprendre à {clock(position)}"
    return "Vu" if watched else ""


# ─────────────────────────────────────────────────────────────────────────────
# Épisodes et saisons (écran Série)
# ─────────────────────────────────────────────────────────────────────────────


def _order(item: Mapping[str, Any]) -> Tuple[int, int, int]:
    """Spéciaux en dernier, puis saison, puis épisode."""
    season = _int(item.get("season"))
    return (1 if season == SPECIALS else 0, season, _int(item.get("episode")))


def sort_episodes(episodes: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return sorted((e for e in episodes or [] if isinstance(e, Mapping)), key=_order)


def episode_model(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Épisode Kodi → ce que l'écran Série affiche."""
    season, number = _int(item.get("season")), _int(item.get("episode"))
    title = str(item.get("title") or item.get("label") or "").strip()
    watched = is_watched(item)
    position, total = resume_of(item)
    art = item.get("art") or {}
    return {
        "episodeid": _int(item.get("episodeid")),
        "season": season,
        "episode": number,
        "code": episode_code(season, number),
        "title": title or f"Épisode {number}",
        "label": f"{number}. {title}" if title else f"Épisode {number}",
        "duration": duration_label(total or item.get("runtime")),
        "aired": aired_label(item.get("firstaired")),
        "plot": str(item.get("plot") or "").strip(),
        "thumb": art.get("thumb") or art.get("tvshow.fanart") or art.get("fanart") or "",
        "watched": watched,
        "resume": position,
        "total": total,
        "bar": bar_name(position, total),
        "status": state_label(watched, position),
        "lastplayed": str(item.get("lastplayed") or ""),
    }


def next_episode(episodes: Iterable[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """L'épisode à lancer avec « Lire la suite », ou None si tout est vu.

    1. Un épisode commencé (le plus récemment regardé) : on le reprend.
    2. Sinon, le premier non vu APRÈS le dernier vu (on ne revient pas sur
       un épisode sauté plus tôt dans la série).
    3. Rien de vu : le tout premier épisode. Les spéciaux sont ignorés.
    """
    regular = [e for e in sort_episodes(episodes) if _int(e.get("season")) != SPECIALS]
    started = [e for e in regular if resume_of(e)[0] and not is_watched(e)]
    if started:
        return max(started, key=lambda e: str(e.get("lastplayed") or ""))
    last_seen = max((i for i, e in enumerate(regular) if is_watched(e)), default=-1)
    return next((e for e in regular[last_seen + 1 :] if not is_watched(e)), None)


def chain_after(
    episodes: Iterable[Mapping[str, Any]], episodeid: int, limit: int = CHAIN_LIMIT
) -> List[int]:
    """Épisodes à enchaîner après celui qu'on lance (même s'ils sont déjà vus).

    On suit l'ordre de la série, d'une saison à la suivante. Depuis un
    épisode spécial, on n'enchaîne rien (ils ne se suivent pas).
    """
    ordered = sort_episodes(episodes)
    index = next((i for i, e in enumerate(ordered) if _int(e.get("episodeid")) == episodeid), None)
    if index is None or _int(ordered[index].get("season")) == SPECIALS:
        return []
    following = [
        _int(e.get("episodeid"))
        for e in ordered[index + 1 :]
        if _int(e.get("season")) != SPECIALS and _int(e.get("episodeid"))
    ]
    return following[:limit]


def season_models(episodes: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Saisons présentes (spéciaux en dernier), avec « 3 / 9 vus » et une barre."""
    counts: Dict[int, List[int]] = {}
    for item in episodes:
        seen_total = counts.setdefault(_int(item.get("season")), [0, 0])
        seen_total[0] += 1 if is_watched(item) else 0
        seen_total[1] += 1
    out = []
    for number in sorted(counts, key=lambda n: (n == SPECIALS, n)):
        seen, total = counts[number]
        out.append(
            {
                "season": number,
                "label": season_label(number),
                "progress": "Vue" if seen == total else f"{seen} / {total} vus",
                "bar": bar_name(seen, total) or "bar-000",
                "watched": seen,
                "total": total,
            }
        )
    return out


def build_show(show: Mapping[str, Any], episodes: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Écran Série complet : en-tête, saisons, épisodes par saison, point de départ."""
    ordered = sort_episodes(episodes)
    seasons = season_models(ordered)
    by_season: Dict[int, List[Dict[str, Any]]] = {s["season"]: [] for s in seasons}
    for item in ordered:
        by_season[_int(item.get("season"))].append(episode_model(item))

    nxt = next_episode(ordered)
    start_season, start_episode = 0, 0
    if nxt is not None:
        numbers = [s["season"] for s in seasons]
        start_season = numbers.index(_int(nxt.get("season")))
        start_episode = next(
            i
            for i, e in enumerate(by_season[_int(nxt.get("season"))])
            if e["episodeid"] == _int(nxt.get("episodeid"))
        )

    regular = [s for s in seasons if s["season"] != SPECIALS]
    total = sum(s["total"] for s in regular)
    seen = sum(s["watched"] for s in regular)
    meta = []
    year = _int(show.get("year"))
    if _known_year(year):
        meta.append(str(year))
    if regular:
        meta.append(f"{len(regular)} saison{'s' if len(regular) > 1 else ''}")
    if total:
        meta.append(f"{total} épisode{'s' if total > 1 else ''}")
        meta.append("tout vu" if seen == total else f"{seen} vu{'s' if seen > 1 else ''}")
    art = show.get("art") or {}

    if nxt is None:
        play_label = "Revoir depuis le début" if ordered else ""
    else:
        model = by_season[_int(nxt.get("season"))][start_episode]
        verb = "Reprendre" if model["resume"] else "Lire"
        play_label = f"{verb} {model['code']}"

    return {
        "title": str(show.get("title") or show.get("label") or ""),
        "plot": str(show.get("plot") or "").strip(),
        "meta": " · ".join(meta),
        "poster": art.get("poster") or "",
        "fanart": art.get("fanart") or "",
        "clearlogo": art.get("clearlogo") or "",
        "seasons": seasons,
        "episodes": by_season,
        "next_id": _int(nxt.get("episodeid")) if nxt is not None else 0,
        "play_label": play_label,
        "start_season": start_season,
        "start_episode": start_episode,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Épisodes manquants ou à venir (Sonarr), dans l'écran Série (phase 4.4)
# ─────────────────────────────────────────────────────────────────────────────

# Sorte d'épisode absent de la médiathèque Kodi → (badge sur la vignette, état)
MISSING_KINDS = {
    "nas": ("Sur le NAS", "Sur le NAS · scan de Kodi en attente"),
    "aired": ("Manquant", "Manquant · OK pour le chercher"),
    "upcoming": ("À venir", ""),  # l'état dit la date de diffusion
    "tba": ("À venir", "Date de diffusion inconnue"),
}


def _air_moment(value: Any) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def detail_line(episode: Mapping[str, Any]) -> str:
    """Ligne sous le titre de l'épisode sélectionné : « état · diffusion · durée ».

    Sans morceau vide ni séparateur en trop, et sans répéter la date quand
    l'état la dit déjà (« Diffusion le 18 octobre 2026 »).
    """
    status, aired = str(episode.get("status") or ""), str(episode.get("aired") or "")
    parts = [status, "" if aired and aired in status else aired, episode.get("duration") or ""]
    return " · ".join(str(part) for part in parts if part)


def missing_kind(item: Mapping[str, Any], now: datetime) -> str:
    """« nas », « aired », « upcoming », « tba » ; "" si on ne le montre pas.

    Un épisode diffusé mais non suivi dans Sonarr (vieille saison qu'on ne
    veut pas) n'est pas affiché : seuls comptent ceux qu'on attend.
    """
    if item.get("has_file"):
        return "nas"
    if not item.get("monitored"):
        return ""
    moment = _air_moment(item.get("air_date"))
    if moment is None:
        return "tba"
    return "aired" if moment <= now else "upcoming"


def missing_model(
    item: Mapping[str, Any], kind: str, tz: Optional[tzinfo] = None
) -> Dict[str, Any]:
    """Épisode connu de Sonarr seulement → même forme que `episode_model`."""
    season, number = _int(item.get("season")), _int(item.get("episode"))
    title = str(item.get("title") or "").strip()
    if title.upper() == "TBA":
        title = ""
    moment = _air_moment(item.get("air_date"))
    local = (moment.astimezone(tz) if tz else moment.astimezone()) if moment else None
    aired = aired_label(local.date().isoformat()) if local else ""
    badge, status = MISSING_KINDS[kind]
    if kind == "upcoming":
        status = f"Diffusion le {aired}" if aired else "À venir"
    return {
        "episodeid": 0,
        "season": season,
        "episode": number,
        "code": episode_code(season, number),
        "title": title or f"Épisode {number}",
        "label": f"{number}. {title}" if title else f"Épisode {number}",
        "duration": "",
        "aired": aired,
        "plot": str(item.get("overview") or "").strip(),
        "thumb": "",
        "watched": False,
        "resume": 0,
        "total": 0,
        "bar": "",
        "status": status,
        "lastplayed": "",
        "missing": kind,
        "badge": badge,
    }


def add_missing(
    model: Mapping[str, Any],
    sonarr_episodes: Iterable[Mapping[str, Any]],
    now: Optional[datetime] = None,
    tz: Optional[tzinfo] = None,
) -> Dict[str, Any]:
    """Écran Série complété par les épisodes que Sonarr connaît et Kodi pas.

    Les épisodes absents s'intercalent à leur place (grisés à l'écran), une
    saison entièrement absente est ajoutée (« À venir » / « Manquante »).
    Le point de départ (épisode à suivre) reste le même épisode.
    """
    now = now or datetime.now(timezone.utc)
    episodes = {season: list(items) for season, items in model["episodes"].items()}
    present = {(e["season"], e["episode"]) for items in episodes.values() for e in items}
    added = 0
    for item in sonarr_episodes or []:
        season, number = _int(item.get("season")), _int(item.get("episode"))
        if season == SPECIALS or number <= 0 or (season, number) in present:
            continue
        kind = missing_kind(item, now)
        if not kind:
            continue
        episodes.setdefault(season, []).append(missing_model(item, kind, tz))
        present.add((season, number))
        added += 1
    if not added:
        return dict(model)

    known = {s["season"]: s for s in model["seasons"]}
    seasons = []
    for number in sorted(episodes, key=lambda n: (n == SPECIALS, n)):
        episodes[number].sort(key=lambda e: e["episode"])
        if number in known:
            seasons.append(known[number])
            continue
        waiting = any(e.get("missing") in ("upcoming", "tba") for e in episodes[number])
        seasons.append(
            {
                "season": number,
                "label": season_label(number),
                "progress": "À venir" if waiting else "Manquante",
                "bar": "bar-000",
                "watched": 0,
                "total": 0,
            }
        )

    result = dict(model, seasons=seasons, episodes=episodes)
    next_id = model.get("next_id") or 0
    for index, season in enumerate(seasons):
        for position, episode in enumerate(episodes[season["season"]]):
            if next_id and episode["episodeid"] == next_id:
                result["start_season"], result["start_episode"] = index, position
    if not next_id and model["seasons"]:
        # Rien à suivre : on garde la saison de départ d'origine
        first = model["seasons"][model.get("start_season", 0)]["season"]
        result["start_season"] = [s["season"] for s in seasons].index(first)
        result["start_episode"] = 0
    result["missing"] = added
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Rangée « Reprendre » (films et épisodes commencés + épisode suivant)
# ─────────────────────────────────────────────────────────────────────────────


def _continue_movie(item: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    position, total = resume_of(item)
    if not position:
        return None
    art = item.get("art") or {}
    left = duration_label(total - position) if total > position else ""
    return {
        "kind": "movie",
        "dbid": _int(item.get("movieid")),
        "tvshowid": 0,
        "title": str(item.get("title") or item.get("label") or ""),
        "subtitle": str(_int(item.get("year"))) if _known_year(_int(item.get("year"))) else "",
        "status": f"Reprendre à {clock(position)}" + (f" · reste {left}" if left else ""),
        "poster": art.get("poster") or art.get("thumb") or "",
        "thumb": art.get("fanart") or art.get("thumb") or art.get("poster") or "",
        "fanart": art.get("fanart") or "",
        "resume": position,
        "total": total,
        "bar": bar_name(position, total),
        "plot": str(item.get("plot") or ""),
        "lastplayed": str(item.get("lastplayed") or ""),
        "tmdb_id": str((item.get("uniqueid") or {}).get("tmdb") or ""),
    }


def _continue_episode(
    item: Mapping[str, Any], show: Optional[Mapping[str, Any]] = None, upcoming: bool = False
) -> Dict[str, Any]:
    model = episode_model(item)
    art = item.get("art") or {}
    show = show or {}
    if upcoming:
        status = "Épisode suivant"
    else:
        left = duration_label(model["total"] - model["resume"]) if model["total"] else ""
        status = f"Reprendre à {clock(model['resume'])}" + (f" · reste {left}" if left else "")
    return {
        "kind": "episode",
        "dbid": model["episodeid"],
        "tvshowid": _int(item.get("tvshowid") or show.get("tvshowid")),
        "season": model["season"],
        "episode": model["episode"],
        "episode_title": model["title"],
        "title": str(item.get("showtitle") or show.get("title") or ""),
        "subtitle": f"{model['code']} · {model['title']}",
        "status": status,
        "poster": art.get("tvshow.poster") or (show.get("art") or {}).get("poster") or "",
        "thumb": model["thumb"],
        "fanart": art.get("tvshow.fanart") or (show.get("art") or {}).get("fanart") or "",
        "resume": model["resume"],
        "total": model["total"],
        "bar": model["bar"],
        "plot": model["plot"],
        # L'épisode suivant n'a jamais été lu : on le date du passage de la série
        "lastplayed": str(show.get("lastplayed") or "") if upcoming else model["lastplayed"],
        "tmdb_id": "",
    }


def continue_feed(
    movies: Iterable[Mapping[str, Any]],
    episodes: Iterable[Mapping[str, Any]],
    next_ups: Iterable[Tuple[Mapping[str, Any], Mapping[str, Any]]],
    limit: int = CONTINUE_LIMIT,
) -> List[Dict[str, Any]]:
    """Rangée « Reprendre », du plus récemment regardé au plus ancien.

    `movies`, `episodes` : éléments EN COURS (filtre « inprogress » de Kodi).
    `next_ups` : (série en cours, son épisode suivant non vu). Une série
    n'apparaît qu'une fois : l'épisode commencé passe avant l'épisode suivant.
    """
    rows: List[Dict[str, Any]] = []
    for movie in movies or []:
        row = _continue_movie(movie)
        if row:
            rows.append(row)
    shows_seen = set()
    for item in episodes or []:
        if not resume_of(item)[0]:
            continue
        row = _continue_episode(item)
        shows_seen.add(row["tvshowid"])
        rows.append(row)
    for show, item in next_ups or []:
        tvshowid = _int(show.get("tvshowid") or item.get("tvshowid"))
        if tvshowid in shows_seen or not item:
            continue
        shows_seen.add(tvshowid)
        rows.append(_continue_episode(item, show, upcoming=True))
    rows.sort(key=lambda r: r["lastplayed"], reverse=True)
    return rows[:limit]


# ─────────────────────────────────────────────────────────────────────────────
# Films et séries des listes ArrMada : état dans la médiathèque Kodi
# ─────────────────────────────────────────────────────────────────────────────


def movie_state(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Film Kodi → {"movieid", "watched", "resume", "total", "status"}."""
    position, total = resume_of(item)
    watched = is_watched(item)
    return {
        "movieid": _int(item.get("movieid")),
        "watched": watched,
        "resume": position,
        "total": total,
        "status": state_label(watched, position),
    }


def show_state(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Série Kodi → {"tvshowid", "watched", "total", "status"}."""
    total, seen = _int(item.get("episode")), _int(item.get("watchedepisodes"))
    if total and seen >= total:
        status = "Tout vu"
    elif seen:
        status = f"{seen} / {total} épisodes vus"
    else:
        status = ""
    return {
        "tvshowid": _int(item.get("tvshowid")),
        "watched": seen,
        "total": total,
        "status": status,
    }


def library_index(items: Iterable[Mapping[str, Any]], unique: str) -> Dict[str, Mapping[str, Any]]:
    """Index {identifiant TMDB/TVDB → élément Kodi} pour retrouver un titre du serveur."""
    index: Dict[str, Mapping[str, Any]] = {}
    for item in items or []:
        value = str((item.get("uniqueid") or {}).get(unique) or "").strip()
        if value:
            index.setdefault(value, item)
    return index


def annotate(
    entries: List[Dict[str, Any]],
    movies: Mapping[str, Mapping[str, Any]],
    shows: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Ajoute aux entrées des listes l'état Kodi (vu, reprise, épisodes vus).

    Le skin affiche alors sa coche « vu » et sa barre de progression ; le
    menu de l'appui long propose « Marquer comme vu / non vu ». Les entrées
    absentes de la médiathèque Kodi restent telles quelles.
    """
    for entry in entries:
        ids = entry.get("ids") or {}
        info = entry.setdefault("info", {})
        props = entry.setdefault("props", {})
        if ids.get("tmdb") and ids["tmdb"] in movies:
            state = movie_state(movies[ids["tmdb"]])
            info["playcount"] = 1 if state["watched"] else 0
            if state["resume"]:
                info["resume"] = (state["resume"], state["total"])
            props["kodi_status"] = state["status"]
            # Pour les écrans ArrMada (grille) : pastille « Vu », barre de reprise
            props["watched"] = "1" if state["watched"] else ""
            props["bar"] = bar_name(state["resume"], state["total"])
            _add_watch_ops(entry, state["watched"])
        elif ids.get("tvdb") and ids["tvdb"] in shows:
            state = show_state(shows[ids["tvdb"]])
            info["playcount"] = 1 if state["total"] and state["watched"] >= state["total"] else 0
            props["TotalEpisodes"] = state["total"]
            props["WatchedEpisodes"] = state["watched"]
            props["UnWatchedEpisodes"] = max(0, state["total"] - state["watched"])
            props["kodi_status"] = state["status"]
            done = bool(state["total"]) and state["watched"] >= state["total"]
            props["watched"] = "1" if done else ""
            props["bar"] = "" if done else bar_name(state["watched"], state["total"])
    return entries


def _add_watch_ops(entry: Dict[str, Any], watched: bool) -> None:
    """« Marquer comme vu » OU « non vu » (jamais les deux, même après un changement)."""
    ops = [op for op in entry.get("context") or [] if op not in ("seen", "unseen")]
    ops.append("unseen" if watched else "seen")
    entry["context"] = ops


def continue_entries(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Rangée « Reprendre » → entrées de liste (lib/listing.py) : dossier et widget.

    OK lance la lecture par la logique d'ArrMada (reprise, enchaînement,
    préréglage de l'ampli) ; l'appui long propose Lire depuis le début,
    Marquer comme vu et, pour un épisode, Ouvrir la série.
    """
    out = []
    for row in rows or []:
        is_movie = row.get("kind") == "movie"
        action = {
            "action": "resume_play",
            "type": row.get("kind"),
            "id": str(row.get("dbid") or ""),
        }
        context = ["restart"] if row.get("resume") else []
        context.append("seen")
        # État en tête du résumé : le libellé secondaire est remplacé par la
        # durée dans les listes de Kodi, le résumé est toujours affiché.
        status, plot = row.get("status") or "", row.get("plot") or ""
        info: Dict[str, Any] = {
            "title": row.get("title") if is_movie else row.get("episode_title"),
            "plot": f"{status}[CR]{plot}" if status and plot else status or plot,
            "mediatype": "movie" if is_movie else "episode",
            "playcount": 0,
            "duration": _int(row.get("total")),
        }
        if not is_movie:
            info.update(
                tvshowtitle=row.get("title") or "",
                season=_int(row.get("season")),
                episode=_int(row.get("episode")),
            )
            action["tvshowid"] = str(row.get("tvshowid") or "")
            context.append("series")
        if row.get("resume"):
            info["resume"] = (_int(row.get("resume")), _int(row.get("total")))
        art = {
            "thumb": row.get("thumb") or row.get("poster") or "",
            "poster": row.get("poster") or "",
            "fanart": row.get("fanart") or "",
            "icon": row.get("thumb") or row.get("poster") or "",
        }
        if not is_movie:
            art["tvshow.poster"] = row.get("poster") or ""
        code = episode_code(row.get("season"), row.get("episode"))
        out.append(
            {
                "label": row.get("title") if is_movie else f"{row.get('title')} · {code}",
                "label2": " · ".join(p for p in (row.get("subtitle"), row.get("status")) if p),
                "info": info,
                "ids": {},
                "art": {k: v for k, v in art.items() if v},
                "action": action,
                "context": context,
                "props": {"status": row.get("status") or ""},
                "folder": False,
            }
        )
    return out

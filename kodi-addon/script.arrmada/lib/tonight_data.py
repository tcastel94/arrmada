# -*- coding: utf-8 -*-
"""« Ce soir » : ce qu'on peut regarder avant l'heure choisie (1.18.0).

Logique pure, sans Kodi (testée en CI).

L'écran « Ce soir » est la grille ArrMada avec, en onglets, des heures de
fin : « Avant 22:00 », « Avant 22:30 »… « Sans limite ». Pour chaque onglet,
on ne garde que ce qui sera FINI avant l'heure dite, en partant de
maintenant :

  1. ce qui est commencé (film ou épisode) : il reste durée − reprise ;
  2. l'épisode suivant des séries en cours ;
  3. les films jamais vus de la médiathèque, du plus récemment ajouté au
     plus ancien.

Chaque affiche dit « fini vers 22:14 ». C'est un `at` à l'envers : au lieu
de « lance ça à 22 h », on demande « qu'est-ce qui tient avant 22 h ».

L'heure vient de l'horloge de la TV (System.Time de Kodi) : sur Android,
l'heure locale de Python n'est pas toujours la bonne. Piège vu sur le banc :
Kodi suit le réglage régional 12 h / 24 h quel que soit le format demandé
(« HH » est lu « hh »). On demande donc « hh:mm:ss xx » et on convertit
« 05:43:58 PM » en 17:43:58 ; une région en 24 h répond « 17:43:58 ».
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import watch_data

LEAD = timedelta(minutes=45)  # le 1er horaire laisse au moins 45 min
STEP = timedelta(minutes=30)  # puis un horaire toutes les 30 min
SLOTS = 5  # horaires proposés avant « Sans limite »
TARGET = timedelta(hours=2)  # onglet ouvert d'office : le 1er à 2 h ou plus
FRESH_LIMIT = 40  # films jamais vus examinés (les plus récents)
CONTINUE_LIMIT = 40  # éléments commencés / épisodes suivants examinés
ANY = "any"  # clé de l'onglet « Sans limite »

GROUP_ORDER = {"resume": 0, "next": 1, "fresh": 2}


# ─────────────────────────────────────────────────────────────────────────────
# Heure et onglets
# ─────────────────────────────────────────────────────────────────────────────


def tv_now(label: Any, today: datetime) -> datetime:
    """« 21:47 », « 21:47:05 » ou « 09:47:05 PM » (horloge de la TV) → datetime du jour.

    `today` sert de date (et de secours si l'heure est illisible).
    """
    text = str(label or "").strip().upper()
    suffix = ""
    if text.endswith(("AM", "PM")):
        text, suffix = text[:-2].strip(), text[-2:]
    parts = text.split(":")
    try:
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) > 2 else 0
        if suffix == "PM" and hour < 12:
            hour += 12
        elif suffix == "AM" and hour == 12:
            hour = 0  # 12:05 AM = 00:05
        return today.replace(hour=hour, minute=minute, second=second, microsecond=0)
    except (ValueError, IndexError):
        return today.replace(microsecond=0)


def clock_label(moment: datetime) -> str:
    """22:14 (à la minute la plus proche, comme les durées) ; minuit → « minuit »."""
    moment = moment + timedelta(seconds=30)
    if moment.hour == 0 and moment.minute == 0:
        return "minuit"
    return moment.strftime("%H:%M")


def _round_up(moment: datetime) -> datetime:
    """Heure ronde ou demi-heure suivante (22:07 → 22:30, 22:30 → 22:30)."""
    base = moment.replace(second=0, microsecond=0)
    if moment.second or moment.microsecond:
        base += timedelta(minutes=1)
    extra = (-base.minute) % 30
    return base + timedelta(minutes=extra)


def deadlines(now: datetime) -> List[Tuple[str, str, Optional[datetime]]]:
    """Onglets (clé, libellé, heure limite) : 5 horaires puis « Sans limite ».

    À 20:47 : 20:47 + 45 min = 21:32, arrondi à 22:00 → Avant 22:00, 22:30,
    23:00, 23:30, minuit, puis Sans limite.
    """
    first = _round_up(now + LEAD)
    tabs: List[Tuple[str, str, Optional[datetime]]] = []
    for index in range(SLOTS):
        moment = first + STEP * index
        tabs.append((moment.strftime("%H:%M"), f"Avant {clock_label(moment)}", moment))
    tabs.append((ANY, "Sans limite", None))
    return tabs


def default_tab(tabs: Sequence[Tuple[str, str, Optional[datetime]]], now: datetime) -> int:
    """Onglet ouvert d'office : le 1er qui laisse 2 h (la durée d'un film)."""
    for index, (_, _, moment) in enumerate(tabs):
        if moment is not None and moment - now >= TARGET:
            return index
    return len(tabs) - 1 if tabs else 0


# ─────────────────────────────────────────────────────────────────────────────
# Candidats
# ─────────────────────────────────────────────────────────────────────────────


def fresh_movie(item: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Film Kodi jamais vu → ligne au format de « Reprendre » (watch_data)."""
    if watch_data.is_watched(item):
        return None
    position, total = watch_data.resume_of(item)
    if position:
        return None  # commencé : il vient déjà de « Reprendre »
    art = item.get("art") or {}
    year = watch_data._int(item.get("year"))
    return {
        "kind": "movie",
        "dbid": watch_data._int(item.get("movieid")),
        "tvshowid": 0,
        "title": str(item.get("title") or item.get("label") or ""),
        "subtitle": str(year) if watch_data._known_year(year) else "",
        "status": "",
        "poster": art.get("poster") or art.get("thumb") or "",
        "thumb": art.get("fanart") or art.get("thumb") or art.get("poster") or "",
        "fanart": art.get("fanart") or "",
        "resume": 0,
        "total": total,
        "bar": "",
        "plot": str(item.get("plot") or ""),
        "lastplayed": "",
        "tmdb_id": str((item.get("uniqueid") or {}).get("tmdb") or ""),
    }


def group_of(row: Mapping[str, Any]) -> str:
    """« resume » (commencé), « next » (épisode suivant) ou « fresh » (jamais vu)."""
    if watch_data._int(row.get("resume")):
        return "resume"
    return "next" if row.get("kind") == "episode" else "fresh"


def candidates(
    continue_rows: Iterable[Mapping[str, Any]], movies: Iterable[Mapping[str, Any]]
) -> List[Dict[str, Any]]:
    """Commencés, puis épisodes suivants, puis films jamais vus (sans doublon).

    `continue_rows` : la rangée « Reprendre » (watch_data.continue_feed),
    `movies` : films Kodi non vus, du plus récemment ajouté au plus ancien.
    """
    rows = [dict(row) for row in continue_rows or []]
    seen = {("movie", row.get("dbid")) for row in rows if row.get("kind") == "movie"}
    for item in movies or []:
        row = fresh_movie(item)
        if row and ("movie", row["dbid"]) not in seen:
            seen.add(("movie", row["dbid"]))
            rows.append(row)
    # Tri stable : l'ordre de chaque groupe (récemment regardé, ajouté) est gardé
    rows.sort(key=lambda row: GROUP_ORDER[group_of(row)])
    return rows


def remaining(row: Mapping[str, Any]) -> int:
    """Secondes qu'il reste à regarder ; 0 si la durée est inconnue."""
    total = watch_data._int(row.get("total"))
    return max(0, total - watch_data._int(row.get("resume"))) if total else 0


def status_of(row: Mapping[str, Any], finish: Optional[datetime]) -> str:
    """« Reprise à 42:10 · fini vers 22:14 », « 1 h 52 · fini vers 22:40 »…"""
    left = remaining(row)
    group = group_of(row)
    if group == "resume":
        head = f"Reprise à {watch_data.clock(row.get('resume'))}"
    elif group == "next":
        head = "Épisode suivant"
    else:
        head = watch_data.duration_label(left) if left else ""
    if finish is None:
        tail = "durée inconnue"
    else:
        tail = f"fini vers {clock_label(finish)}"
        if group != "fresh":
            tail = f"reste {watch_data.duration_label(left)} · {tail}"
    return " · ".join(part for part in (head, tail) if part)


def tonight_rows(
    rows: Iterable[Mapping[str, Any]], now: datetime, deadline: Optional[datetime]
) -> List[Dict[str, Any]]:
    """Ce qui sera fini avant `deadline` (None : tout), avec « fini vers HH:MM ».

    Durée inconnue : seulement dans « Sans limite » (on ne promet rien).
    """
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        left = remaining(row)
        finish = now + timedelta(seconds=left) if left else None
        if deadline is not None and (finish is None or finish > deadline):
            continue
        result = dict(row)
        result["status"] = status_of(row, finish)
        result["finish"] = clock_label(finish) if finish else ""
        out.append(result)
    return out


def tonight_entries(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Lignes → entrées de la grille (mêmes actions que « Reprendre »).

    OK lance la lecture par la logique d'ArrMada (reprise, épisodes
    enchaînés) ; l'appui long propose Lire depuis le début, Marquer comme vu…
    En haut de la grille : « fini vers 22:14 · S02E05 · Titre ».
    """
    rows = list(rows or [])
    entries = watch_data.continue_entries(rows)
    for entry, row in zip(entries, rows):
        entry["label2"] = row.get("subtitle") or ""
        props = entry.setdefault("props", {})
        props["kodi_status"] = row.get("status") or ""
        props["bar"] = row.get("bar") or ""
        props["finish"] = row.get("finish") or ""
    return entries


def empty_message(label: str) -> str:
    """Rien ne tient avant l'heure choisie : on le dit, et quoi faire."""
    if label == "Sans limite":
        return "Rien à proposer : la médiathèque Kodi est vide ou tout est vu."
    return f"Rien ne se termine {label.lower()} : essaie un horaire plus tard."

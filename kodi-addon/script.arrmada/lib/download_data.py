# -*- coding: utf-8 -*-
"""Feuille « Télécharger » : la logique, sans Kodi (testée en CI).

L'écran (lib/download_window.py) ne fait qu'afficher ce que ces fonctions
préparent : choix de la portée (toute la série / une saison / un épisode),
saisons, épisodes cochés, libellé du bouton et corps envoyé au serveur
(POST /api/kodi/media/download, ADR-005).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

# Portées d'une série, dans l'ordre de la rangée
SCOPES = (
    ("series", "Toute la série"),
    ("season", "Une saison"),
    ("episode", "Un épisode"),
)


def entry_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Paramètres d'une URL du plugin (« media_details ») → entrée de la feuille."""

    def num(key: str) -> Optional[int]:
        value = str(params.get(key) or "")
        return int(value) if value.isdigit() and int(value) > 0 else None

    kind = params.get("type") or params.get("kind") or "movie"
    return {
        "kind": "series" if kind in ("series", "tvshow", "tv") else "movie",
        "title": params.get("title") or "",
        "year": params.get("year") or "",
        "tmdb_id": num("tmdb_id"),
        "tvdb_id": num("tvdb_id"),
        "arr_id": num("arr_id"),
        "in_library": params.get("in_library") == "1",
        "overview": params.get("overview") or params.get("plot") or "",
        "poster": params.get("poster_url") or params.get("poster") or "",
        "fanart": params.get("fanart") or "",
    }


def scope_items(selected: str, seasons: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Les 3 cases de la rangée « portée », avec leur sous-titre."""
    total = sum(int(s.get("episodes") or 0) for s in seasons)
    whole = f"{plural(len(seasons), 'saison')}" + (
        f" · {plural(total, 'épisode')}" if total else ""
    )
    hints = {"series": whole if seasons else "tout ce qui existe", "season": "au choix",
             "episode": "précis"}  # fmt: skip
    return [
        {
            "key": key,
            "label": label,
            "label2": hints[key],
            "selected": "1" if key == selected else "",
        }
        for key, label in SCOPES
    ]


def season_items(seasons: List[Dict[str, Any]], selected: Optional[int]) -> List[Dict[str, str]]:
    """Pastilles « Saison 1 », « Saison 2 »… avec ce qui est déjà sur le NAS."""
    items = []
    for season in seasons:
        number = int(season.get("number") or 0)
        total, have = int(season.get("episodes") or 0), int(season.get("have") or 0)
        if total and have >= total:
            detail = "complète"
        elif have:
            detail = f"{have}/{total} sur le NAS"
        elif total:
            detail = plural(total, "épisode")
        else:
            detail = ""
        items.append(
            {
                "number": str(number),
                "label": f"Saison {number}",
                "label2": detail,
                "selected": "1" if number == selected else "",
            }
        )
    return items


def episode_items(episodes: List[Dict[str, Any]], picked: Set[int]) -> List[Dict[str, str]]:
    """Lignes d'épisodes : code, titre, état (déjà là / à venir) et coche."""
    items = []
    for ep in episodes:
        number = int(ep.get("number") or 0)
        season = int(ep.get("season") or 0)
        if ep.get("has_file"):
            state, note = "have", "Déjà sur le NAS"
        elif not ep.get("aired", True):
            when = french_date(ep.get("air_date") or "")
            state, note = "future", f"Sortie le {when}" if when else "À venir"
        else:
            state = note = ""
        runtime = int(ep.get("runtime") or 0)
        items.append(
            {
                "number": str(number),
                "code": f"S{season:02d}E{number:02d}",
                "label": ep.get("title") or f"Épisode {number}",
                "state": state,
                "note": note or (f"{runtime} min" if runtime else ""),
                "picked": "1" if number in picked else "",
            }
        )
    return items


def toggle_pick(picked: Set[int], number: int) -> Set[int]:
    """OK sur un épisode : coché ↔ décoché (plusieurs épisodes possibles)."""
    return picked - {number} if number in picked else picked | {number}


def button_label(kind: str, scope: str, season: Optional[int], picked: Set[int]) -> str:
    """Le bouton dit exactement ce qui va partir."""
    if kind == "movie":
        return "Télécharger le film"
    if scope == "series":
        return "Télécharger toute la série"
    if season is None:
        return "Choisis une saison"
    if scope == "season":
        return f"Télécharger la saison {season}"
    if not picked:
        return "Coche un épisode"
    if len(picked) == 1:
        return f"Télécharger S{season:02d}E{next(iter(picked)):02d}"
    return f"Télécharger {len(picked)} épisodes"


def ready(kind: str, scope: str, season: Optional[int], picked: Set[int]) -> bool:
    """Assez d'informations pour envoyer la demande ?"""
    if kind == "movie" or scope == "series":
        return True
    if season is None:
        return False
    return scope == "season" or bool(picked)


def payload(
    entry: Dict[str, Any], scope: str, season: Optional[int], picked: Set[int], tonight: bool
) -> Dict[str, Any]:
    """Corps de POST /api/kodi/media/download."""
    body: Dict[str, Any] = {
        "type": entry.get("kind", "movie"),
        "title": entry.get("title") or "",
        "priority": bool(tonight),
    }
    for key in ("tmdb_id", "tvdb_id", "arr_id"):
        if entry.get(key):
            body[key] = entry[key]
    if entry.get("kind") == "series":
        body["scope"] = scope
        if scope in ("season", "episode"):
            body["season"] = season
        if scope == "episode":
            body["episodes"] = sorted(picked)
    return body


def tonight_hint(tonight: bool) -> str:
    if tonight:
        return "Passe devant les autres téléchargements"
    return "Rejoint la file normale"


def summary(kind: str, seasons: List[Dict[str, Any]], source: str = "") -> str:
    """Ligne sous le titre de la feuille."""
    if kind == "movie":
        return "Qualité et dossier habituels · sous-titres français automatiques"
    if not seasons:
        return "Saisons en cours de chargement…"
    total = sum(int(s.get("episodes") or 0) for s in seasons)
    have = sum(int(s.get("have") or 0) for s in seasons)
    parts = [plural(len(seasons), "saison")]
    if total:
        parts.append(plural(total, "épisode"))
    if have:
        parts.append(f"{have} déjà sur le NAS")
    return " · ".join(parts)


def episodes_note(source: str, episodes: List[Dict[str, Any]]) -> str:
    """Pourquoi la liste d'épisodes est vide (série pas encore suivie, sans TMDB)."""
    if episodes:
        return ""
    if source == "sonarr":
        return "Épisodes connus une fois la série ajoutée : choisis la saison entière."
    return "Aucun épisode pour cette saison."


def result_message(result: Any) -> Dict[str, Any]:
    """Réponse du serveur → {ok, title, message} pour la notification de la TV."""
    if not isinstance(result, dict):
        return {"ok": False, "title": "Télécharger", "message": "Serveur injoignable"}
    ok = result.get("status") == "ok"
    message = str(result.get("message") or ("C'est parti" if ok else "Échec de la demande"))
    return {"ok": ok, "title": str(result.get("title") or "Télécharger"), "message": message,
            "available": result.get("code") == "available"}  # fmt: skip


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'s' if count > 1 else ''}"


_MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.",
           "nov.", "déc.")  # fmt: skip


def french_date(iso: str) -> str:
    """« 2026-11-03 » → « 3 nov. 2026 » ; illisible → ""."""
    try:
        year, month, day = (int(p) for p in iso[:10].split("-"))
        return f"{day} {_MONTHS[month - 1]} {year}"
    except (ValueError, IndexError):
        return ""

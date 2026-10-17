# -*- coding: utf-8 -*-
"""Films et Séries de la médiathèque ArrMada (add-on 1.9.0) — logique pure, sans Kodi.

Jusqu'ici, l'appli ne montrait que les ajouts récents, les manquants et le
calendrier. « Films » et « Séries » donnent accès à TOUTE la bibliothèque
de Radarr / Sonarr, par vues :

  Tous, de A à Z · Ajoutés récemment · Par genre · En 4K (films) ·
  Pas encore disponibles

Tri et filtres faits par le serveur (`GET /api/media`), sur toute la
bibliothèque ; la TV ne reçoit qu'une page à la fois (PER_PAGE titres), avec
une entrée « Page suivante ». Charger 2 000 films d'un coup ferait ramer la
Shield.
"""

from __future__ import annotations

from typing import Any, Dict, List, NamedTuple, Tuple

from screens_data import genre_fr

PER_PAGE = 100

# Type de l'API → (titre affiché, contenu annoncé au skin pour choisir la vue)
KINDS: Dict[str, Tuple[str, str]] = {
    "movie": ("Films", "movies"),
    "series": ("Séries", "tvshows"),
}


class View(NamedTuple):
    key: str
    label: str
    plot: str
    params: Dict[str, Any]  # paramètres de /api/media
    kinds: Tuple[str, ...]  # types concernés


VIEWS: Tuple[View, ...] = (
    View(
        "all",
        "Tous, de A à Z",
        "Toute la bibliothèque, par ordre alphabétique",
        {"sort": "title", "order": "asc"},
        ("movie", "series"),
    ),
    View(
        "recent",
        "Ajoutés récemment",
        "Les derniers ajoutés à Radarr / Sonarr en premier",
        {"sort": "added", "order": "desc"},
        ("movie", "series"),
    ),
    View("genres", "Par genre", "Science-fiction, Comédie, Animation…", {}, ("movie", "series")),
    View(
        "uhd",
        "En 4K",
        "Les films dont le fichier est en 2160p",
        {"min_resolution": 2160, "sort": "title", "order": "asc"},
        ("movie",),
    ),
    View(
        "missing",
        "Pas encore disponibles",
        "Suivis, mais sans fichier sur le NAS pour l'instant",
        {"availability": "missing", "sort": "added", "order": "desc"},
        ("movie", "series"),
    ),
)
_BY_KEY = {view.key: view for view in VIEWS}


def views_for(kind: str) -> List[View]:
    """Vues proposées pour un type (« En 4K » : films seulement)."""
    return [view for view in VIEWS if kind in view.kinds]


def browse_query(kind: str, view: str, genre: str = "", page: int = 1) -> Dict[str, Any]:
    """Paramètres de /api/media pour une vue (ValueError si la demande est absurde)."""
    if kind not in KINDS:
        raise ValueError(f"type inconnu : {kind}")
    if view == "genre":
        if not genre:
            raise ValueError("genre manquant")
        params: Dict[str, Any] = {"genre": genre, "sort": "title", "order": "asc"}
    else:
        chosen = _BY_KEY.get(view)
        if chosen is None or chosen.key == "genres" or kind not in chosen.kinds:
            raise ValueError(f"vue inconnue : {view}")
        params = dict(chosen.params)
    params.update({"type": kind, "page": max(1, int(page)), "per_page": PER_PAGE})
    return params


def view_title(kind: str, view: str, genre: str = "") -> str:
    """Titre du dossier : « Films · En 4K », « Séries · Science-fiction »."""
    family = KINDS.get(kind, ("ArrMada", ""))[0]
    if view == "genre":
        return f"{family} · {genre_fr(genre)}"
    chosen = _BY_KEY.get(view)
    return f"{family} · {chosen.label}" if chosen else family


def page_info(payload: Any) -> Tuple[int, int, int]:
    """(page, nombre de pages, nombre de titres) d'une réponse de /api/media."""
    meta = payload.get("pagination") if isinstance(payload, dict) else None
    meta = meta if isinstance(meta, dict) else {}
    try:
        page = max(1, int(meta.get("page") or 1))
        pages = max(1, int(meta.get("total_pages") or 1))
        total = max(0, int(meta.get("total") or 0))
    except (TypeError, ValueError):
        return 1, 1, 0
    return page, pages, total


def next_page_label(page: int, pages: int) -> str:
    return f"Page suivante ({page + 1} / {pages})"


def genre_choices(facets: Any) -> List[Tuple[str, str]]:
    """[(nom du genre pour le serveur, « Science-fiction (42) »)], par ordre alphabétique.

    Le serveur garde les genres en anglais (Radarr / Sonarr) : on filtre avec
    ce nom-là, on affiche la traduction.
    """
    counts = facets.get("genre_counts") if isinstance(facets, dict) else None
    if not isinstance(counts, dict):
        names = facets.get("genres") if isinstance(facets, dict) else None
        counts = {name: 0 for name in names or [] if isinstance(name, str)}
    rows = []
    for name, count in counts.items():
        if not name:
            continue
        label = genre_fr(name)
        rows.append((name, f"{label} ({count})" if count else label))
    return sorted(rows, key=lambda row: row[1].casefold())

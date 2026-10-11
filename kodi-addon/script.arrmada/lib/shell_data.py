# -*- coding: utf-8 -*-
"""Coquille ArrMada : accueil média, grille, retour automatique (ADR-004, phases 4.2-4.3).

Logique pure, sans Kodi (testée en CI). Elle décide :
  - du menu principal et des rangées de l'accueil média ;
  - de l'en-tête (« héros ») qui décrit l'élément sélectionné ;
  - du moment où la grille Films / Séries charge la page suivante ;
  - du moment où le service rouvre ArrMada quand l'accueil de Kodi s'affiche
    (démarrage, retour d'un add-on…), sans jamais enfermer l'utilisateur.

Les éléments manipulés ici sont des « entrées » de liste (lib/catalog_data.py,
lib/watch_data.py) : {label, label2, info, art, action, context, props}.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Menu principal (clé, libellé). « board » : l'ancien Accueil (tableau de bord).
MENU: Tuple[Tuple[str, str], ...] = (
    ("home", "Accueil"),
    ("movies", "Films"),
    ("series", "Séries"),
    ("apps", "Applis"),  # add-ons, TV en direct, dossiers du NAS, favoris (4.3)
    ("discover", "Découvrir"),
    ("search", "Rechercher"),
    ("queue", "Téléchargements"),
    ("salon", "Salon"),
    ("board", "Tableau de bord"),
    ("settings", "Réglages"),
)

# Rangées de l'accueil média, de haut en bas (clé, titre).
ROWS: Tuple[Tuple[str, str], ...] = (
    ("continue", "Reprendre"),
    ("apps", "Tes applis"),  # favoris Kodi, TV en direct, add-ons vidéo (4.3)
    ("recent", "Ajouts récents"),
    ("foryou", "Pour toi"),
    ("upcoming", "Bientôt"),
)
ROW_LIMIT = 30  # éléments par rangée au plus

# Retour → « Quitter ? » (clé, libellé). Toujours une porte de sortie vers Kodi.
QUIT_CHOICES: Tuple[Tuple[str, str], ...] = (
    ("stay", "Rester dans ArrMada"),
    ("kodi", "Passer à l'interface Kodi"),  # jusqu'au prochain démarrage de Kodi
    ("kodi_settings", "Réglages de Kodi"),
    ("quit", "Quitter Kodi"),
)

# Découvrir : onglets de la grille (sous-flux de « foryou »).
DISCOVER_TABS: Tuple[Tuple[str, str], ...] = (
    ("foryou", "Pour toi"),
    ("movies", "Films tendance"),
    ("tvshows", "Séries tendance"),
)

# Recherche (4.3) : résultats dans la grille, filtrés par onglet ; « new »
# rouvre le clavier.
SEARCH_TABS: Tuple[Tuple[str, str], ...] = (
    ("all", "Tout"),
    ("movie", "Films"),
    ("series", "Séries"),
    ("new", "Nouvelle recherche"),
)

GRID_COLUMNS = 7  # affiches par ligne dans la grille (1920 px)
PRELOAD_ROWS = 2  # lignes d'avance : la page suivante arrive avant qu'on l'atteigne

# Retour automatique : au-delà de OPEN_LIMIT ouvertures en OPEN_WINDOW s, on
# arrête (un écran qui se fermerait tout seul ne doit pas tourner en boucle).
OPEN_LIMIT = 3
OPEN_WINDOW = 60.0
OPEN_RETRY = 10.0  # s avant de réessayer une ouverture restée sans effet

# Propriétés de la fenêtre Home de Kodi (mémoire commune à tout Kodi) :
SHELL_PROP = "arrmada.shell"  # « 1 » tant que l'accueil ArrMada est ouvert
SHELL_OFF = "arrmada.shell_off"  # « 1 » : « Interface Kodi » choisi (cette session)


# ─────────────────────────────────────────────────────────────────────────────
# Accueil média
# ─────────────────────────────────────────────────────────────────────────────


def limit_rows(rows: Mapping[str, Sequence[Any]]) -> Dict[str, List[Any]]:
    """Rangées connues, chacune limitée à ROW_LIMIT éléments (les autres : vides)."""
    return {key: list(rows.get(key) or [])[:ROW_LIMIT] for key, _ in ROWS}


def first_row(rows: Mapping[str, Sequence[Any]]) -> Optional[str]:
    """Première rangée non vide (là où l'on pose le focus en arrivant)."""
    return next((key for key, _ in ROWS if rows.get(key)), None)


def hero(entry: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """En-tête de l'accueil : ce qu'on sait de l'élément sélectionné.

    Le résumé des éléments de « Reprendre » commence par leur état (« Reprendre
    à 12:34[CR]… ») : l'en-tête l'affiche à part, en couleur.
    """
    if not entry:
        return {key: "" for key in ("title", "meta", "plot", "status", "fanart", "clearlogo")}
    art = entry.get("art") or {}
    info = entry.get("info") or {}
    props = entry.get("props") or {}
    status = str(props.get("status") or props.get("kodi_status") or "")
    plot = str(info.get("plot") or "")
    meta = str(entry.get("label2") or "")
    if status and meta.endswith(f" · {status}"):
        meta = meta[: -len(status) - 3]  # l'état s'affiche déjà à part
    if status and plot.startswith(status):
        plot = plot[len(status) :].lstrip()
        plot = plot[4:] if plot.startswith("[CR]") else plot
    return {
        "title": str(entry.get("label") or info.get("title") or ""),
        "meta": meta,
        "plot": plot,
        "status": status,
        # Pas de fond : la vignette agrandie, sauf pour une icône (applis, 4.3)
        "fanart": art.get("fanart") or ("" if props.get("icon_only") else art.get("thumb") or ""),
        "clearlogo": art.get("clearlogo") or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Grille Films / Séries / Découvrir
# ─────────────────────────────────────────────────────────────────────────────


def need_more(
    selected: int,
    loaded: int,
    page: int,
    pages: int,
    columns: int = GRID_COLUMNS,
    ahead: int = PRELOAD_ROWS,
) -> bool:
    """Charger la page suivante ? Oui à `ahead` lignes de la fin de ce qui est chargé."""
    return page < pages and loaded > 0 and selected >= loaded - columns * ahead


def tab_index(tabs: Sequence[Tuple[str, str]], key: str) -> int:
    return next((i for i, (k, _) in enumerate(tabs) if k == key), 0)


def grid_status(shown: int, total: int, loading: bool) -> str:
    """« 100 / 2 431 titres » (espace fine des milliers), « … » pendant le chargement."""
    if loading and not shown:
        return "Chargement…"
    if total and total > shown:
        return f"{shown:,} / {total:,} titres".replace(",", " ")
    return f"{shown:,} titre{'s' if shown > 1 else ''}".replace(",", " ")


# ─────────────────────────────────────────────────────────────────────────────
# Retour automatique sur ArrMada (service)
# ─────────────────────────────────────────────────────────────────────────────


def should_open_shell(state: Mapping[str, Any]) -> bool:
    """Le service doit-il rouvrir l'accueil ArrMada maintenant ?

    Seulement si l'accueil de KODI est à l'écran, sans fenêtre par-dessus ni
    vidéo en cours, et que l'utilisateur n'a pas choisi « Interface Kodi ».
    `state` : enabled, safe_mode, suspended, home_active, modal, playing,
    shell_open, opening_age (s depuis la dernière ouverture demandée, None).
    """
    if not state.get("enabled") or state.get("safe_mode") or state.get("suspended"):
        return False
    if not state.get("home_active") or state.get("modal") or state.get("playing"):
        return False
    if state.get("shell_open"):
        return False
    age = state.get("opening_age")
    return age is None or age >= OPEN_RETRY


def opens_too_often(history: Iterable[float], now: float) -> bool:
    """Trop d'ouvertures récentes : l'écran se ferme tout seul, on arrête."""
    return sum(1 for t in history if now - t <= OPEN_WINDOW) >= OPEN_LIMIT

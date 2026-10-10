# -*- coding: utf-8 -*-
"""Liens de la TV vers la web app (ADR-003 § 7, phase 3) — logique pure, sans Kodi.

Ce qui ne se fait pas sur la TV (nettoyage, configuration, page complète
d'un titre) s'ouvre sur le téléphone : la TV affiche un QR code
(lib/qr_window.py) fabriqué par le serveur (`GET /api/qr`), qui seul connaît
l'adresse de la web app.
"""

from __future__ import annotations

import hashlib
from typing import Dict, NamedTuple, Optional


class WebPage(NamedTuple):
    path: str  # chemin dans la web app
    title: str  # titre de la fenêtre QR
    text: str  # ce qu'on y trouvera


# Pages de la web app proposées depuis la TV
PAGES: Dict[str, WebPage] = {
    "home": WebPage(
        "/dashboard",
        "ArrMada sur ton téléphone",
        "Le tableau de bord complet : services, stockage, activité, réglages.",
    ),
    "cleanup": WebPage(
        "/health",
        "Maintenance du NAS",
        "Nettoyage des fichiers orphelins et santé de la stack : depuis la web app "
        "seulement, aucune suppression n'est possible depuis une TV.",
    ),
    "devices": WebPage(
        "/settings/kodi",
        "Appareils et mises à jour",
        "Nom, pièce et ampli de chaque TV ; révocation d'un appareil.",
    ),
}


def media_path(kind: str, arr_id) -> str:
    """Page web d'un titre (« /media/movie/12 », « /media/series/7 ») ; "" si inconnu."""
    if not str(arr_id or "").isdigit():
        return ""
    family = "series" if kind in ("tvshow", "series", "tv", "episode") else "movie"
    return f"/media/{family}/{arr_id}"


def qr_file_name(url: str) -> str:
    """Nom du fichier image du QR code, propre à l'adresse.

    Kodi garde les images en cache par chemin : un même nom pour deux QR
    codes différents afficherait l'ancien.
    """
    return f"arrmada-qr-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:12]}.png"


def android_open_url(url: str) -> Optional[str]:
    """Commande Kodi qui ouvre l'adresse dans le navigateur d'Android.

    None si l'adresse contient de quoi casser la commande (guillemet, virgule
    hors requête…) : le bouton n'est alors pas proposé.
    """
    if not url.startswith(("http://", "https://")) or any(ch in url for ch in '"\\\n '):
        return None
    return f'StartAndroidActivity("","android.intent.action.VIEW","","{url}")'


# ─────────────────────────────────────────────────────────────────────────────
# Raccourcis : favoris Kodi vers les écrans ArrMada (phase 3)
# ─────────────────────────────────────────────────────────────────────────────

PLUGIN = "plugin://script.arrmada/"

# (titre du favori, action de l'add-on)
SHORTCUTS = (
    ("ArrMada · Accueil", "home"),
    ("ArrMada · Téléchargements", "queue"),
    ("ArrMada · Salon", "salon"),
    ("ArrMada · Rechercher", "search_input"),
)

# Écrans ouverts par l'add-on (fenêtres, clavier…), pas des listes : lancés
# depuis un favori, Kodi les appelle comme une lecture (PlayMedia).
WINDOW_ACTIONS = frozenset({"home", "queue", "salon", "pair", "search_input", "qr", "settings"})


def shortcut_path(action: str) -> str:
    return f"{PLUGIN}?action={action}"


def missing_shortcuts(favourites: list) -> list:
    """Raccourcis absents des favoris (réponse de Favourites.GetFavourites).

    Ajouter un favori qui existe déjà le RETIRERAIT (Kodi fait « ajouter ou
    enlever ») : on n'ajoute que ceux qui manquent.
    """
    existing = {
        str(fav.get("path") or fav.get("windowparameter") or "").strip('"')
        for fav in favourites or []
        if isinstance(fav, dict)
    }
    return [(title, action) for title, action in SHORTCUTS if shortcut_path(action) not in existing]

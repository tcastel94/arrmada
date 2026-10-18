# -*- coding: utf-8 -*-
"""Bulles ArrMada dans les écrans ArrMada (appli 1.24.1) : la logique, sans Kodi.

Pourquoi : la bulle standard de Kodi (Dialog().notification) est dessinée par
le skin (Aeon Nox SiLVO) en HAUT de l'écran, pile sur le menu des écrans
ArrMada ; une extension ne peut pas la déplacer. Quand un écran ArrMada est à
l'écran, on affiche donc notre propre bulle, en bas à droite, dessinée par
l'écran lui-même (bloc commun tools/toast_xml.py). Ailleurs (écrans de Kodi,
film en cours), la bulle Kodi reste la bonne.

Fonctionnement, façon file de messages :
  - qui veut afficher une bulle (service, écran, action) la dépose dans une
    file, une propriété de la fenêtre Accueil de Kodi (mémoire partagée par
    tous les scripts de l'appli) ;
  - le service, qui tourne en boucle toutes les secondes, la dépile : il
    affiche une bulle, l'efface à l'échéance, passe à la suivante ;
  - le service publie un « battement » à chaque tour : sans battement récent
    (service arrêté), on retombe sur la bulle Kodi, jamais de bulle figée.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# Écrans plein écran d'ArrMada qui portent le bloc de bulle (tools/toast_xml.py).
# Pas l'appairage (aucune notification avant), pas les pop-ups (dialogues).
WINDOWS = (
    "script-arrmada-shell.xml",
    "script-arrmada-home.xml",
    "script-arrmada-grid.xml",
    "script-arrmada-series.xml",
    "script-arrmada-detail.xml",
    "script-arrmada-download.xml",
    "script-arrmada-downloads.xml",
    "script-arrmada-apps.xml",
    "script-arrmada-salon.xml",
)
# Condition Kodi « un écran ArrMada est à l'écran »
ON_SCREEN = " | ".join(f"Window.IsActive({name})" for name in WINDOWS)

# Propriétés de la fenêtre Accueil de Kodi (id 10000)
PROP = "arrmada.toast"  # "1" tant qu'une bulle est affichée (lue par le XML)
HEADING = "arrmada.toast.heading"
MESSAGE = "arrmada.toast.message"
ICON = "arrmada.toast.icon"
ERROR = "arrmada.toast.error"  # "1" : titre en rouge
UNTIL = "arrmada.toast.until"  # échéance (horloge du système, en secondes)
QUEUE = "arrmada.toast.queue"  # bulles en attente (JSON)
BEAT = "arrmada.toast.beat"  # dernier tour de boucle du service

DEFAULT_MS = 5000
MIN_MS = 2500
MAX_MS = 10000
QUEUE_MAX = 4  # au-delà, les plus anciennes sont abandonnées
BEAT_STALE = 10  # s sans battement : service arrêté

# Emojis et pictogrammes absents de la police de la TV (carré vide à l'écran)
SYMBOLS = re.compile(
    "[\U0001f000-\U0001faff\u2190-\u21ff\u2300-\u23ff\u25a0-\u25ff"
    "\u2600-\u27bf\u2b00-\u2bff\ufe0f\u200d]"
)
# Flèches de chemin (« Paramètres → Avancé ») : « › », que la police sait dessiner
_ARROWS = str.maketrans({"\u2192": "\u203a", "\u21d2": "\u203a", "\u279c": "\u203a"})


def clean(text: Any) -> str:
    """Texte affichable par la police de la TV : sans emoji, espaces normalisés."""
    return " ".join(SYMBOLS.sub(" ", str(text or "").translate(_ARROWS)).split())


def bubble(
    heading: Any, message: Any, icon: Any = "", ms: Any = DEFAULT_MS, error: bool = False
) -> Dict[str, Any]:
    """Une bulle prête à afficher (textes nettoyés, durée bornée)."""
    try:
        duration = int(ms)
    except (TypeError, ValueError):
        duration = DEFAULT_MS
    return {
        "heading": clean(heading) or "ArrMada",
        "message": clean(message),
        "icon": str(icon or ""),
        "ms": max(MIN_MS, min(MAX_MS, duration)),
        "error": bool(error),
    }


def alive(beat: Any, now: float) -> bool:
    """Le service tourne-t-il (battement de moins de BEAT_STALE secondes) ?"""
    try:
        return now - float(beat) < BEAT_STALE
    except (TypeError, ValueError):
        return False


def decode(raw: Any) -> List[Dict[str, Any]]:
    """File lue dans la propriété (illisible → vide)."""
    try:
        items = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def encode(items: List[Dict[str, Any]]) -> str:
    return json.dumps(items, ensure_ascii=False) if items else ""


def enqueue(raw: Any, item: Dict[str, Any]) -> str:
    """Ajoute une bulle à la file (sans doublon consécutif, QUEUE_MAX au plus)."""
    items = decode(raw)
    if items and items[-1] == item:
        return encode(items)
    items.append(item)
    return encode(items[-QUEUE_MAX:])


def step(
    raw: Any, until: Any, now: float, on_screen: bool
) -> Tuple[str, Optional[Dict[str, Any]], str]:
    """Un tour de boucle du service : (action, bulle, nouvelle file).

    Actions :
      "idle"     rien à faire (ou bulle affichée pas encore échue) ;
      "clear"    effacer la bulle affichée (échue, ou écran ArrMada quitté) ;
      "show"     afficher la bulle renvoyée ;
      "fallback" plus d'écran ArrMada : la bulle part dans la bulle Kodi.
    Un tour « vide » sépare deux bulles : l'animation d'apparition rejoue.
    """
    items = decode(raw)
    try:
        deadline = float(until or 0)
    except (TypeError, ValueError):
        deadline = 0.0
    if deadline:
        if on_screen and now < deadline:
            return "idle", None, encode(items)
        return "clear", None, encode(items)
    if not items:
        return "idle", None, ""
    first = items.pop(0)
    return ("show" if on_screen else "fallback"), first, encode(items)

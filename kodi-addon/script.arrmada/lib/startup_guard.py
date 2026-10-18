# -*- coding: utf-8 -*-
"""Disjoncteur de démarrage du service — logique pure, sans Kodi.

Le même principe que `StartLimitBurst` de systemd : si Kodi se ferme deux
fois de suite peu après le démarrage du service, le service passe tout seul
en **mode minimal** au démarrage suivant. Il fait alors seulement ce que
faisait la 1.4.2 (suivi de lecture, alertes de fin de téléchargement), sans
cache des listes ni relevé des événements. Kodi redevient utilisable sans
avoir à brancher un PC sur la Shield.

Comment on sait que Kodi s'est fermé ? Le service note « démarrage en cours »
dans un petit fichier, et l'efface quand :
  - il a tourné normalement pendant HEALTHY_AFTER secondes ;
  - ou Kodi l'arrête proprement (sortie de Kodi, mise à jour de l'add-on).
Si Kodi plante avant, la note reste : au démarrage suivant, le compteur
monte. Au-delà de TRIP_AFTER démarrages interrompus d'affilée : mode minimal.

Pour en sortir : Paramètres de l'add-on → Avancé → décocher « Mode minimal ».
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

STATE_FILE = "service-state.json"
TRIP_AFTER = 2  # démarrages interrompus d'affilée avant le mode minimal
HEALTHY_AFTER = 120  # secondes de fonctionnement normal = démarrage réussi


def state_path(profile_dir: str) -> str:
    return os.path.join(profile_dir, STATE_FILE)


def load(path: str) -> Dict[str, Any]:
    """État enregistré ({} si absent ou illisible : on repart de zéro)."""
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save(path: str, state: Dict[str, Any]) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(tmp, path)


def on_start(state: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Démarrage du service : (nouvel état à enregistrer, mode minimal ?).

    En mode minimal, le compteur est remis à zéro : quand on réactive le
    fonctionnement normal, on repart sur deux essais.
    """
    try:
        unfinished = int(state.get("unfinished_starts") or 0)
    except (TypeError, ValueError):
        unfinished = 0
    if unfinished >= TRIP_AFTER:
        return {"unfinished_starts": 0, "tripped": True}, True
    return {"unfinished_starts": unfinished + 1}, False


def healthy() -> Dict[str, Any]:
    """État après un démarrage réussi (ou un arrêt propre)."""
    return {"unfinished_starts": 0}

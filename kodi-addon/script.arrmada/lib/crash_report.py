# -*- coding: utf-8 -*-
"""Journal de plantage de Kodi envoyé au serveur — logique pure, sans Kodi.

Pourquoi : certains plantages n'arrivent que sur la Shield (Kodi 21 Android)
et jamais sur le banc de test. Sans PC branché sur la TV, le journal de la
session plantée est perdu. Comme un `journalctl -b -1` lu après un reboot
inattendu, le service relit au démarrage `kodi.old.log` (la session
précédente : Kodi renomme kodi.log en kodi.old.log à chaque démarrage).

Comment on sait que Kodi s'est arrêté net : un arrêt normal finit par la
ligne « Exiting the application... » (Application.cpp de Kodi 20 et 21).
Si elle manque, c'est un plantage, ou un arrêt forcé (Android qui tue Kodi
en arrière-plan, débranchement) : la fin du journal part au serveur, qui
la range dans data/kodi-crashes/.

Une seule fois par journal : son empreinte (taille + date) est notée dans
le profil de l'add-on, le service relancé (mise à jour de l'add-on) ne
renvoie pas le même.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

LOG_NAME = "kodi.old.log"
CLEAN_EXIT = "Exiting the application"  # dernière ligne d'un arrêt normal
MAX_BYTES = 400_000  # fin du journal envoyée (les dernières minutes)
END_BYTES = 4096  # où chercher la ligne d'arrêt normal
STATE_FILE = "crash-report.json"
SEND_AFTER = 30  # s après le démarrage du service : Kodi a fini de démarrer


def fingerprint(size: int, mtime: float) -> str:
    """Identité d'un journal : il change à chaque démarrage de Kodi."""
    return f"{int(size)}:{int(mtime)}"


def ended_cleanly(end_text: str) -> bool:
    return CLEAN_EXIT in end_text


def read_tail(path: str, max_bytes: int = MAX_BYTES) -> str:
    """Fin du fichier (texte, octets illisibles remplacés), à partir d'un début de ligne."""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        data = handle.read()
    text = data.decode("utf-8", errors="replace")
    if size > max_bytes and "\n" in text:
        text = text.split("\n", 1)[1]  # première ligne coupée en deux : on l'enlève
    return text


def should_send(tail: str, current: str, last_sent: str) -> bool:
    """Vrai si ce journal finit sans arrêt normal et n'a pas déjà été envoyé."""
    if not tail.strip() or current == last_sent:
        return False
    return not ended_cleanly(tail[-END_BYTES:])


def payload(tail: str, size: int, kodi_version: str, addon_version: str) -> Dict[str, Any]:
    return {
        "log": tail,
        "size": int(size),
        "source": LOG_NAME,
        "kodi_version": kodi_version,
        "addon_version": addon_version,
    }


def load_state(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def save_state(path: str, state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    os.replace(tmp, path)

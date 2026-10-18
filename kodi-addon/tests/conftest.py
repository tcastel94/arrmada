"""Tests de l'add-on Kodi, exécutés SANS Kodi (CI GitHub, poste de dev).

On ne teste ici que ce qui ne dépend pas de Kodi : la logique pure
(lib/home_data.py) et la cohérence des fichiers (XML ↔ Python ↔ textures ↔
polices du skin). Le rendu, lui, se valide sur l'appareil (ADR-003 § 8).
"""

from __future__ import annotations

import sys
from pathlib import Path

ADDON_DIR = Path(__file__).resolve().parent.parent / "script.arrmada"
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"

# Même résolution des imports que dans Kodi (default.py ajoute lib/ au chemin).
sys.path.insert(0, str(ADDON_DIR / "lib"))
sys.path.insert(0, str(TOOLS_DIR))

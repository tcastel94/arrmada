#!/usr/bin/env python3
"""Construit le zip installable de l'add-on Kodi ArrMada.

Produit deux fichiers dans kodi-addon/ :
  - script.arrmada-<version>.zip : version figée (ignorée par Git, à garder
    sous la main pour revenir en arrière dans Kodi) ;
  - script.arrmada.zip           : copie « dernière version » (suivie par Git),
    celle à installer via Extensions → Installer depuis un fichier ZIP.

La version est lue dans script.arrmada/addon.xml : pour que Kodi propose la
mise à jour, il suffit d'augmenter `version="…"` dans ce fichier puis de
relancer ce script.

Usage : python3 kodi-addon/build_zip.py
"""

from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
ADDON_DIR = ROOT_DIR / "script.arrmada"


def addon_version() -> str:
    """Version déclarée dans addon.xml (source unique de vérité)."""
    return ET.parse(ADDON_DIR / "addon.xml").getroot().attrib["version"]


def package_addon() -> Path:
    if not ADDON_DIR.exists():
        sys.exit(f"Erreur : {ADDON_DIR} introuvable")

    version = addon_version()
    versioned = ROOT_DIR / f"script.arrmada-{version}.zip"
    latest = ROOT_DIR / "script.arrmada.zip"

    print(f"Empaquetage de {ADDON_DIR.name} v{version} → {versioned.name}")
    with zipfile.ZipFile(versioned, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in sorted(ADDON_DIR.rglob("*")):
            # Ni fichiers cachés (.DS_Store…) ni caches Python dans le zip.
            if file.is_file() and not file.name.startswith(".") and "__pycache__" not in file.parts:
                arcname = file.relative_to(ROOT_DIR)  # le zip contient le dossier script.arrmada/
                zipf.write(file, arcname)
                print(f"  + {arcname}")

    shutil.copyfile(versioned, latest)
    print(f"OK : {versioned.name} et {latest.name}")
    return versioned


if __name__ == "__main__":
    package_addon()

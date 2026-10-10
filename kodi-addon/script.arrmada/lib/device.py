# -*- coding: utf-8 -*-
"""Identité de CETTE TV une fois appairée (ADR-003 § 4).

Le jeton reçu à l'appairage est gardé dans le dossier de données de
l'add-on (`special://profile/addon_data/script.arrmada/device.json`), pas
dans les réglages : il n'apparaît dans aucun écran et n'est pas exporté
avec les réglages. Il est lié à l'adresse du serveur : si on change de
serveur, l'appareil redevient « non appairé ».
"""

from __future__ import annotations

import json
import os

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon("script.arrmada")
_FILE = "device.json"


def _path() -> str:
    return os.path.join(xbmcvfs.translatePath(ADDON.getAddonInfo("profile")), _FILE)


def load() -> dict:
    """Infos de l'appareil ({} si non appairé ou fichier illisible)."""
    try:
        with open(_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(server_url: str, token: str, device: dict) -> None:
    """Enregistre le jeton et la description de l'appareil (écriture atomique)."""
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {
        "server": server_url,
        "token": token,
        "id": device.get("id"),
        "name": device.get("name") or "",
        "room": device.get("room") or "",
        "avr_name": device.get("avr_name") or "",
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)  # jamais de fichier à moitié écrit


def update(device: dict) -> None:
    """Met à jour nom / pièce / ampli (changés dans la web app), garde le jeton."""
    data = load()
    if not data.get("token"):
        return
    save(data["server"], data["token"], {**data, **device})


def clear() -> None:
    """Oublie l'appairage (jeton révoqué ou refusé par le serveur)."""
    try:
        os.remove(_path())
    except OSError:
        pass


def token_for(server_url: str) -> str:
    """Jeton à utiliser avec ce serveur ("" si non appairé avec lui)."""
    data = load()
    return data.get("token", "") if data.get("server") == server_url else ""


def room() -> str:
    """Pièce choisie à l'appairage ("" si non appairé)."""
    value = (load().get("room") or "").lower()
    return value if value in ("salon", "cinema") else ""

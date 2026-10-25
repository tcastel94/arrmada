"""Optional hardware modules: show only what the household actually has.

Everyone has Sonarr/Radarr; not everyone has a TV running the ArrMada app, a
wall tablet, a Yamaha amplifier or Eufy cameras. Each module below hides its
navigation entries, settings sections and background polling when disabled.

State per module:
  - ``explicit``: the choice made in the setup wizard or Settings › Équipement
    (stored in ``DATA_DIR/modules.json``), or None when never chosen;
  - ``detected``: what the existing configuration shows (a paired TV, an amp
    registered…), so an instance configured before this setting existed
    keeps everything it already uses;
  - ``enabled`` = explicit choice if any, else detected.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.device import Device
from app.models.service import Service
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Order = display order in the wizard and in Settings.
MODULES: dict[str, dict[str, str]] = {
    "tv": {
        "label": "Application TV",
        "description": "L'appli ArrMada sur une TV Android, une Shield ou une box Kodi : "
        "accueil, reprise de lecture, demandes depuis le canapé.",
    },
    "tablet": {
        "label": "Tablette d'appoint",
        "description": "Une tablette posée près de la TV qui affiche ce qui passe, "
        "l'heure de fin et les sorties du soir.",
    },
    "amplifier": {
        "label": "Ampli home cinéma",
        "description": "Un ampli Yamaha MusicCast réglé automatiquement selon le film "
        "(profils audio par pièce).",
    },
    "cameras": {
        "label": "Caméras Eufy",
        "description": "Une alerte sur la TV quand une caméra Eufy détecte quelqu'un "
        "pendant un film.",
    },
}


def _store() -> Path:
    return Path(settings.DATA_DIR) / "modules.json"


def load_choices() -> dict[str, bool]:
    """Explicit choices only (missing module = never chosen)."""
    try:
        data = json.loads(_store().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: bool(v) for k, v in data.items() if k in MODULES and isinstance(v, bool)}


def save_choices(choices: dict[str, bool]) -> dict[str, bool]:
    """Merge and persist explicit choices (atomic write)."""
    merged = {**load_choices(), **{k: bool(v) for k, v in choices.items() if k in MODULES}}
    path = _store()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    logger.info("Modules choisis : %s", merged)
    return merged


async def detect(db: AsyncSession) -> dict[str, bool]:
    """What the current configuration already uses."""

    async def count(stmt) -> int:
        return int((await db.execute(stmt)).scalar() or 0)

    tvs = await count(select(func.count()).select_from(Device).where(Device.kind == "tv"))
    kodis = await count(select(func.count()).select_from(Service).where(Service.type == "kodi"))
    screens = await count(select(func.count()).select_from(Device).where(Device.kind == "screen"))
    amps = await count(select(func.count()).select_from(Service).where(Service.type == "yamaha"))
    return {
        "tv": tvs + kodis > 0,
        "tablet": screens > 0,
        "amplifier": amps > 0,
        "cameras": bool(settings.EUFY_WS_URL),
    }


async def get_modules(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Effective state of every module, with label and description."""
    choices = load_choices()
    detected = await detect(db)
    result: dict[str, dict[str, Any]] = {}
    for key, meta in MODULES.items():
        explicit = choices.get(key)
        result[key] = {
            **meta,
            "enabled": explicit if explicit is not None else detected[key],
            "explicit": explicit,
            "detected": detected[key],
        }
    return result

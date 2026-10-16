"""Journaux de plantage envoyés par les TV (appli Kodi 1.21.1+).

Pourquoi : certains plantages n'arrivent que sur la Shield (Kodi 21 Android),
jamais sur le banc de test (Kodi 20 sous Linux). Le seul témoin est alors le
journal de Kodi de la session qui s'est arrêtée (`kodi.old.log`). Au
démarrage suivant, l'appli voit que ce journal ne finit pas par la ligne
d'arrêt normal de Kodi et en envoie la fin ici. C'est l'équivalent d'un
`journalctl -b -1` qu'on irait lire après un reboot inattendu.

Rangement : `data/kodi-crashes/<date>-<appareil>.log`, monté sur l'hôte
(`/mnt/user/appdata/arrmada/data/kodi-crashes/` sur l'Unraid). Les
KEEP_REPORTS plus récents sont gardés, les plus vieux effacés.

Le texte vient de la TV : il est traité comme une donnée brute (taille
bornée, nom de fichier fabriqué ici, jamais à partir de ce qu'envoie la TV).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CRASH_DIR = Path("data") / "kodi-crashes"
KEEP_REPORTS = 10  # rapports gardés (tous appareils confondus)
MAX_LOG_CHARS = 600_000  # ~ les 10 dernières minutes d'un journal en mode debug
_NAME_RE = re.compile(r"^\d{8}-\d{6}-[a-z0-9-]{1,40}\.log$")


def _slug(text: str) -> str:
    """« Shield Salon » → « shield-salon » (nom de fichier sûr)."""
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:40] or "tv"


def _clean(value: Any, limit: int = 120) -> str:
    """Champ court d'en-tête : une seule ligne, longueur bornée."""
    return re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()[:limit]


def save_report(device_name: str, data: dict, now: datetime | None = None) -> dict:
    """Écrit le rapport, garde les KEEP_REPORTS plus récents, rend {name, size}."""
    now = now or datetime.now(UTC)
    log = str(data.get("log") or "")
    if len(log) > MAX_LOG_CHARS:
        log = log[-MAX_LOG_CHARS:]  # la fin compte : c'est là que Kodi s'est arrêté
    name = f"{now:%Y%m%d-%H%M%S}-{_slug(device_name)}.log"
    header = "\n".join(
        (
            f"# Journal de plantage Kodi reçu le {now:%Y-%m-%d %H:%M:%S} UTC",
            f"# Appareil : {_clean(device_name) or '?'}",
            f"# Kodi : {_clean(data.get('kodi_version')) or '?'}",
            f"# Appli ArrMada : {_clean(data.get('addon_version')) or '?'}",
            f"# Journal : {_clean(data.get('source')) or 'kodi.old.log'}"
            f" ({_clean(data.get('size'))} octets, fin seulement)",
            "",
        )
    )
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    path = CRASH_DIR / name
    path.write_text(header + "\n" + log, encoding="utf-8")
    for old in list_reports()[KEEP_REPORTS:]:
        (CRASH_DIR / old["name"]).unlink(missing_ok=True)
    return {"name": name, "size": path.stat().st_size}


def list_reports() -> list[dict]:
    """Rapports présents, du plus récent au plus ancien."""
    if not CRASH_DIR.is_dir():
        return []
    files = [f for f in CRASH_DIR.iterdir() if f.is_file() and _NAME_RE.match(f.name)]
    files.sort(key=lambda f: f.name, reverse=True)  # le nom commence par la date
    return [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "received_at": datetime.fromtimestamp(f.stat().st_mtime, UTC).isoformat(),
        }
        for f in files
    ]


def read_report(name: str) -> str | None:
    """Texte d'un rapport, ou None (nom inconnu ou mal formé : pas de « ../ »)."""
    if not _NAME_RE.match(name or ""):
        return None
    path = CRASH_DIR / name
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None

"""Read API keys, ports and credentials from the apps' own config files.

The user mounts the folder holding the containers' config directories
(``/mnt/user/appdata`` on Unraid, ``/volume1/docker`` on Synology,
``/opt/docker``…) read-only at ``settings.APPDATA_DIR``. We walk it and
recognise each app by its config file:

  Sonarr/Radarr/Lidarr/Readarr/Prowlarr  config.xml   <ApiKey>, <Port>, <UrlBase>
  Bazarr                                 config.yaml  auth.apikey, general.port
                                         (config.ini on Bazarr < 1.3)
  SABnzbd                                sabnzbd.ini  [misc] api_key, port, url_base
  Deluge                                 web.conf     port, salted SHA-1 of the web password
  qBittorrent                            qBittorrent.conf  WebUI\\Port, PBKDF2 hash
  Jellyfin                               jellyfin.db  ApiKeys table, network.xml port

Passwords are only ever stored hashed by Deluge / qBittorrent: we cannot
read them, only CHECK a candidate (their well-known defaults, or what the
user types in the UI).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Folder depth explored under the appdata root (appdata/sonarr/config.xml = 2;
# Jellyfin's data/data/jellyfin.db sits deeper).
MAX_DEPTH = 5
# Never descend into these (huge, and never hold app configs).
SKIP_DIRS = {
    "MediaCover",
    "Backups",
    "backups",
    "logs",
    "Logs",
    "cache",
    "Cache",
    "metadata",
    "transcodes",
    "Sentry",
    "UpdateLogs",
    "asp",
    "plugins",
    "incomplete",
    "downloads",
    "Downloads",
    "admin",
    "temp",
    "tmp",
}

ARR_TYPES = ("sonarr", "radarr", "lidarr", "readarr", "prowlarr", "whisparr")
ARR_DEFAULT_PORTS = {
    7878: "radarr",
    8989: "sonarr",
    8686: "lidarr",
    8787: "readarr",
    9696: "prowlarr",
}

DELUGE_DEFAULT_PASSWORD = "deluge"
QBIT_DEFAULT_USER = "admin"
QBIT_DEFAULT_PASSWORD = "adminadmin"  # qBittorrent < 4.6.1 only


@dataclass
class FoundConfig:
    """One application found in the appdata folder."""

    type: str
    name: str
    port: int
    source: str  # path of the config file (relative to the appdata root)
    api_key: str | None = None
    url_base: str = ""
    ssl: bool = False
    # Downloaders: login name and the password when we could confirm it.
    username: str | None = None
    password: str | None = None
    # Deluge / qBittorrent: hashed password, to check user-supplied candidates.
    password_check: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def needs_password(self) -> bool:
        """Downloader whose password could not be confirmed automatically."""
        return self.type in ("deluge", "qbittorrent") and self.password is None

    def check_password(self, candidate: str) -> bool:
        """True if ``candidate`` matches the stored hash (downloaders only)."""
        return check_password(self.type, self.password_check, candidate)


# ── Password checks (no plaintext is ever stored by these apps) ──
def check_password(app_type: str, check: dict[str, str], candidate: str) -> bool:
    if app_type == "deluge" and check.get("salt") and check.get("sha1"):
        digest = hashlib.sha1((check["salt"] + candidate).encode()).hexdigest()
        return hmac.compare_digest(digest, check["sha1"])
    if app_type == "qbittorrent" and check.get("pbkdf2"):
        try:
            salt_b64, key_b64 = check["pbkdf2"].split(":", 1)
            salt, key = base64.b64decode(salt_b64), base64.b64decode(key_b64)
        except ValueError:
            return False
        derived = hashlib.pbkdf2_hmac("sha512", candidate.encode(), salt, 100_000, dklen=len(key))
        return hmac.compare_digest(derived, key)
    return False


# ── Helpers ───────────────────────────────────────────────────
def _type_from_path(path: Path) -> str | None:
    """Guess the app from folder names (``appdata/radarr-4k/config.xml``)."""
    for part in reversed(path.parts[:-1]):
        low = part.lower()
        for app in ARR_TYPES:
            if app in low:
                return app
    return None


def _display_name(app_type: str, path: Path, root: Path) -> str:
    """'Radarr' or, for a second instance, 'Radarr (radarr-4k)'."""
    label = app_type.capitalize() if app_type != "sabnzbd" else "SABnzbd"
    label = {"qbittorrent": "qBittorrent"}.get(app_type, label)
    try:
        folder = path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return label
    return label if folder.lower() == app_type else f"{label} ({folder})"


def _int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _clean_base(url_base: str | None) -> str:
    url_base = (url_base or "").strip().strip("/")
    return f"/{url_base}" if url_base else ""


# ── Parsers (one per file type; each returns None if not applicable) ──
def parse_arr_config_xml(path: Path, root: Path) -> FoundConfig | None:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return None
    cfg = tree.getroot()
    if cfg.tag != "Config":
        return None
    api_key = (cfg.findtext("ApiKey") or "").strip()
    if not api_key:
        return None
    port = _int(cfg.findtext("Port"), 0)
    instance = (cfg.findtext("InstanceName") or "").strip().lower()
    app_type = next((a for a in ARR_TYPES if a in instance), None)
    app_type = app_type or _type_from_path(path) or ARR_DEFAULT_PORTS.get(port)
    if not app_type:
        return None
    ssl = (cfg.findtext("EnableSsl") or "").strip().lower() == "true"
    if ssl:
        port = _int(cfg.findtext("SslPort"), port)
    return FoundConfig(
        type=app_type,
        name=_display_name(app_type, path, root),
        port=port or next(p for p, a in ARR_DEFAULT_PORTS.items() if a == app_type),
        source=str(path.relative_to(root)),
        api_key=api_key,
        url_base=_clean_base(cfg.findtext("UrlBase")),
        ssl=ssl,
    )


def parse_bazarr_yaml(path: Path, root: Path) -> FoundConfig | None:
    if "bazarr" not in str(path).lower():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return None
    api_key = (data.get("auth") or {}).get("apikey")
    if not api_key:
        return None
    general = data.get("general") or {}
    return FoundConfig(
        type="bazarr",
        name=_display_name("bazarr", path, root),
        port=_int(general.get("port"), 6767),
        source=str(path.relative_to(root)),
        api_key=str(api_key),
        url_base=_clean_base(general.get("base_url")),
    )


def _ini_section(text: str, section: str) -> dict[str, str]:
    """Flat ``key = value`` pairs of one top-level ``[section]``.

    Tolerates SABnzbd's configobj format (nested ``[[sub]]`` sections),
    which the stdlib configparser rejects.
    """
    values: dict[str, str] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            current = line.strip("[]").strip() if not line.startswith("[[") else f"{current}/sub"
            continue
        if current == section and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    return values


def parse_bazarr_ini(path: Path, root: Path) -> FoundConfig | None:
    if "bazarr" not in str(path).lower():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    api_key = _ini_section(text, "auth").get("apikey")
    if not api_key:
        return None
    general = _ini_section(text, "general")
    return FoundConfig(
        type="bazarr",
        name=_display_name("bazarr", path, root),
        port=_int(general.get("port"), 6767),
        source=str(path.relative_to(root)),
        api_key=api_key,
        url_base=_clean_base(general.get("base_url")),
    )


def parse_sabnzbd_ini(path: Path, root: Path) -> FoundConfig | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    misc = _ini_section(text, "misc")
    api_key = misc.get("api_key")
    if not api_key:
        return None
    ssl = misc.get("enable_https") == "1"
    port = _int(misc.get("https_port") if ssl else misc.get("port"), 8080)
    return FoundConfig(
        type="sabnzbd",
        name=_display_name("sabnzbd", path, root),
        port=port,
        source=str(path.relative_to(root)),
        api_key=api_key,
        url_base=_clean_base(misc.get("url_base")),
        ssl=ssl,
    )


def parse_deluge_web_conf(path: Path, root: Path) -> FoundConfig | None:
    """web.conf = two concatenated JSON objects (format header + settings)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    decoder = json.JSONDecoder()
    settings: dict = {}
    pos = 0
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        try:
            obj, pos = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            return None
        if isinstance(obj, dict):
            settings.update(obj)
    if "pwd_sha1" not in settings:
        return None
    found = FoundConfig(
        type="deluge",
        name=_display_name("deluge", path, root),
        port=_int(settings.get("port"), 8112),
        source=str(path.relative_to(root)),
        ssl=bool(settings.get("https")),
        url_base=_clean_base(settings.get("base")),
        password_check={
            "salt": str(settings.get("pwd_salt", "")),
            "sha1": str(settings["pwd_sha1"]),
        },
    )
    if found.check_password(DELUGE_DEFAULT_PASSWORD):
        found.password = DELUGE_DEFAULT_PASSWORD
        found.notes.append("Mot de passe web par défaut (« deluge ») : pense à le changer.")
    return found


def parse_deluge_core_conf(path: Path, root: Path) -> FoundConfig | None:
    """Deluge that never saved its web settings: web.conf does not exist yet.

    The web UI then runs on its defaults (port 8112, password « deluge »).
    The password is only a CANDIDATE here: the probe confirms it with a
    real login, and asks the user otherwise.
    """
    if (path.parent / "web.conf").exists() or "deluge" not in str(path).lower():
        return None
    found = FoundConfig(
        type="deluge",
        name=_display_name("deluge", path, root),
        port=8112,
        source=str(path.relative_to(root)),
        password=DELUGE_DEFAULT_PASSWORD,
    )
    found.notes.append("Réglages web jamais modifiés : mot de passe par défaut « deluge » supposé.")
    return found


def parse_qbittorrent_conf(path: Path, root: Path) -> FoundConfig | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    prefs = _ini_section(text, "Preferences")
    port = _int(prefs.get("WebUI\\Port"), 8080)
    username = prefs.get("WebUI\\Username") or QBIT_DEFAULT_USER
    raw_hash = prefs.get("WebUI\\Password_PBKDF2", "")
    match = re.match(r"@ByteArray\((.+)\)", raw_hash)
    found = FoundConfig(
        type="qbittorrent",
        name=_display_name("qbittorrent", path, root),
        port=port,
        source=str(path.relative_to(root)),
        username=username,
        ssl=prefs.get("WebUI\\HTTPS\\Enabled") == "true",
        password_check={"pbkdf2": match.group(1)} if match else {},
    )
    if found.check_password(QBIT_DEFAULT_PASSWORD):
        found.password = QBIT_DEFAULT_PASSWORD
        found.notes.append("Identifiants par défaut (admin / adminadmin) : pense à les changer.")
    elif not match:
        found.notes.append(
            "Aucun mot de passe enregistré : qBittorrent ≥ 4.6.1 en affiche un temporaire "
            "dans ses logs au démarrage."
        )
    return found


def parse_jellyfin_db(path: Path, root: Path) -> FoundConfig | None:
    """Read the first API key from jellyfin.db (Jellyfin ≥ 10.9)."""
    # immutable=1: the mount is read-only, SQLite must not try to write WAL files.
    uri = f"file:{path}?mode=ro&immutable=1"
    try:
        with sqlite3.connect(uri, uri=True, timeout=2) as conn:
            row = conn.execute(
                "SELECT AccessToken FROM ApiKeys ORDER BY DateCreated LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None
    port = 8096
    # network.xml lives in the config dir: same folder or a few levels up.
    for parent in [path.parent, *path.parents][:4]:
        network = parent / "network.xml"
        if network.is_file():
            try:
                port = _int(ET.parse(network).getroot().findtext("InternalHttpPort"), 8096)
            except (ET.ParseError, OSError):
                pass
            break
    found = FoundConfig(
        type="jellyfin",
        name=_display_name("jellyfin", path, root),
        port=port,
        source=str(path.relative_to(root)),
        api_key=row[0] if row else None,
    )
    if not row:
        found.notes.append(
            "Aucune clé API : crée-en une dans Jellyfin → Tableau de bord → Clés API."
        )
    return found


PARSERS = {
    "config.xml": parse_arr_config_xml,
    "config.yaml": parse_bazarr_yaml,
    "config.ini": parse_bazarr_ini,
    "sabnzbd.ini": parse_sabnzbd_ini,
    "web.conf": parse_deluge_web_conf,
    "core.conf": parse_deluge_core_conf,
    "qBittorrent.conf": parse_qbittorrent_conf,
    "jellyfin.db": parse_jellyfin_db,
}


def scan_appdata(root: str | Path) -> list[FoundConfig]:
    """Walk the appdata folder and return every recognised app config."""
    root = Path(root)
    if not root.is_dir():
        return []
    found: list[FoundConfig] = []
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        depth = len(Path(dirpath).parts) - root_depth
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        for filename in filenames:
            parser = PARSERS.get(filename)
            if not parser:
                continue
            try:
                result = parser(Path(dirpath) / filename, root)
            except Exception:  # noqa: BLE001 — one odd file must not stop the scan
                logger.exception("Could not parse %s", Path(dirpath) / filename)
                continue
            if result:
                found.append(result)

    # Bazarr ≥ 1.3 keeps a stale config.ini next to config.yaml: keep one per folder.
    unique: dict[tuple[str, str], FoundConfig] = {}
    for item in found:
        key = (item.type, str(Path(item.source).parts[0]))
        if key not in unique or item.source.endswith((".yaml", ".xml", ".db")):
            unique[key] = item
    result = sorted(unique.values(), key=lambda c: (c.type, c.name))
    logger.info("Appdata scan of %s: %d app config(s) found", root, len(result))
    return result

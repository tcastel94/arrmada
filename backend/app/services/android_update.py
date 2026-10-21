"""Mises à jour de l'appli Android (ADR-009).

Circuit, comme un miroir de paquets :

1. la CI compile l'APK signée (clé release) et la publie dans la release
   GitHub ``android-latest`` du dépôt, avec son empreinte SHA-256 ;
2. ce module la rapatrie toutes les heures dans ``data/apk`` et vérifie
   l'empreinte avant de la garder (fichier ``.part`` renommé à la fin : une
   APK coupée n'est jamais proposée) ;
3. les TV et téléphones demandent ``/api/android/update`` au lancement et
   téléchargent l'APK depuis le serveur, sur le réseau local.

Une APK compilée à la main (``./build-apk.sh``) peut aussi être déposée dans
``data/apk`` : son nom dit sa version (``arrmada-2.7.0-152-release.apk``).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Nom produit par build-apk.sh : arrmada-<version affichée>-<n° interne>-<type>.apk
APK_NAME = re.compile(
    r"^arrmada-(?P<name>[A-Za-z0-9.+_-]+)-(?P<code>\d+)-(?P<type>release|debug)\.apk$"
)

# APK gardées par type (la plus récente + la précédente, pour revenir en arrière à la main)
KEEP = 2

_GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class Apk:
    """Une APK disponible sur le serveur."""

    path: Path
    version_name: str
    version_code: int
    build_type: str  # « release » ou « debug »

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    def as_dict(self) -> dict:
        return {
            "file": self.path.name,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "build_type": self.build_type,
            "size": self.size,
            "sha256": sha256_of(self.path),
            "url": f"/api/android/apk/{self.path.name}",
        }


# Dernière vérification GitHub (affichée dans la web app)
_status: dict = {"checked_at": None, "error": None, "message": None}
_lock = asyncio.Lock()
_hashes: dict[tuple[str, float], str] = {}  # (fichier, date de modif) → empreinte


def apk_dir() -> Path:
    return Path(settings.ANDROID_APK_DIR)


def parse_name(name: str) -> tuple[str, int, str] | None:
    """« arrmada-2.7.0-152-release.apk » → ("2.7.0", 152, "release") ; None si autre chose."""
    match = APK_NAME.fullmatch(name)
    if match is None:
        return None
    return match["name"], int(match["code"]), match["type"]


def sha256_of(path: Path) -> str:
    """Empreinte du fichier, calculée une fois par version du fichier."""
    key = (str(path), path.stat().st_mtime)
    if key not in _hashes:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def local_apks(directory: Path | None = None) -> list[Apk]:
    """APK présentes sur le serveur, la plus récente d'abord."""
    directory = directory or apk_dir()
    if not directory.is_dir():
        return []
    found = []
    for path in directory.glob("arrmada-*.apk"):
        parsed = parse_name(path.name)
        if parsed and path.is_file():
            found.append(Apk(path, *parsed))
    return sorted(found, key=lambda apk: apk.version_code, reverse=True)


def latest(build_type: str = "release", directory: Path | None = None) -> Apk | None:
    """APK la plus récente de ce type (une APK de test ne met pas à jour une appli release)."""
    return next((apk for apk in local_apks(directory) if apk.build_type == build_type), None)


def find(name: str, directory: Path | None = None) -> Apk | None:
    """APK demandée par son nom exact (jamais un autre fichier du dossier)."""
    return next((apk for apk in local_apks(directory) if apk.path.name == name), None)


def prune(directory: Path | None = None) -> None:
    """Garde les KEEP plus récentes de chaque type, supprime les autres et les restes de téléchargement."""
    directory = directory or apk_dir()
    by_type: dict[str, int] = {}
    for apk in local_apks(directory):
        by_type[apk.build_type] = by_type.get(apk.build_type, 0) + 1
        if by_type[apk.build_type] > KEEP:
            apk.path.unlink(missing_ok=True)
            Path(f"{apk.path}.sha256").unlink(missing_ok=True)
    for leftover in directory.glob("*.part"):
        leftover.unlink(missing_ok=True)


def status() -> dict:
    return dict(_status)


async def refresh(client: httpx.AsyncClient | None = None, directory: Path | None = None) -> str:
    """Rapatrie l'APK de la release GitHub si elle est plus récente. Renvoie un message d'état."""
    repo = settings.ANDROID_UPDATE_REPO.strip()
    if not repo:
        return "Dépôt GitHub non configuré : APK déposées à la main seulement"
    directory = directory or apk_dir()
    async with _lock:
        own = client is None
        client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True
        )
        try:
            message = await _refresh(client, repo, directory)
            _status.update(checked_at=datetime.now(UTC).isoformat(), error=None, message=message)
            return message
        except (httpx.HTTPError, OSError, ValueError) as exc:
            _status.update(
                checked_at=datetime.now(UTC).isoformat(), error=str(exc) or type(exc).__name__
            )
            logger.warning("Mise à jour Android : vérification GitHub en échec (%s)", exc)
            raise
        finally:
            if own:
                await client.aclose()


async def _refresh(client: httpx.AsyncClient, repo: str, directory: Path) -> str:
    url = f"{_GITHUB_API}/repos/{repo}/releases/tags/{settings.ANDROID_UPDATE_TAG}"
    response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    if response.status_code == 404:
        return "Aucune APK publiée par la CI (release absente : clé de signature à configurer ?)"
    response.raise_for_status()
    assets = {asset["name"]: asset for asset in response.json().get("assets", [])}

    # Meilleure APK release de la release GitHub
    candidates = sorted(
        ((parse_name(name), asset) for name, asset in assets.items()),
        key=lambda item: item[0][1] if item[0] else -1,
        reverse=True,
    )
    best = next(
        ((parsed, asset) for parsed, asset in candidates if parsed and parsed[2] == "release"), None
    )
    if best is None:
        return "La release GitHub ne contient pas d'APK release"
    (version_name, version_code, _), asset = best
    target = directory / asset["name"]
    current = latest("release", directory)
    if target.exists() or (current and current.version_code >= version_code):
        return f"À jour : {current.version_name if current else version_name}"

    # Empreinte publiée par la CI (« <sha256>  <fichier> »), obligatoire
    checksum = assets.get(f"{asset['name']}.sha256")
    if checksum is None:
        raise ValueError(f"Empreinte SHA-256 absente pour {asset['name']}")
    expected_response = await client.get(checksum["browser_download_url"])
    expected_response.raise_for_status()
    expected = expected_response.text.split()[0].lower()

    directory.mkdir(parents=True, exist_ok=True)
    partial = directory / f"{asset['name']}.part"
    digest = hashlib.sha256()
    async with client.stream("GET", asset["browser_download_url"]) as download:
        download.raise_for_status()
        with partial.open("wb") as out:
            async for chunk in download.aiter_bytes(1 << 20):
                digest.update(chunk)
                out.write(chunk)
    if digest.hexdigest() != expected:
        partial.unlink(missing_ok=True)
        raise ValueError(f"Empreinte SHA-256 différente pour {asset['name']} : APK refusée")
    partial.rename(target)
    Path(f"{target}.sha256").write_text(f"{expected}  {target.name}\n")
    prune(directory)
    logger.info(
        "Mise à jour Android : %s (%d) disponible pour les appareils", version_name, version_code
    )
    return f"Nouvelle version rapatriée : {version_name}"

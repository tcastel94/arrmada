"""Dépôt Kodi servi par ArrMada (ADR-003 § 5) : mises à jour automatiques.

Un « dépôt » Kodi, c'est simplement trois choses servies en HTTP :
  - `addons.xml`     la liste des add-ons et de leur version ;
  - `addons.xml.md5` son empreinte (Kodi ne relit la liste que si elle change) ;
  - les zips, rangés `<id>/<id>-<version>.zip`.
On installe une fois `repository.arrmada` sur la TV ; ensuite Kodi compare
régulièrement les versions et met l'appli à jour tout seul (comme `apt` avec
un dépôt ajouté dans sources.list).

Les zips sont fabriqués à la volée depuis le dossier `kodi-addon/` du dépôt
Git (monté dans le conteneur, voir docker-compose.yml) : après un `git pull`,
la nouvelle version est proposée aux TV sans reconstruire l'image Docker.
L'adresse du serveur est écrite dans le zip du dépôt au moment où la TV le
télécharge (celle par laquelle elle joint ArrMada).

Depuis le dépôt 1.1.0, chaque zip a son empreinte SHA-256 (`<zip>.sha256`,
déclarée par `<hashes>sha256</hashes>`). Comme un `sha256sum -c` avant un
`dpkg -i` : Kodi vérifie le zip téléchargé, et surtout il le retélécharge à
chaque installation. Sans empreinte, Kodi réutilise tel quel un zip déjà
présent dans son dossier `packages/` sous le même nom, même s'il a été
coupé par un plantage pendant le téléchargement.
"""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from app.config import settings

ADDON_ID = "script.arrmada"
REPO_ID = "repository.arrmada"
# 1.1.0 : empreintes SHA-256 des zips. Les TV qui ont le dépôt 1.0.0 le mettent
# à jour toutes seules (il est listé dans addons.xml).
REPO_VERSION = "1.1.0"

# Fichiers jamais mis dans un zip : caches Python, fichiers cachés (.DS_Store…)
_SKIP_PARTS = {"__pycache__"}


def addon_root() -> Path | None:
    """Dossier `kodi-addon/` (celui qui contient `script.arrmada/addon.xml`)."""
    candidates = [settings.KODI_ADDON_DIR] if settings.KODI_ADDON_DIR else []
    candidates += [
        "/app/kodi-addon",  # monté par docker-compose.yml
        str(Path(__file__).resolve().parents[3] / "kodi-addon"),  # poste de dev
    ]
    for candidate in candidates:
        root = Path(candidate)
        if (root / ADDON_ID / "addon.xml").is_file():
            return root
    return None


def addon_version(root: Path) -> str:
    return ET.parse(root / ADDON_ID / "addon.xml").getroot().attrib["version"]


def addon_assets(root: Path) -> set[str]:
    """Images déclarées dans addon.xml (icône, fanart) : seules servies à part."""
    tree = ET.parse(root / ADDON_ID / "addon.xml").getroot()
    return {el.text.strip() for el in tree.iterfind(".//assets/*") if el.text and el.text.strip()}


def _strip_declaration(xml: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", xml).strip()


def repository_addon_xml(base_url: str) -> str:
    """addon.xml du dépôt, pointant vers CE serveur."""
    repo = f"{base_url.rstrip('/')}/kodi/repo"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{REPO_ID}" name="Dépôt ArrMada" version="{REPO_VERSION}" provider-name="ArrMada">
    <extension point="xbmc.addon.repository" name="Dépôt ArrMada">
        <dir>
            <info compressed="false">{repo}/addons.xml</info>
            <checksum>{repo}/addons.xml.md5</checksum>
            <datadir zip="true">{repo}/</datadir>
            <hashes>sha256</hashes>
        </dir>
    </extension>
    <extension point="xbmc.addon.metadata">
        <summary lang="fr_FR">Mises à jour automatiques de l'appli ArrMada</summary>
        <summary lang="en_GB">Automatic updates for the ArrMada app</summary>
        <description lang="fr_FR">Dépôt servi par ton serveur ArrMada ({base_url}). Kodi y trouve les nouvelles versions de l'appli et les installe tout seul.</description>
        <platform>all</platform>
        <assets>
            <icon>icon.png</icon>
        </assets>
    </extension>
</addon>
"""


def addons_xml(root: Path, base_url: str) -> str:
    """Liste des add-ons du dépôt : l'appli + le dépôt lui-même."""
    script = _strip_declaration((root / ADDON_ID / "addon.xml").read_text(encoding="utf-8"))
    repo = _strip_declaration(repository_addon_xml(base_url))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f"<addons>\n{script}\n{repo}\n</addons>\n"
    )


def md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()  # noqa: S324 — format imposé par Kodi


def sha256(data: bytes) -> str:
    """Empreinte d'un zip, au format lu par Kodi dans `<zip>.sha256` (hexadécimal)."""
    return hashlib.sha256(data).hexdigest()


_ZIP_CACHE: dict[tuple[str, float], bytes] = {}


def _files(folder: Path) -> list[Path]:
    return sorted(
        f
        for f in folder.rglob("*")
        if f.is_file() and not f.name.startswith(".") and not _SKIP_PARTS & set(f.parts)
    )


def addon_zip(root: Path) -> bytes:
    """Zip de l'appli (dossier `script.arrmada/` à la racine du zip).

    Gardé en mémoire tant que ni la version ni aucun fichier ne change.
    """
    folder = root / ADDON_ID
    files = _files(folder)
    key = (addon_version(root), max((f.stat().st_mtime for f in files), default=0.0))
    if key not in _ZIP_CACHE:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, file.relative_to(root).as_posix())
        _ZIP_CACHE.clear()  # une seule version gardée
        _ZIP_CACHE[key] = buffer.getvalue()
    return _ZIP_CACHE[key]


# Date fixe dans le zip du dépôt : deux téléchargements donnent les mêmes octets,
# donc la même empreinte (sinon l'heure du zip changerait à chaque appel et
# Kodi verrait une empreinte différente de celle annoncée juste avant).
_FIXED_DATE = (2024, 1, 1, 0, 0, 0)


def repository_zip(root: Path, base_url: str) -> bytes:
    """Zip du dépôt, avec l'adresse de CE serveur écrite dedans."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        entries = [(f"{REPO_ID}/addon.xml", repository_addon_xml(base_url).encode("utf-8"))]
        icon = root / ADDON_ID / "resources" / "icon.png"
        if icon.is_file():
            entries.append((f"{REPO_ID}/icon.png", icon.read_bytes()))
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=_FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()

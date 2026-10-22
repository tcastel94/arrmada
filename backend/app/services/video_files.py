"""Écran « Vidéos » : explorateur des dossiers vidéo hors médiathèque.

Les vidéos sans fiche officielle (mangas « Kai », montages, vidéos perso)
échappent à Radarr / Sonarr / Jellyfin. Les dossiers déclarés dans la web app
(table ``video_roots``) se parcourent ici comme un explorateur de fichiers :
dossiers, vidéos, sous-titres posés à côté.

Sécurité (les TV n'ont qu'un jeton d'appareil) :

- un élément est désigné par un **jeton** opaque (« n° du dossier racine /
  chemin relatif », en base64 d'URL), jamais par un chemin brut ;
- chaque jeton est résolu en chemin réel (liens symboliques suivis) puis
  **confiné** à son dossier racine, comme un chroot : « ../ » ou un lien qui
  sort du dossier donnent « introuvable » ;
- seuls les dossiers, les vidéos et les sous-titres sont listés ou servis.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.tv_playback import DIRECT_EXTENSIONS

# Ce que le lecteur de l'appli (ExoPlayer) ouvre directement
VIDEO_EXTENSIONS = DIRECT_EXTENSIONS | {"mpg", "mpeg", "flv", "3gp"}

VIDEO_MIME = {
    "mkv": "video/x-matroska",
    "mk3d": "video/x-matroska",
    "webm": "video/webm",
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "mov": "video/quicktime",
    "ts": "video/mp2t",
    "avi": "video/x-msvideo",
    "ogv": "video/ogg",
    "mpg": "video/mpeg",
    "mpeg": "video/mpeg",
    "flv": "video/x-flv",
    "3gp": "video/3gpp",
}

# Sous-titres posés à côté d'une vidéo (« Ep01.srt », « Ep01.fr.ass »)
SUBTITLE_MIME = {
    "srt": "application/x-subrip",
    "ass": "text/x-ssa",
    "ssa": "text/x-ssa",
    "vtt": "text/vtt",
}
MAX_SUBTITLE_BYTES = 5 * 1024 * 1024

# Images posées dans les dossiers (affiches, fonds, vignettes : séries maison)
IMAGE_MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

# Dossiers techniques de NAS / Windows, jamais affichés
_HIDDEN_DIRS = {"$recycle.bin", "system volume information", "#recycle", "lost+found", "@eadir"}

_LANGUAGES = {
    "fr": "Français",
    "fre": "Français",
    "fra": "Français",
    "vf": "Français",
    "vff": "Français",
    "vostfr": "Français",
    "en": "Anglais",
    "eng": "Anglais",
    "ja": "Japonais",
    "jpn": "Japonais",
    "es": "Espagnol",
    "spa": "Espagnol",
    "de": "Allemand",
    "ger": "Allemand",
    "it": "Italien",
    "ita": "Italien",
}

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,2000}$")


class NotFound(Exception):
    """Jeton invalide, chemin hors du dossier racine, ou élément absent."""


@dataclass(frozen=True)
class Root:
    id: int
    name: str
    path: str


# ─── Jetons ──────────────────────────────────────────────────────────────────


def encode_token(root_id: int, relative: str = "") -> str:
    """(dossier racine, chemin relatif) → jeton d'URL (base64 sans « = »)."""
    raw = f"{root_id}/{relative}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_token(token: str) -> tuple[int, str]:
    if not _TOKEN.fullmatch(token or ""):
        raise NotFound("Jeton invalide")
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise NotFound("Jeton invalide") from exc
    root_id, _, relative = raw.partition("/")
    if not root_id.isdigit():
        raise NotFound("Jeton invalide")
    return int(root_id), relative


def resolve(roots: dict[int, Root], token: str) -> tuple[Root, Path, str]:
    """Jeton → (racine, chemin réel, chemin relatif propre), confiné à la racine."""
    root_id, relative = decode_token(token)
    root = roots.get(root_id)
    if root is None:
        raise NotFound("Dossier inconnu")
    base = os.path.realpath(root.path)
    real = os.path.realpath(os.path.join(base, relative))
    if real != base and not real.startswith(base + os.sep):
        raise NotFound("Hors du dossier")  # « ../ » ou lien symbolique qui sort
    if not os.path.exists(real):
        raise NotFound("Introuvable")
    clean = "" if real == base else os.path.relpath(real, base)
    return root, Path(real), clean


# ─── Règles de nommage ───────────────────────────────────────────────────────


def natural_key(name: str) -> list[Any]:
    """Tri « humain » : Episode 2 avant Episode 10 (comme un explorateur)."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name.lower())]


def _hidden(name: str) -> bool:
    return name.startswith((".", "@")) or name.lower() in _HIDDEN_DIRS


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def watch_id(real: Path) -> str:
    """Identifiant de vu / reprise d'une vidéo : empreinte SHA-1 de son chemin réel."""
    return hashlib.sha1(str(real).encode()).hexdigest()  # noqa: S324 (identifiant, pas sécurité)


def subtitle_label(video_stem: str, sub_name: str) -> tuple[str, str]:
    """« Ep01.forced.fr.srt » à côté de « Ep01.mkv » → ("Français (forcés)", "fr")."""
    stem = sub_name.rsplit(".", 1)[0]
    rest = stem[len(video_stem) :].strip(".").lower()
    parts = [p for p in rest.split(".") if p]
    language = next((p for p in parts if p in _LANGUAGES), "")
    label = _LANGUAGES.get(language, "") or (rest or "Externe")
    flags = [p for p in parts if p in ("forced", "sdh", "cc")]
    if "forced" in flags:
        label += " (forcés)"
    elif flags:
        label += " (malentendants)"
    iso = {"fre": "fr", "fra": "fr", "vf": "fr", "vff": "fr", "vostfr": "fr", "eng": "en"}.get(
        language, language
    )
    return label, iso[:2] if language in _LANGUAGES else ""


def _sidecars(video: str, names: list[str]) -> list[str]:
    """Sous-titres du même dossier qui accompagnent [video] (même début de nom)."""
    stem = video.rsplit(".", 1)[0]
    found = []
    for name in names:
        if _ext(name) not in SUBTITLE_MIME:
            continue
        sub_stem = name.rsplit(".", 1)[0]
        if sub_stem == stem or sub_stem.startswith(stem + "."):
            found.append(name)
    return sorted(found, key=natural_key)


# ─── Explorateur ─────────────────────────────────────────────────────────────


def roots_listing(roots: list[Root]) -> dict[str, Any]:
    """Premier niveau de l'écran Vidéos : les dossiers déclarés dans la web app."""
    return {
        "title": "Vidéos",
        "crumbs": [],
        "parent": None,
        "folders": [
            {
                "name": r.name,
                "token": encode_token(r.id),
                "available": os.path.isdir(r.path),
            }
            for r in roots
        ],
        "files": [],
    }


def listing(root: Root, real: Path, relative: str) -> dict[str, Any]:
    """Contenu d'un dossier : sous-dossiers puis vidéos, en tri naturel."""
    if not real.is_dir():
        raise NotFound("Pas un dossier")
    try:
        entries = [e for e in os.scandir(real) if not _hidden(e.name)]
    except OSError as exc:
        raise NotFound(f"Dossier illisible : {exc.strerror}") from exc
    names = [e.name for e in entries]
    folders, files = [], []
    for entry in sorted(entries, key=lambda e: natural_key(e.name)):
        child = f"{relative}/{entry.name}" if relative else entry.name
        try:
            if entry.is_dir():
                folders.append({"name": entry.name, "token": encode_token(root.id, child)})
            elif entry.is_file() and _ext(entry.name) in VIDEO_EXTENSIONS:
                stat = entry.stat()
                full = Path(os.path.realpath(entry.path))
                files.append(
                    {
                        "name": entry.name,
                        "title": entry.name.rsplit(".", 1)[0],
                        "token": encode_token(root.id, child),
                        "size": stat.st_size,
                        "modified": int(stat.st_mtime),
                        "watch_id": watch_id(full),
                        "subtitles": len(_sidecars(entry.name, names)),
                    }
                )
        except OSError:
            continue  # fichier disparu entre-temps, lien cassé : ignoré

    # Fil d'Ariane : racine, puis chaque sous-dossier
    crumbs = [{"name": root.name, "token": encode_token(root.id)}]
    parts = [p for p in relative.split(os.sep) if p] if relative else []
    for index, part in enumerate(parts):
        crumbs.append({"name": part, "token": encode_token(root.id, "/".join(parts[: index + 1]))})
    parent = crumbs[-2]["token"] if len(crumbs) > 1 else None
    return {
        "title": crumbs[-1]["name"],
        "crumbs": crumbs,
        "parent": parent,
        "folders": folders,
        "files": files,
    }


def play_info(root: Root, real: Path, relative: str) -> dict[str, Any]:
    """Infos de lecture d'une vidéo, au format de /api/tv/play (le lecteur de l'appli est le même)."""
    if not real.is_file() or _ext(real.name) not in VIDEO_EXTENSIONS:
        raise NotFound("Pas une vidéo")
    folder = os.path.dirname(relative)
    names = [n for n in os.listdir(real.parent) if not _hidden(n)]
    stem = real.name.rsplit(".", 1)[0]
    subtitles = []
    for name in _sidecars(real.name, names):
        label, language = subtitle_label(stem, name)
        token = encode_token(root.id, f"{folder}/{name}" if folder else name)
        subtitles.append(
            {
                "url": f"/api/videos/subtitle/{token}",
                "label": label,
                "language": language,
                "mime": SUBTITLE_MIME[_ext(name)],
            }
        )
    token = encode_token(root.id, relative)
    return {
        "status": "ok",
        "item_id": "",
        "title": stem,
        "duration": 0,  # connue du lecteur à l'ouverture
        "mode": "direct",
        "container": _ext(real.name),
        "stream": f"/api/videos/stream/{token}",
        "remux_stream": "",
        "chapters": [],
        "segments": [],
        "watch_id": watch_id(real),
        "subtitles": subtitles,
    }


def video_mime(real: Path) -> str:
    return VIDEO_MIME.get(_ext(real.name), "application/octet-stream")


def subtitle_bytes(real: Path) -> tuple[bytes, str]:
    """Sous-titre converti en UTF-8 (beaucoup de .srt français sont en Windows-1252)."""
    if not real.is_file() or _ext(real.name) not in SUBTITLE_MIME:
        raise NotFound("Pas un sous-titre")
    if real.stat().st_size > MAX_SUBTITLE_BYTES:
        raise NotFound("Sous-titre trop gros")
    raw = real.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return text.encode("utf-8"), SUBTITLE_MIME[_ext(real.name)]


# ─── Dossiers racines (web app) ──────────────────────────────────────────────


def check_root_path(path: str) -> str:
    """Chemin proposé dans la web app → chemin réel accepté, ou ValueError en clair."""
    path = (path or "").strip()
    if not path.startswith("/"):
        raise ValueError("Chemin absolu attendu (ex. /mnt/user/medias/mangas-kai)")
    real = os.path.realpath(path)
    base = settings.VIDEO_ALLOWED_BASE.strip()
    if base:
        allowed = os.path.realpath(base)
        if real != allowed and not real.startswith(allowed + os.sep):
            raise ValueError(f"Dossier refusé : il doit être sous {base}")
    if not os.path.isdir(real):
        raise ValueError("Dossier introuvable sur le serveur (vérifie le montage du NAS)")
    return real

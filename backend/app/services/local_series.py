"""Séries maison : lecture d'un dossier de montage (« Kai ») comme une série.

Règles, comme un explorateur qui « devine » une série :

- **saisons** : les sous-dossiers qui contiennent des vidéos (un arc = une
  saison), dans l'ordre naturel ; le numéro vient du nom (« Saison 2 »,
  « Arc 03 - … », « S04 ») s'il est sans ambiguïté, sinon de l'ordre. Sans
  sous-dossier, toutes les vidéos forment la saison 1 ;
- **épisodes** : les vidéos de chaque saison ; le numéro vient du NFO, sinon
  du nom de fichier (« Naruto Kai - 015 », « Ep 12 », « E07 »), sinon de
  l'ordre ; le titre vient du NFO, sinon du nom de fichier nettoyé ;
- **métadonnées locales** (Jellyfin / Kodi / OnePacerr) : ``tvshow.nfo``,
  un ``.nfo`` par épisode, ``poster.jpg`` / ``fanart.jpg``, vignettes
  ``<épisode>-thumb.jpg``. Elles l'emportent sur les noms de fichiers.

Le vu / la reprise restent ceux des fichiers (écran Vidéos) : même empreinte
de chemin, donc une vidéo vue depuis l'écran Vidéos est vue ici aussi.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.services.video_files import (
    VIDEO_EXTENSIONS,
    Root,
    _ext,
    _hidden,
    encode_token,
    natural_key,
    watch_id,
)

MAX_NFO_BYTES = 256 * 1024

_POSTER_NAMES = ("poster", "folder", "cover", "show")
_FANART_NAMES = ("fanart", "backdrop", "background")

# Numéro de saison dans un nom de dossier : « Saison 2 », « Season 02 », « S03 », « Arc 4 - … », « 05 - … »
_SEASON_NUMBER = re.compile(
    r"^(?:(?:saison|season|arc|partie|part|s)\s*[-_.]?\s*)?0*(\d{1,3})(?=\D|$)", re.IGNORECASE
)
# Numéro d'épisode explicite : « Ep 12 », « Episode 12 », « E12 », « S01E12 », « #12 »
_EPISODE_EXPLICIT = re.compile(
    r"(?:s\d{1,3}\s*e|\b[ée]p(?:isode)?|\be|#)\s*[-_.]?\s*0*(\d{1,4})(?!\d)", re.IGNORECASE
)
# Étiquettes de release à ignorer avant de chercher un numéro nu
_TAGS = re.compile(
    r"\[[^\]]*\]|\([^)]*\)|\b(?:2160p|1080p|720p|480p|x26[45]|h\.?26[45]|hevc|10bit|8bit|aac|flac|ac3|web(?:-?dl|rip)?|bluray|bdrip|vostfr|multi|vf|vff)\b",
    re.IGNORECASE,
)
_BARE_NUMBER = re.compile(r"(?<!\d)0*(\d{1,4})(?:v\d)?(?!\d)")


@dataclass
class Episode:
    season: int
    number: int
    title: str
    overview: str | None
    token: str  # jeton de lecture (écran Vidéos)
    watch_id: str  # vu / reprise (empreinte du chemin)
    image: str | None = None  # jeton d'image (vignette locale)
    aired: str | None = None


@dataclass
class Season:
    number: int
    name: str
    episodes: list[Episode] = field(default_factory=list)


@dataclass
class Scan:
    seasons: list[Season]
    title: str | None = None  # tvshow.nfo
    overview: str | None = None
    year: int | None = None
    poster: str | None = None  # jeton d'image locale
    fanart: str | None = None


# ─── NFO (format Kodi / Jellyfin) ────────────────────────────────────────────


def read_nfo(path: Path) -> dict[str, str]:
    """Champs utiles d'un NFO (title, plot, season, episode, year, aired) ; {} si illisible.

    Les NFO sont des fichiers XML posés sur le NAS par Jellyfin, Kodi ou
    OnePacerr : taille bornée, erreurs ignorées (le nom de fichier prend le relais).
    """
    try:
        if not path.is_file() or path.stat().st_size > MAX_NFO_BYTES:
            return {}
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError, ValueError):
        return {}
    out = {}
    for tag in ("title", "plot", "season", "episode", "year", "aired", "premiered"):
        node = root.find(tag)
        if node is not None and node.text and node.text.strip():
            out[tag] = node.text.strip()
    return out


def _int(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ─── Noms de fichiers ────────────────────────────────────────────────────────


def season_number(name: str) -> int | None:
    match = _SEASON_NUMBER.match(name.strip())
    return int(match.group(1)) if match else None


def episode_number(stem: str, series_title: str = "") -> int | None:
    """Numéro d'épisode lu dans un nom de fichier, ou None."""
    explicit = _EPISODE_EXPLICIT.findall(stem)
    if explicit:
        return int(explicit[-1])
    text = stem
    if series_title:
        text = re.sub(re.escape(series_title), " ", text, flags=re.IGNORECASE)
    text = _TAGS.sub(" ", text)
    numbers = [int(n) for n in _BARE_NUMBER.findall(text)]
    numbers = [n for n in numbers if not 1900 <= n <= 2100]  # une année n'est pas un épisode
    return numbers[-1] if numbers else None


def clean_title(stem: str, series_title: str, number: int) -> str:
    """« [Kaizoku] Naruto Kai - 015 - Le Pays des Vagues [1080p] » → « Le Pays des Vagues »."""
    text = _TAGS.sub(" ", stem)
    if series_title:
        text = re.sub(re.escape(series_title), " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"(?:s\d{1,3}\s*e|\b[ée]p(?:isode)?|\be|#)\s*[-_.]?\s*0*\d{1,4}(?!\d)",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(rf"(?<!\d)0*{number}(?!\d)", " ", text, count=1)
    text = re.sub(r"[_.]+", " ", text)
    # Nommage courant « Série - 015 - Titre » : le titre est le dernier morceau
    parts = [
        p.strip()
        for p in re.split(r"\s[-–·:]+\s|\s[-–]+$|^[-–]+\s", f" {text} ")
        if p.strip(" -–·:")
    ]
    text = parts[-1].strip(" -–·:") if parts else ""
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text or f"Épisode {number}"


# ─── Scan ────────────────────────────────────────────────────────────────────


def _image_beside(directory: Path, names: list[str], stems: tuple[str, ...]) -> str | None:
    """Premier fichier image dont le nom (sans extension) est dans [stems]."""
    lowered = {n.lower(): n for n in names}
    for stem in stems:
        for ext in ("jpg", "jpeg", "png", "webp"):
            if f"{stem}.{ext}" in lowered:
                return lowered[f"{stem}.{ext}"]
    return None


def _videos(directory: Path) -> tuple[list[str], list[str], list[str]]:
    """(vidéos, sous-dossiers, tous les noms) d'un dossier, sans les éléments cachés."""
    try:
        entries = [e for e in os.scandir(directory) if not _hidden(e.name)]
    except OSError:
        return [], [], []
    videos = sorted(
        (e.name for e in entries if e.is_file() and _ext(e.name) in VIDEO_EXTENSIONS),
        key=natural_key,
    )
    dirs = sorted((e.name for e in entries if e.is_dir()), key=natural_key)
    return videos, dirs, [e.name for e in entries]


def _episodes(
    root: Root,
    directory: Path,
    relative: str,
    season: int,
    videos: list[str],
    names: list[str],
    series_title: str,
) -> list[Episode]:
    found = []
    for name in videos:
        stem = name.rsplit(".", 1)[0]
        nfo = read_nfo(directory / f"{stem}.nfo")
        number = _int(nfo.get("episode")) or episode_number(stem, series_title)
        thumb = _image_beside(directory, names, (f"{stem}-thumb".lower(), stem.lower()))
        child = f"{relative}/{name}" if relative else name
        found.append(
            {
                "number": number,
                "stem": stem,
                "nfo": nfo,
                "token": encode_token(root.id, child),
                "watch_id": watch_id(Path(os.path.realpath(directory / name))),
                "image": encode_token(root.id, f"{relative}/{thumb}" if relative else thumb)
                if thumb
                else None,
            }
        )
    # Numéros absents ou en double : l'ordre naturel fait foi (1, 2, 3…)
    numbers = [f["number"] for f in found]
    if None in numbers or len(set(numbers)) != len(numbers):
        for index, item in enumerate(found, start=1):
            item["number"] = index
    return [
        Episode(
            season=season,
            number=item["number"],
            title=item["nfo"].get("title")
            or clean_title(item["stem"], series_title, item["number"]),
            overview=item["nfo"].get("plot"),
            token=item["token"],
            watch_id=item["watch_id"],
            image=item["image"],
            aired=item["nfo"].get("aired"),
        )
        for item in sorted(found, key=lambda f: f["number"])
    ]


def scan(root: Root, directory: Path, relative: str, series_title: str) -> Scan:
    """Saisons et épisodes d'une série maison (voir l'en-tête du module)."""
    loose, subdirs, names = _videos(directory)
    seasons_found = []
    for sub in subdirs:
        sub_videos, _, sub_names = _videos(directory / sub)
        if sub_videos:
            seasons_found.append((sub, sub_videos, sub_names))

    numbers = [season_number(sub) for sub, _, _ in seasons_found]
    if None in numbers or len(set(numbers)) != len(numbers) or 0 in numbers:
        numbers = list(range(1, len(seasons_found) + 1))  # numéros ambigus : l'ordre fait foi
    seasons = []
    for number, (sub, sub_videos, sub_names) in zip(numbers, seasons_found, strict=True):
        child = f"{relative}/{sub}" if relative else sub
        season_nfo = read_nfo(directory / sub / "season.nfo")
        seasons.append(
            Season(
                number=number,
                name=season_nfo.get("title") or sub,
                episodes=_episodes(
                    root, directory / sub, child, number, sub_videos, sub_names, series_title
                ),
            )
        )
    if loose:
        number = 1 if not seasons else max(s.number for s in seasons) + 1
        name = "Saison 1" if not seasons else "Autres"
        seasons.append(
            Season(
                number,
                name,
                _episodes(root, directory, relative, number, loose, names, series_title),
            )
        )
    seasons.sort(key=lambda s: s.number)

    show = read_nfo(directory / "tvshow.nfo")
    poster = _image_beside(directory, names, _POSTER_NAMES)
    fanart = _image_beside(directory, names, _FANART_NAMES)

    def image_token(name: str | None) -> str | None:
        if not name:
            return None
        return encode_token(root.id, f"{relative}/{name}" if relative else name)

    year = _int(show.get("year")) or _int((show.get("premiered") or "")[:4])
    return Scan(
        seasons=seasons,
        title=show.get("title"),
        overview=show.get("plot"),
        year=year,
        poster=image_token(poster),
        fanart=image_token(fanart),
    )


def signature(directory: Path) -> tuple[Any, ...]:
    """Empreinte rapide du dossier (dates de modification de la série et de ses saisons).

    Un épisode ajouté, renommé ou supprimé change la date de son dossier : le
    scan en cache est alors refait, sinon il est réutilisé.
    """
    try:
        stamps = [directory.stat().st_mtime]
        for entry in os.scandir(directory):
            if entry.is_dir() and not _hidden(entry.name):
                stamps.append((entry.name, entry.stat().st_mtime))
        return tuple(stamps)
    except OSError:
        return ()


def image_url(token: str | None) -> str | None:
    return f"/api/videos/image/{token}" if token else None

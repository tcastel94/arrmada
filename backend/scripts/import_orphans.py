#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArrMada — Import Orphans
========================
Scan les répertoires de téléchargements Deluge, identifie les fichiers
non-importés (séries TV et films), les fait correspondre à la médiathèque
existante, gère les doublons, et les déplace/renomme proprement.

Usage:
    python3 import_orphans.py              # Exécution réelle
    python3 import_orphans.py --dry-run    # Simulation sans rien bouger
    python3 import_orphans.py --source sonarr   # Sonarr uniquement
    python3 import_orphans.py --source radarr   # Radarr uniquement
    python3 import_orphans.py --source all      # Tout scanner (défaut)
    python3 import_orphans.py --report          # Afficher rapport final étendu

Author: ArrMada
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MEDIA_ROOT = Path("/mnt/user/medias")

SERIES_ROOT = MEDIA_ROOT / "seriesTV"
MOVIES_ROOT = MEDIA_ROOT / "movies"

DOWNLOAD_SOURCES = [
    MEDIA_ROOT / "downloads",
    MEDIA_ROOT / "downloads" / "complete",
    MEDIA_ROOT / "downloads" / "complete" / "sonarr",
    MEDIA_ROOT / "downloads" / "complete" / "radarr",
    MEDIA_ROOT / "downloads" / "complete" / "completed",
]

# Sous-dossiers de downloads à ignorer lors du scan racine
SKIP_SUBDIRS = {"complete", "completed", "sonarr", "radarr", "incomplete", "youtube"}

# Extensions vidéo acceptées
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov", ".ts", ".m2ts"}

# Titres à exclure/supprimer (normalisés, lowercase)
EXCLUDED_TITLES = {"blackish", "black ish", "black-ish", "black.ish"}

# Seuil de similarité fuzzy (0-100)
FUZZY_THRESHOLD = 90

# Tags de qualité reconnus (ordre décroissant = meilleur)
QUALITY_HIERARCHY = [
    ("remux",    100),
    ("2160p",    90),
    ("4k",       88),
    ("uhd",      87),
    ("1080p",    70),
    ("720p",     50),
    ("480p",     30),
    ("sd",       10),
]

CODEC_HIERARCHY = [
    ("webdl",   20),
    ("web-dl",  20),
    ("web dl",  20),
    ("webrip",  15),
    ("bluray",  18),
    ("blu-ray", 18),
    ("hdtv",    10),
    ("dvd",      5),
]

# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

MediaType = Literal["episode", "movie", "unknown"]
ResultStatus = Literal[
    "imported", "duplicate_replaced", "duplicate_kept_existing",
    "no_library_match", "series_not_in_library", "excluded_deleted",
    "skipped_non_media", "error"
]


@dataclass
class ParsedMedia:
    source_path: Path
    media_type: MediaType
    raw_title: str            # Titre brut nettoyé
    normalized_title: str     # Titre normalisé pour fuzzy match
    year: str | None = None
    season: int | None = None
    episode: int | None = None
    quality_tag: str = ""
    quality_score: int = 0
    video_file: Path | None = None  # Fichier vidéo principal


@dataclass
class ImportResult:
    source: Path
    status: ResultStatus
    detail: str = ""
    destination: Path | None = None
    replaced: Path | None = None


# ─────────────────────────────────────────────────────────────────────────────
# PARSING
# ─────────────────────────────────────────────────────────────────────────────

# Regex pour détecter un épisode TV (SxxExx ou sxxexx)
RE_EPISODE = re.compile(r'[Ss](\d{1,2})[Ee](\d{2,3})', re.IGNORECASE)
# Regex pour détecter une année (1900-2099)
RE_YEAR = re.compile(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)')
# Balises parasites à supprimer pour obtenir un titre propre
RE_QUALITY_TAGS = re.compile(
    r'(?i)\b('
    r'2160p|4k|uhd|1080p|720p|480p|sd|'
    r'web[\-\s]?dl|webrip|web|bluray|blu[\-\s]?ray|hdtv|dvd|remux|'
    r'hevc|h\.?265|h\.?264|avc|xvid|divx|x265|x264|av1|vp9|'
    r'dts[\-\s]?hd|dts|truehd|atmos|dts[\-\s]?ma|ac3|aac|'
    r'dd5\.1|ddp5\.1|eac3|flac|mp3|'
    r'hdr10?|dolby|dv|dolby[\s\-]?vision|'
    r'proper|repack|internal|extended|theatrical|directors\.?cut|'
    r'multi|vf2?|vostfr|'
    r'ntb|nf|stan|amzn|amazon|hulu|max|peacock|apple|disney|adn|iq|'
    r'\w+\[tgx\]|\[eztvx?\.to\]|\[rartv\]|\[eztv\]'
    r')\b',
    re.IGNORECASE
)
# Groupes de release en fin de nom (ex: -ELiTE, -NTb, -SuccessfulCrab)
RE_RELEASE_GROUP = re.compile(r'[\-\s][\w]+$')
# Balises www.*, -, {}, []
RE_NOISE = re.compile(r'www\.\S+\s*|[\[\]{}<>]|\(by\s+\w+\)', re.IGNORECASE)
# Séparateurs multiples → espace
RE_SEPARATORS = re.compile(r'[\.\-_]+')


def _clean_name(name: str) -> str:
    """Supprime l'extension si présente, remplace séparateurs par espaces."""
    name = Path(name).stem if '.' in name and not name.startswith('.') else name
    # Supprimer préfixes parasites comme _UNPACK_, _FAILED_, etc.
    name = re.sub(r'^_[A-Z]+_\s*', '', name)
    # Supprimer préfixes www.xxx.org/com - ...
    name = re.sub(r'(?i)^www\.\S+\s*[-–]\s*', '', name)
    name = RE_NOISE.sub(' ', name)
    name = RE_SEPARATORS.sub(' ', name)
    return name.strip()


def normalize_title(raw: str) -> str:
    """Normalise un titre pour la comparaison fuzzy."""
    s = raw.lower()
    s = RE_NOISE.sub(' ', s)
    s = RE_QUALITY_TAGS.sub(' ', s)
    s = RE_SEPARATORS.sub(' ', s)
    # Supprimer caractères spéciaux sauf apostrophe
    s = re.sub(r"[^\w\s']", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_quality_tag(raw_name: str) -> str:
    """Extrait un tag de qualité lisible depuis le nom brut."""
    raw_lower = raw_name.lower()
    parts = []

    # Résolution
    for res in ("2160p", "1080p", "720p", "480p"):
        if res in raw_lower:
            parts.append(res.upper())
            break

    # Source
    for src, label in [
        ("web-dl", "WEB-DL"), ("webdl", "WEB-DL"), ("webrip", "WEBRip"),
        ("blu-ray", "BluRay"), ("bluray", "BluRay"), ("remux", "REMUX"),
        ("hdtv", "HDTV"), ("dvd", "DVD"),
    ]:
        if src in raw_lower:
            parts.append(label)
            break

    return "-".join(parts) if parts else "Unknown"


def quality_score(raw_name: str) -> int:
    """Retourne un score de qualité entier (plus grand = meilleur)."""
    name_lower = raw_name.lower()
    score = 0
    for tag, pts in QUALITY_HIERARCHY:
        if tag in name_lower:
            score += pts
            break
    for tag, pts in CODEC_HIERARCHY:
        if tag in name_lower:
            score += pts
            break
    if "remux" in name_lower:
        score += 15
    return score


# Regex pour dossier saison entière : "Invincible - S01 -" ou "Series.S02."  (sans Exx)
RE_SEASON_ONLY = re.compile(r'[\s\-\.][Ss](\d{1,2})[\s\-\.](?!E\d)', re.IGNORECASE)


def parse_item(path: Path) -> ParsedMedia:
    """Analyse un chemin (fichier ou dossier) et retourne un ParsedMedia."""
    name = path.name
    clean = _clean_name(name)

    # Détection épisode TV (SxxExx)
    ep_match = RE_EPISODE.search(name)
    if ep_match:
        season_num = int(ep_match.group(1))
        ep_num     = int(ep_match.group(2))

        # Titre = tout ce qui précède le SxxExx, en nettoyant les préfixes parasites
        raw_before = name[:ep_match.start()]
        title_raw = _clean_name(raw_before)
        title_raw = RE_QUALITY_TAGS.sub(' ', title_raw).strip()
        title_raw = re.sub(r'\s+', ' ', title_raw).strip()

        # Si le titre est vide après nettoyage (ex: "www.xxx.org - "), utiliser le nom complet nettoyé
        if not title_raw:
            # Appliquer _clean_name sur le nom complet puis retrancher avant SxxExx
            full_clean = _clean_name(name)
            ep_in_clean = RE_EPISODE.search(full_clean)
            if ep_in_clean:
                raw_before2 = full_clean[:ep_in_clean.start()]
            else:
                raw_before2 = full_clean
            title_raw = RE_QUALITY_TAGS.sub(' ', raw_before2)
            title_raw = re.sub(r'\s+', ' ', title_raw).strip()

        return ParsedMedia(
            source_path=path,
            media_type="episode",
            raw_title=title_raw,
            normalized_title=normalize_title(title_raw),
            season=season_num,
            episode=ep_num,
            quality_tag=extract_quality_tag(name),
            quality_score=quality_score(name),
        )

    # Détection dossier de saison complète (ex: "Invincible - S02 - 2160p...")
    season_match = RE_SEASON_ONLY.search(name)
    if season_match and path.is_dir():
        season_num = int(season_match.group(1))
        raw_before = name[:season_match.start()]
        title_raw = _clean_name(raw_before)
        title_raw = RE_QUALITY_TAGS.sub(' ', title_raw).strip()
        title_raw = re.sub(r'\s+', ' ', title_raw).strip()
        return ParsedMedia(
            source_path=path,
            media_type="episode",   # On le traite comme épisodes multiples
            raw_title=title_raw,
            normalized_title=normalize_title(title_raw),
            season=season_num,
            episode=-1,            # -1 = dossier de saison entière
            quality_tag=extract_quality_tag(name),
            quality_score=quality_score(name),
        )

    # Détection film (année 4 chiffres)
    year_match = RE_YEAR.search(clean)
    if year_match:
        year_val = year_match.group(1)
        title_raw = clean[:year_match.start()].strip()
        title_raw = RE_QUALITY_TAGS.sub(' ', title_raw)
        title_raw = re.sub(r'\s+', ' ', title_raw).strip()

        return ParsedMedia(
            source_path=path,
            media_type="movie",
            raw_title=title_raw,
            normalized_title=normalize_title(title_raw),
            year=year_val,
            quality_tag=extract_quality_tag(name),
            quality_score=quality_score(name),
        )

    # Inconnu
    return ParsedMedia(
        source_path=path,
        media_type="unknown",
        raw_title=clean,
        normalized_title=normalize_title(clean),
    )


# ─────────────────────────────────────────────────────────────────────────────
# FUZZY MATCHING
# ─────────────────────────────────────────────────────────────────────────────

def fuzzy_ratio(a: str, b: str) -> float:
    """Ratio de similarité 0-100 entre deux chaînes normalisées."""
    return SequenceMatcher(None, a, b).ratio() * 100


def find_best_library_match(normalized_title: str, library_root: Path) -> tuple[Path | None, float]:
    """Trouve le dossier de bibliothèque le plus proche du titre donné.
    Compare le titre contre le nom complet du dossier ET contre le nom court
    (sans l'année entre parenthèses) pour améliorer les correspondances.
    """
    best_path: Path | None = None
    best_ratio = 0.0

    for folder in library_root.iterdir():
        if not folder.is_dir():
            continue
        # Comparer avec le nom complet normalisé
        folder_title_full = normalize_title(folder.name)
        # Comparer aussi avec le nom sans l'année : "BMF (2021)" → "BMF"
        folder_title_short = normalize_title(re.sub(r'\s*\(\d{4}\)\s*$', '', folder.name))
        ratio_full  = fuzzy_ratio(normalized_title, folder_title_full)
        ratio_short = fuzzy_ratio(normalized_title, folder_title_short)
        # Bonus si le titre normalisé commence par le nom court (ex: "bmf" in "bmf black mafia family")
        starts_bonus = 10 if (folder_title_short and normalized_title.startswith(folder_title_short)) else 0
        # Bonus acronyme : si le nom court est un acronyme contenu au début du titre entrant
        # ex: dossier "BMF" et titre entrant "BMF Black Mafia Family" → acronyme match
        if len(folder_title_short) <= 5 and normalized_title.split()[:1] == [folder_title_short]:
            starts_bonus = max(starts_bonus, 30)
        ratio = max(ratio_full, ratio_short) + starts_bonus

        if ratio > best_ratio:
            best_ratio = ratio
            best_path = folder

    if best_ratio >= FUZZY_THRESHOLD:
        return best_path, best_ratio
    return None, best_ratio


# ─────────────────────────────────────────────────────────────────────────────
# EXCLUSION CHECK
# ─────────────────────────────────────────────────────────────────────────────

def is_excluded(title: str) -> bool:
    """Retourne True si le titre doit être exclu/supprimé."""
    norm = normalize_title(title)
    for excl in EXCLUDED_TITLES:
        if excl in norm or fuzzy_ratio(norm, excl) > 85:
            return True
    return False


def is_media_content(path: Path) -> bool:
    """Retourne True si le chemin contient du contenu vidéo (pas musique/zip/etc)."""
    name_lower = path.name.lower()
    # Exclure archives, musique, etc.
    non_media = {".zip", ".rar", ".nfo", ".jpg", ".png", ".srt", ".sub", ".mp3", ".flac", ".iso"}
    if path.is_file():
        return path.suffix.lower() in VIDEO_EXTENSIONS
    # Si c'est un dossier, vérifier qu'il contient au moins un fichier vidéo
    for f in path.rglob("*"):
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            return True
    return False


def find_video_in(path: Path) -> Path | None:
    """Trouve le plus grand fichier vidéo dans un dossier (l'épisode principal)."""
    best = None
    best_size = 0
    for f in path.rglob("*"):
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                sz = f.stat().st_size
                if sz > best_size:
                    best_size = sz
                    best = f
            except OSError:
                pass
    return best


# ─────────────────────────────────────────────────────────────────────────────
# DUPLICATE HANDLING
# ─────────────────────────────────────────────────────────────────────────────

def find_existing_episode(dest_season_dir: Path, season: int, episode: int) -> Path | None:
    """Cherche un fichier vidéo existant pour cet épisode dans le dossier de saison."""
    pattern = re.compile(rf'[Ss]{season:02d}[Ee]{episode:02d}', re.IGNORECASE)
    for f in dest_season_dir.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            if pattern.search(f.name):
                return f
    return None


def find_existing_movie(dest_movie_dir: Path) -> Path | None:
    """Cherche un fichier vidéo existant dans le dossier du film."""
    for f in dest_movie_dir.iterdir():
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
            return f
    return None


# ─────────────────────────────────────────────────────────────────────────────
# RENAMING
# ─────────────────────────────────────────────────────────────────────────────

def build_episode_filename(series_folder_name: str, season: int, episode: int,
                           quality_tag: str, ext: str) -> str:
    """Construit un nom de fichier épisode selon la convention Sonarr/Kodi."""
    # Extraire le nom de la série depuis le nom du dossier (sans l'année)
    series_name = re.sub(r'\s*\(\d{4}\)\s*$', '', series_folder_name).strip()
    return f"{series_name} - S{season:02d}E{episode:02d} - {quality_tag}{ext}"


def build_movie_filename(movie_folder_name: str, quality_tag: str, ext: str) -> str:
    """Construit un nom de fichier film."""
    return f"{movie_folder_name} {quality_tag}{ext}"


# ─────────────────────────────────────────────────────────────────────────────
# SCANNING
# ─────────────────────────────────────────────────────────────────────────────

def scan_source(source_dir: Path, is_root: bool = False) -> list[Path]:
    """Scanne un répertoire et retourne la liste des items à traiter."""
    items = []
    if not source_dir.exists():
        return items

    for entry in source_dir.iterdir():
        # Sauter les sous-répertoires connus si on est à la racine de downloads/
        if is_root and entry.is_dir() and entry.name.lower() in SKIP_SUBDIRS:
            continue
        # Sauter les sous-dossiers des dossiers complete/ (ils ont leurs propres sources)
        if entry.name in {"completed", "incomplete", "radarr", "sonarr"}:
            continue
        # Sauter les fichiers non-vidéo isolés (zips, nfo, jpg…)
        if entry.is_file() and entry.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        items.append(entry)

    return items


# ─────────────────────────────────────────────────────────────────────────────
# CORE PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def _import_season_folder(parsed: ParsedMedia, lib_folder: Path, ratio: float,
                          dry_run: bool) -> ImportResult:
    """Importe un dossier de saison entière : déplace chaque épisode dedans."""
    season_dir = lib_folder / f"Season {parsed.season}"
    video_files = list(parsed.source_path.rglob("*"))
    video_files = [f for f in video_files if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]

    if not video_files:
        return ImportResult(parsed.source_path, "skipped_non_media",
                            "Dossier de saison sans fichiers vidéo")

    imported = 0
    for vf in sorted(video_files):
        ep_match = RE_EPISODE.search(vf.name)
        if not ep_match:
            print(f"    [?EP]  {vf.name} (pas de numéro d'épisode)")
            continue
        ep_num = int(ep_match.group(2))
        qtag   = extract_quality_tag(vf.name) or parsed.quality_tag
        ext    = vf.suffix.lower()
        dest_filename = build_episode_filename(
            lib_folder.name, parsed.season, ep_num, qtag, ext)
        dest_path = season_dir / dest_filename

        existing = find_existing_episode(season_dir, parsed.season, ep_num) \
            if season_dir.exists() else None

        if existing:
            if quality_score(vf.name) <= quality_score(existing.name):
                print(f"    [DUP=] {vf.name}")
                continue
            if not dry_run:
                existing.unlink()

        print(f"    [OK]  {vf.name} → Season {parsed.season}/{dest_filename}")
        if not dry_run:
            season_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vf), str(dest_path))
        imported += 1

    if imported > 0 and not dry_run:
        try:
            shutil.rmtree(parsed.source_path)
        except Exception:
            pass

    return ImportResult(
        parsed.source_path, "imported" if imported > 0 else "skipped_non_media",
        f"{imported}/{len(video_files)} épisodes importés | Série: {lib_folder.name} | Match {ratio:.0f}%",
        destination=season_dir,
    )


def process_item(item: Path, dry_run: bool) -> ImportResult:
    """Traite un item (fichier ou dossier) : parse, match, déplace, renomme."""

    # 1. Parse
    parsed = parse_item(item)

    # 2. Exclusion check (black-ish, etc.)
    if is_excluded(parsed.raw_title):
        print(f"  [EXCLU]  {item.name}")
        if not dry_run:
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                return ImportResult(item, "error", f"Suppression échouée: {e}")
        return ImportResult(item, "excluded_deleted",
                            f"Titre exclu supprimé: {parsed.raw_title}")

    # 3. Vérifier que c'est du contenu média
    if not is_media_content(item):
        print(f"  [SKIP]   {item.name} (pas de contenu vidéo)")
        return ImportResult(item, "skipped_non_media", "Aucun fichier vidéo trouvé")

    # 4. Trouver le fichier vidéo principal
    if item.is_dir():
        video_file = find_video_in(item)
        if not video_file:
            return ImportResult(item, "skipped_non_media", "Dossier sans fichier vidéo")
    else:
        video_file = item

    ext = video_file.suffix.lower()

    # ── ÉPISODE TV ──────────────────────────────────────────────────────────
    if parsed.media_type == "episode":
        lib_folder, ratio = find_best_library_match(parsed.normalized_title, SERIES_ROOT)

        if lib_folder is None:
            print(f"  [?SERIE] {item.name} ({parsed.raw_title!r}, ratio={ratio:.0f}%)")
            return ImportResult(item, "series_not_in_library",
                                f"Série inconnue: {parsed.raw_title!r} (meilleur ratio={ratio:.0f}%)")

        # Dossier de saison entière (episode=-1) : déléguer à _import_season_folder
        if parsed.episode == -1:
            print(f"  [SAISON] {item.name} → {lib_folder.name} (S{parsed.season:02d}, match {ratio:.0f}%)")
            return _import_season_folder(parsed, lib_folder, ratio, dry_run)

        season_dir = lib_folder / f"Season {parsed.season}"
        dest_filename = build_episode_filename(
            lib_folder.name, parsed.season, parsed.episode,
            parsed.quality_tag, ext
        )
        dest_path = season_dir / dest_filename


        # Chercher doublon existant
        existing = find_existing_episode(season_dir, parsed.season, parsed.episode) \
            if season_dir.exists() else None

        if existing:
            existing_score = quality_score(existing.name)
            if parsed.quality_score <= existing_score:
                print(f"  [DUP=]   {item.name} → garde existant (score {existing_score} >= {parsed.quality_score})")
                return ImportResult(item, "duplicate_kept_existing",
                                    f"Existant conservé: {existing.name}")
            else:
                # Notre version est meilleure → remplacer
                print(f"  [DUP+]   {item.name} → remplace existant "
                      f"({parsed.quality_score} > {existing_score})")
                if not dry_run:
                    existing.unlink()

        # Créer dossier saison si nécessaire
        if not dry_run:
            season_dir.mkdir(parents=True, exist_ok=True)

        print(f"  [OK]     {item.name}")
        print(f"           → {dest_path.relative_to(MEDIA_ROOT)}")

        if not dry_run:
            try:
                shutil.move(str(video_file), str(dest_path))
                # Nettoyer le dossier source s'il est vide
                if item.is_dir():
                    try:
                        shutil.rmtree(item)
                    except Exception:
                        pass
            except Exception as e:
                return ImportResult(item, "error", str(e))

        status = "duplicate_replaced" if existing else "imported"
        return ImportResult(item, status,
                            f"Série: {lib_folder.name} | Match {ratio:.0f}%",
                            destination=dest_path,
                            replaced=existing if existing else None)

    # ── FILM ────────────────────────────────────────────────────────────────
    elif parsed.media_type == "movie":
        lib_folder, ratio = find_best_library_match(parsed.normalized_title, MOVIES_ROOT)

        if lib_folder is None:
            print(f"  [?FILM]  {item.name} ({parsed.raw_title!r}, ratio={ratio:.0f}%)")
            return ImportResult(item, "no_library_match",
                                f"Film inconnu: {parsed.raw_title!r} (meilleur ratio={ratio:.0f}%)")

        dest_filename = build_movie_filename(lib_folder.name, parsed.quality_tag, ext)
        dest_path = lib_folder / dest_filename

        # Chercher doublon
        existing = find_existing_movie(lib_folder)
        if existing:
            existing_score = quality_score(existing.name)
            if parsed.quality_score <= existing_score:
                print(f"  [DUP=]   {item.name} → garde existant (score {existing_score} >= {parsed.quality_score})")
                return ImportResult(item, "duplicate_kept_existing",
                                    f"Existant conservé: {existing.name}")
            else:
                print(f"  [DUP+]   {item.name} → remplace existant "
                      f"({parsed.quality_score} > {existing_score})")
                if not dry_run:
                    existing.unlink()

        print(f"  [OK]     {item.name}")
        print(f"           → {dest_path.relative_to(MEDIA_ROOT)}")

        if not dry_run:
            try:
                shutil.move(str(video_file), str(dest_path))
                if item.is_dir():
                    try:
                        shutil.rmtree(item)
                    except Exception:
                        pass
            except Exception as e:
                return ImportResult(item, "error", str(e))

        status = "duplicate_replaced" if existing else "imported"
        return ImportResult(item, status,
                            f"Film: {lib_folder.name} | Match {ratio:.0f}%",
                            destination=dest_path,
                            replaced=existing if existing else None)

    # ── INCONNU ─────────────────────────────────────────────────────────────
    else:
        print(f"  [UNKN]   {item.name} (type non détecté)")
        return ImportResult(item, "no_library_match", "Type non déterminé (ni épisode ni film)")


# ─────────────────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────────────────

def print_report(results: list[ImportResult], dry_run: bool) -> None:
    """Affiche le rapport final."""
    mode = "[DRY-RUN] " if dry_run else ""

    counts: dict[ResultStatus, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    print("\n")
    print("=" * 70)
    print(f"  {mode}RAPPORT IMPORT ORPHELINS — ArrMada")
    print("=" * 70)
    print(f"  Total traités         : {len(results)}")
    print(f"  ✔  Importés           : {counts.get('imported', 0)}")
    print(f"  ↑  Doublons remplacés : {counts.get('duplicate_replaced', 0)}")
    print(f"  =  Doublons conservés : {counts.get('duplicate_kept_existing', 0)}")
    print(f"  🗑  Exclus/supprimés  : {counts.get('excluded_deleted', 0)}")
    print(f"  ?  Série inconnue     : {counts.get('series_not_in_library', 0)}")
    print(f"  ?  Film inconnu       : {counts.get('no_library_match', 0)}")
    print(f"  ~  Ignorés (non-media): {counts.get('skipped_non_media', 0)}")
    print(f"  ✗  Erreurs            : {counts.get('error', 0)}")
    print("=" * 70)

    # Détails des non-matchés
    unmatched = [r for r in results if r.status in ("no_library_match", "series_not_in_library")]
    if unmatched:
        print(f"\n  [NON-MATCHÉS — à vérifier manuellement ({len(unmatched)})]")
        for r in unmatched:
            print(f"    - {r.source.name}")
            print(f"      {r.detail}")

    errors = [r for r in results if r.status == "error"]
    if errors:
        print(f"\n  [ERREURS ({len(errors)})]")
        for r in errors:
            print(f"    - {r.source.name}: {r.detail}")

    print()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

SOURCE_MAP = {
    "sonarr":    [MEDIA_ROOT / "downloads" / "complete" / "sonarr"],
    "radarr":    [MEDIA_ROOT / "downloads" / "complete" / "radarr"],
    "root":      [MEDIA_ROOT / "downloads"],
    "complete":  [MEDIA_ROOT / "downloads" / "complete"],
    "completed": [MEDIA_ROOT / "downloads" / "complete" / "completed"],
    "all": DOWNLOAD_SOURCES,
}


def clean_empty_and_orphans(sources: list[Path], dry_run: bool = True) -> tuple[int, int]:
    """Scanne les répertoires de téléchargement pour supprimer :
    1. Les dossiers qui ne contiennent AUCUN fichier vidéo (dossiers vides ou avec seulement .nfo, .jpg, .txt, etc.).
    2. Les fichiers parasites isolés (.nfo, .txt, .part, .torrent, .sample) à la racine de ces dossiers.
    """
    deleted_dirs = 0
    deleted_files = 0
    protected_names = {"complete", "completed", "sonarr", "radarr", "incomplete", "youtube"}

    print("\n" + "=" * 70)
    print("  NETTOYAGE DES DOSSIERS VIDES ET FICHIERS ORPHELIN")
    print("=" * 70)

    for src in sources:
        if not src.exists():
            continue

        for item in sorted(src.iterdir()):
            if item.name.lower() in protected_names or item.name.startswith("."):
                continue

            if item.is_dir():
                # Vérifier si le dossier contient au moins 1 fichier vidéo
                has_video = False
                for f in item.rglob("*"):
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        has_video = True
                        break

                if not has_video:
                    print(f"  [SUPPR DOSSIER VIDE/SANS VIDÉO] {item.name}")
                    if not dry_run:
                        try:
                            shutil.rmtree(item)
                            deleted_dirs += 1
                        except Exception as e:
                            print(f"    ✗ Erreur suppression: {e}")
                    else:
                        deleted_dirs += 1

            elif item.is_file():
                if item.suffix.lower() not in VIDEO_EXTENSIONS:
                    print(f"  [SUPPR FICHIER ORPHELIN] {item.name}")
                    if not dry_run:
                        try:
                            item.unlink()
                            deleted_files += 1
                        except Exception as e:
                            print(f"    ✗ Erreur suppression: {e}")
                    else:
                        deleted_files += 1

    mode = "[DRY-RUN] " if dry_run else ""
    print("-" * 70)
    print(f"  {mode}Dossiers supprimés : {deleted_dirs} | Fichiers orphelins supprimés : {deleted_files}")
    print("=" * 70 + "\n")
    return deleted_dirs, deleted_files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ArrMada — Import des fichiers orphelins dans la médiathèque"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulation : affiche les actions sans rien déplacer ni supprimer"
    )
    parser.add_argument(
        "--source", default="all",
        choices=list(SOURCE_MAP.keys()),
        help="Source à traiter (défaut: all)"
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Nettoyer les dossiers vides et fichiers orphelins dans les dossiers de téléchargement"
    )
    args = parser.parse_args()

    dry_run: bool = args.dry_run
    sources: list[Path] = SOURCE_MAP[args.source]

    if args.clean:
        clean_empty_and_orphans(sources, dry_run=dry_run)
        return

    if dry_run:
        print("\n  *** MODE DRY-RUN — aucun fichier ne sera déplacé ou supprimé ***\n")
    else:
        print("\n  *** MODE RÉEL — les fichiers vont être déplacés/supprimés ***\n")

    # Collecter tous les items à traiter
    all_items: list[Path] = []
    seen: set[Path] = set()

    for src in sources:
        is_root = (src == MEDIA_ROOT / "downloads")
        scanned = scan_source(src, is_root=is_root)
        for item in scanned:
            # Dédupliquer (un item peut apparaître dans plusieurs sources)
            resolved = item.resolve()
            if resolved not in seen:
                seen.add(resolved)
                all_items.append(item)

    print(f"  {len(all_items)} item(s) trouvé(s) à traiter dans {len(sources)} source(s).\n")

    results: list[ImportResult] = []
    for i, item in enumerate(all_items, 1):
        sys.stdout.write(f"[{i:4d}/{len(all_items)}] ")
        result = process_item(item, dry_run=dry_run)
        results.append(result)

    print_report(results, dry_run)


if __name__ == "__main__":
    main()


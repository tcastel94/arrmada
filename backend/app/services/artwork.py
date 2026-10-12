"""Artworks des films et séries : logos, disques, clearart, bannières, fonds…

Radarr et Sonarr ne fournissent que l'affiche, le fond et parfois un logo
(souvent en anglais). Ce module va chercher TOUT le reste, dans trois sources,
de la plus prioritaire à la moins :

  dossiers   les images rangées à côté du film / de la série : poster.jpg,
             fanart.jpg, clearlogo.png, disc.png, clearart.png, banner.jpg,
             landscape.jpg, characterart.png, extrafanart/… (Kodi,
             tinyMediaManager, le scraper NFO d'ArrMada). Ce sont TES images :
             elles passent devant. ArrMada les sert lui-même par une adresse
             signée (comme une URL pré-signée S3 : seul le serveur sait la
             fabriquer, personne ne peut demander un autre fichier).
  fanart.tv  logos HD, disques Blu-ray / DVD (films), clearart, bannières,
             vignettes, affiches, fonds, personnages et saisons (séries).
             Clé personnelle d'un compte gratuit (FANART_CLIENT_KEY) et/ou
             clé de projet (FANART_API_KEY).
  TMDB       logos, affiches, fonds (TMDB_API_KEY, déjà utilisée par « Pour toi »).

Deux usages du résultat, rangé en base (table media_artwork) :
  - les MEILLEURES images, une par type (dossier d'abord, puis français,
    anglais, sans texte, la plus appréciée) : fusionnées dans la médiathèque,
    la fiche et la file de téléchargement (web app et TV) ;
  - TOUTES les images (galerie) : onglet « Artworks » de la web app.
Les écrans n'interrogent donc jamais fanart.tv ou TMDB au moment d'afficher.

Déclenchement :
  - bouton « Artworks » de la Médiathèque (toute la médiathèque) ;
  - bouton « Actualiser les artworks » d'une fiche (un seul titre) ;
  - tâche planifiée (tasks/artwork_task.py) : les nouveaux titres, chaque jour.
Un titre déjà servi n'est redemandé qu'au bout de 30 jours (7 si rien n'avait
été trouvé, 1 h après une panne de réseau) : relancer le bouton est gratuit.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.config import settings
from app.database import async_session_factory
from app.models.artwork import MediaArtwork
from app.services.scraper_service import map_path
from app.utils.logger import get_logger

logger = get_logger(__name__)

FANART_URL = "https://webservice.fanart.tv/v3"
TMDB_URL = "https://api.themoviedb.org/3"
TMDB_IMAGES = "https://image.tmdb.org/t/p"

# Base utilisée par la récupération en arrière-plan (remplacée par celle des tests)
session_factory = async_session_factory

# Chemin Radarr/Sonarr → chemin vu par ArrMada (même traduction que les NFO).
# Remplacé dans les tests par un dossier temporaire.
map_folder: Callable[[str, str], str] = map_path

# Requêtes simultanées vers fanart.tv / TMDB : assez pour aller vite sur une
# grosse médiathèque, assez peu pour rester poli avec des services gratuits.
CONCURRENCY = 4
TIMEOUT = 15

# Délais avant de redemander un titre (voir needs_refresh)
REFRESH_OK = timedelta(days=30)
REFRESH_EMPTY = timedelta(days=7)
REFRESH_ERROR = timedelta(hours=1)

# Champs « meilleure image » stockés, dans l'ordre d'affichage du diagnostic
FIELDS = ("clearlogo", "discart", "clearart", "banner", "landscape", "poster", "fanart")

# Types de la galerie, dans l'ordre de l'onglet Artworks
KIND_ORDER = (
    "clearlogo",
    "discart",
    "clearart",
    "characterart",
    "poster",
    "keyart",
    "fanart",
    "landscape",
    "banner",
    "seasonposter",
    "seasonlandscape",
    "seasonbanner",
    "seasonfanart",
)

# fanart.tv : pour chaque meilleure image, les rubriques à essayer (HD d'abord)
FANART_SECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "movie": {
        "clearlogo": ("hdmovielogo", "movielogo"),
        "discart": ("moviedisc",),
        "clearart": ("hdmovieclearart", "movieart"),
        "banner": ("moviebanner",),
        "landscape": ("moviethumb",),
        "poster": ("movieposter",),
        "fanart": ("moviebackground",),
    },
    "series": {
        "clearlogo": ("hdtvlogo", "clearlogo"),
        "clearart": ("hdclearart", "clearart"),
        "banner": ("tvbanner",),
        "landscape": ("tvthumb",),
        "poster": ("tvposter",),
        "fanart": ("showbackground",),
    },
}

# fanart.tv : toutes les rubriques gardées dans la galerie → type
FANART_GALLERY: dict[str, dict[str, str]] = {
    "movie": {
        "hdmovielogo": "clearlogo",
        "movielogo": "clearlogo",
        "moviedisc": "discart",
        "hdmovieclearart": "clearart",
        "movieart": "clearart",
        "movieposter": "poster",
        "moviebackground": "fanart",
        "moviethumb": "landscape",
        "moviebanner": "banner",
    },
    "series": {
        "hdtvlogo": "clearlogo",
        "clearlogo": "clearlogo",
        "hdclearart": "clearart",
        "clearart": "clearart",
        "characterart": "characterart",
        "tvposter": "poster",
        "showbackground": "fanart",
        "tvthumb": "landscape",
        "tvbanner": "banner",
        "seasonposter": "seasonposter",
        "seasonthumb": "seasonlandscape",
        "seasonbanner": "seasonbanner",
    },
}
FANART_PER_KIND = 40  # au-delà, la galerie devient illisible
TMDB_PER_KIND = 20

# Langues préférées (« 00 » et vide = image sans texte)
_LANG_RANK = {"fr": 0, "en": 1, "00": 2, "": 2}
# Disques : Blu-ray d'abord (c'est ce que montre le boîtier), le 3D en dernier
_DISC_RANK = {"bluray": 0, "dvd": 1, "3d": 2}


# ── Choix des images (fonctions pures, testées) ──────────────────────────────


def lang_rank(lang: Any) -> int:
    """Rang d'une langue : français 0, anglais 1, sans texte 2, autre 3."""
    return _LANG_RANK.get(str(lang if lang is not None else "").strip().lower(), 3)


def _likes(image: dict[str, Any]) -> int:
    try:
        return int(image.get("likes") or 0)
    except (TypeError, ValueError):
        return 0


def _valid_fanart(image: Any) -> bool:
    return isinstance(image, dict) and str(image.get("url") or "").startswith("http")


def pick_fanart(data: dict[str, Any], sections: tuple[str, ...]) -> dict[str, Any] | None:
    """Meilleure image fanart.tv parmi `sections` : langue, puis rubrique HD, puis « likes »."""
    candidates = []
    for order, section in enumerate(sections):
        for image in data.get(section) or []:
            if _valid_fanart(image):
                candidates.append(
                    (
                        lang_rank(image.get("lang")),
                        order,
                        _DISC_RANK.get(str(image.get("disc_type") or "").lower(), 3),
                        -_likes(image),
                        image,
                    )
                )
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[:4])[4]


def parse_fanart(data: dict[str, Any], media_type: str) -> dict[str, str]:
    """Réponse fanart.tv → {champ: url} (+ « disc_type » quand un disque est trouvé)."""
    found: dict[str, str] = {}
    if not isinstance(data, dict):
        return found
    for field, sections in FANART_SECTIONS.get(media_type, {}).items():
        image = pick_fanart(data, sections)
        if image is None:
            continue
        found[field] = str(image["url"])
        if field == "discart":
            found["disc_type"] = str(image.get("disc_type") or "bluray").lower()
    return found


def fanart_preview(url: str) -> str:
    """Miniature fanart.tv (même image, servie en petit) : la galerie reste légère."""
    return url.replace("assets.fanart.tv/fanart/", "assets.fanart.tv/preview/", 1)


def _gallery_item(kind: str, url: str, source: str, **extra: Any) -> dict[str, Any]:
    """Entrée de galerie, toujours avec les mêmes clés (simple à lire côté web app)."""
    return {
        "kind": kind,
        "url": url,
        "preview": extra.get("preview") or url,
        "source": source,
        "lang": str(extra.get("lang") or ""),
        "likes": int(extra.get("likes") or 0),
        "disc_type": str(extra.get("disc_type") or ""),
        "season": str(extra.get("season") or ""),
        "name": str(extra.get("name") or ""),
    }


def parse_fanart_gallery(data: Any, media_type: str) -> list[dict[str, Any]]:
    """Réponse fanart.tv → TOUTES ses images, triées dans chaque type
    (langue, HD d'abord, Blu-ray avant DVD, la plus appréciée)."""
    if not isinstance(data, dict):
        return []
    ranked = []
    for section, kind in FANART_GALLERY.get(media_type, {}).items():
        hd = section.startswith("hd")
        for image in data.get(section) or []:
            if not _valid_fanart(image):
                continue
            url = str(image["url"])
            disc_type = str(image.get("disc_type") or "").lower()
            key = (
                lang_rank(image.get("lang")),
                0 if hd else 1,
                _DISC_RANK.get(disc_type, 3),
                -_likes(image),
            )
            item = _gallery_item(
                kind,
                url,
                "fanart.tv",
                preview=fanart_preview(url),
                lang=image.get("lang"),
                likes=_likes(image),
                disc_type=disc_type,
                season=image.get("season"),
            )
            ranked.append((kind, key, item))
    ranked.sort(key=lambda r: (r[0], r[1]))
    out: list[dict[str, Any]] = []
    per_kind: dict[str, int] = {}
    for kind, _key, item in ranked:
        if per_kind.get(kind, 0) < FANART_PER_KIND:
            per_kind[kind] = per_kind.get(kind, 0) + 1
            out.append(item)
    return out


def parse_tmdb_logo(data: dict[str, Any]) -> str:
    """Meilleur logo TMDB (PNG : Kodi ne sait pas afficher le SVG), URL en 500 px."""
    logos = []
    for logo in (data or {}).get("logos") or []:
        path = str((logo or {}).get("file_path") or "")
        if not path or path.lower().endswith(".svg"):
            continue
        try:
            votes = float(logo.get("vote_average") or 0)
        except (TypeError, ValueError):
            votes = 0.0
        logos.append((lang_rank(logo.get("iso_639_1") or "00"), -votes, path))
    if not logos:
        return ""
    return f"{TMDB_IMAGES}/w500{min(logos)[2]}"


def parse_tmdb_gallery(data: Any) -> list[dict[str, Any]]:
    """Réponse TMDB /images → logos (PNG), affiches et fonds, les mieux notés d'abord."""
    if not isinstance(data, dict):
        return []
    out: list[dict[str, Any]] = []
    for key, kind, preview_size in (
        ("logos", "clearlogo", "w300"),
        ("posters", "poster", "w342"),
        ("backdrops", "fanart", "w780"),
    ):
        ranked = []
        for image in data.get(key) or []:
            path = str((image or {}).get("file_path") or "")
            if not path.startswith("/") or path.lower().endswith(".svg"):
                continue
            try:
                votes = float(image.get("vote_average") or 0)
            except (TypeError, ValueError):
                votes = 0.0
            lang = image.get("iso_639_1") or ""
            ranked.append((lang_rank(lang or "00"), -votes, path, lang))
        ranked.sort()
        for _rank, _votes, path, lang in ranked[:TMDB_PER_KIND]:
            out.append(
                _gallery_item(
                    kind,
                    f"{TMDB_IMAGES}/original{path}",
                    "tmdb",
                    preview=f"{TMDB_IMAGES}/{preview_size}{path}",
                    lang=lang,
                )
            )
    return out


def sort_gallery(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Regroupe par type (ordre de l'onglet) en gardant l'ordre des sources :
    dossier, puis fanart.tv, puis TMDB. Les adresses en double disparaissent."""
    seen: set[str] = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    order = {kind: i for i, kind in enumerate(KIND_ORDER)}
    return sorted(unique, key=lambda i: order.get(i["kind"], len(order)))


def needs_refresh(
    status: str | None, fetched_at: datetime | None, now: datetime, force: bool = False
) -> bool:
    """Faut-il redemander ce titre ? (jamais demandé, ou réponse trop ancienne)."""
    if force or status is None or fetched_at is None:
        return True
    if fetched_at.tzinfo is None:  # SQLite rend des dates sans fuseau
        fetched_at = fetched_at.replace(tzinfo=UTC)
    delay = {"ok": REFRESH_OK, "empty": REFRESH_EMPTY}.get(status, REFRESH_ERROR)
    return now - fetched_at >= delay


def artwork_key(media_type: str, provider_id: Any) -> str:
    """« movie:438631 » (TMDB) ou « series:280619 » (TVDB)."""
    return f"{media_type}:{provider_id}"


def sources_configured() -> dict[str, bool]:
    return {
        "fanart": bool(settings.FANART_API_KEY or settings.FANART_CLIENT_KEY),
        "tmdb": bool(settings.TMDB_API_KEY),
        "local": bool(settings.ARTWORK_LOCAL_ENABLED),
    }


def fanart_params() -> dict[str, str]:
    """Clés fanart.tv : personnelle (`client_key`, compte gratuit) et/ou de projet."""
    params = {}
    if settings.FANART_API_KEY:
        params["api_key"] = settings.FANART_API_KEY
    if settings.FANART_CLIENT_KEY:
        params["client_key"] = settings.FANART_CLIENT_KEY
    return params


# ── Images des dossiers des médias ──────────────────────────────────────────

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
LOCAL_PREFIX = "/api/artwork/local"

# Nom de fichier (sans extension) → type. Conventions Kodi / Jellyfin / Emby /
# tinyMediaManager, et « img_xxx » du scraper NFO d'ArrMada.
LOCAL_KINDS = {
    "poster": "poster",
    "folder": "poster",
    "cover": "poster",
    "fanart": "fanart",
    "backdrop": "fanart",
    "background": "fanart",
    "clearlogo": "clearlogo",
    "logo": "clearlogo",
    "disc": "discart",
    "discart": "discart",
    "cdart": "discart",
    "clearart": "clearart",
    "banner": "banner",
    "landscape": "landscape",
    "thumb": "landscape",
    "characterart": "characterart",
    "keyart": "keyart",
}
# Sous-dossiers d'images supplémentaires (Kodi)
EXTRA_DIRS = {"extrafanart": "fanart", "extrathumbs": "landscape"}
_SEASON_RE = re.compile(
    r"^season(?:(\d{1,3})|-(specials|all))-(poster|banner|landscape|thumb|fanart)$"
)
_SEASON_KIND = {
    "poster": "seasonposter",
    "banner": "seasonbanner",
    "landscape": "seasonlandscape",
    "thumb": "seasonlandscape",
    "fanart": "seasonfanart",
}
LOCAL_LIMIT = 80  # un dossier de film n'en a jamais autant : garde-fou


def classify_local(filename: str) -> tuple[str, str, int] | None:
    """(type, saison, rang) d'un fichier image, ou None si ce n'est pas un artwork.

    « clearlogo.png » → ("clearlogo", "", 0) ; « Dune (2021)-disc.png » →
    ("discart", "", 1) ; « season01-poster.jpg » → ("seasonposter", "1", 0) ;
    « fanart2.jpg » → ("fanart", "", 1). Le rang départage plusieurs fichiers
    d'un même type (le nom exact d'abord).
    """
    stem, ext = os.path.splitext(filename)
    if ext.lower() not in IMAGE_EXTS:
        return None
    name = stem.strip().lower()
    season = _SEASON_RE.match(name)
    if season:
        number, special, part = season.groups()
        label = str(int(number)) if number is not None else special
        return _SEASON_KIND[part], label, 0
    if name.startswith("img_"):  # scraper NFO d'ArrMada
        name = name[4:]
    if name in LOCAL_KINDS:
        return LOCAL_KINDS[name], "", 0
    # Kodi : « <nom du fichier vidéo>-poster.jpg » ; Jellyfin : « backdrop2.jpg »
    last = name.rsplit("-", 1)[-1]
    for token in (last, re.sub(r"\d+$", "", last)):
        if token != name and token in LOCAL_KINDS:
            return LOCAL_KINDS[token], "", 1
    return None


def scan_local_folder(folder: str | Path) -> list[dict[str, Any]]:
    """Images d'artwork du dossier d'un film / d'une série (et de extrafanart/).

    Lecture seule, sans descendre dans les dossiers de saisons. Un dossier
    absent ou illisible donne simplement une liste vide.
    """
    found: list[dict[str, Any]] = []

    def add(path: str, name: str, kind: str, season: str, rank: int) -> None:
        try:
            mtime = int(os.stat(path).st_mtime)
        except OSError:
            return
        found.append(
            {
                "kind": kind,
                "season": season,
                "rank": rank,
                "path": path,
                "name": name,
                "mtime": mtime,
            }
        )

    try:
        with os.scandir(folder) as listing:
            entries = sorted(listing, key=lambda e: e.name.lower())
    except OSError:
        return []
    for entry in entries:
        if len(found) >= LOCAL_LIMIT:
            break
        try:
            if entry.is_file():
                match = classify_local(entry.name)
                if match:
                    add(entry.path, entry.name, *match)
            elif entry.is_dir() and entry.name.lower() in EXTRA_DIRS:
                kind = EXTRA_DIRS[entry.name.lower()]
                with os.scandir(entry.path) as sub_listing:
                    subs = sorted(sub_listing, key=lambda e: e.name.lower())
                for sub in subs[:30]:
                    if sub.is_file() and os.path.splitext(sub.name)[1].lower() in IMAGE_EXTS:
                        add(sub.path, f"{entry.name}/{sub.name}", kind, "", 2)
        except OSError:
            continue
    return found


def _sign(path: str) -> str:
    """Signature d'un chemin (HMAC-SHA256 avec le secret du serveur)."""
    secret = settings.effective_jwt_secret.encode()
    return hmac.new(secret, path.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def local_url(path: str, mtime: int = 0) -> str:
    """Adresse (relative au serveur) d'une image du dossier d'un média.

    Comme une URL pré-signée S3 : le chemin est encodé dans l'adresse et
    signé ; la route ne sert que ce que le serveur a lui-même signé.
    `v` change quand le fichier change (les caches navigateur / Kodi suivent).
    """
    token = base64.urlsafe_b64encode(path.encode("utf-8")).decode().rstrip("=")
    return f"{LOCAL_PREFIX}/{_sign(path)}/{token}{Path(path).suffix.lower()}?v={mtime}"


def local_roots() -> list[str]:
    """Dossiers d'où une image peut être servie : les racines des médias.

    Déduites de la même traduction de chemins que la lecture des dossiers :
    un chemin que la traduction ne touche pas n'est pas une racine.
    """
    roots = set()
    for service in ("radarr", "sonarr"):
        for prefix in ("/media", "/mangas", "/movies", "/tv"):
            mapped = map_folder(prefix, service)
            if mapped and mapped != prefix:
                roots.add(os.path.realpath(mapped))
    return sorted(roots)


def resolve_local(signature: str, name: str) -> Path | None:
    """Fichier désigné par une adresse de local_url(), ou None si elle est
    falsifiée, hors des dossiers des médias, pas une image ou introuvable."""
    token, dot, ext = name.rpartition(".")
    if not dot or f".{ext.lower()}" not in IMAGE_EXTS:
        return None
    try:
        path = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(_sign(path), signature):
        return None
    if Path(path).suffix.lower() != f".{ext.lower()}":
        return None
    real = os.path.realpath(path)  # liens symboliques résolus : pas d'évasion
    if not any(real == root or real.startswith(root + os.sep) for root in local_roots()):
        return None
    return Path(real) if os.path.isfile(real) else None


def local_gallery(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Images d'un dossier → entrées de galerie (meilleur nom d'abord)."""
    ordered = sorted(entries, key=lambda e: (e["rank"], e["name"].lower()))
    return [
        _gallery_item(
            e["kind"], local_url(e["path"], e["mtime"]), "local", season=e["season"], name=e["name"]
        )
        for e in ordered
    ]


def pick_local(entries: list[dict[str, Any]]) -> dict[str, str]:
    """Meilleure image du dossier pour chaque champ (nom exact d'abord)."""
    best: dict[str, str] = {}
    for item in local_gallery(entries):
        if item["kind"] in FIELDS and not item["season"]:
            best.setdefault(item["kind"], item["url"])
    return best


def media_folder(item: dict[str, Any]) -> str | None:
    """Dossier d'un titre de la médiathèque, vu par ArrMada (None si inconnu)."""
    path = str(item.get("path") or "").strip()
    if not path:
        return None
    service = "radarr" if item.get("type") == "movie" else "sonarr"
    return map_folder(path, service)


# ── Récupération d'un titre ─────────────────────────────────────────────────


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, str]) -> Any:
    """GET JSON ; None si le titre est inconnu du site (404). Lève sur panne."""
    response = await client.get(url, params=params)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def fetch_artwork(
    client: httpx.AsyncClient,
    media_type: str,
    provider_id: int,
    tmdb_tv_id: int | None = None,
    folder: str | None = None,
) -> dict[str, Any]:
    """Lit le dossier du titre, puis interroge fanart.tv et TMDB.

    Renvoie {"fields": {champ: url, "disc_type"}, "gallery": [...],
    "sources": [...], "status"} : status « ok » si au moins une image, « empty »
    si rien n'a été trouvé, « error » si un site était injoignable et que rien
    n'a été trouvé.
    """
    fields: dict[str, str] = {}
    gallery: list[dict[str, Any]] = []
    sources: list[str] = []
    failed = False

    # 1. Dossier du média (sans réseau : lu dans un fil à part, le disque du
    #    NAS peut mettre une seconde à se réveiller)
    local_best: dict[str, str] = {}
    if folder and settings.ARTWORK_LOCAL_ENABLED:
        entries = await asyncio.to_thread(scan_local_folder, folder)
        if entries:
            sources.append("local")
            gallery.extend(local_gallery(entries))
            local_best = pick_local(entries)

    # 2. fanart.tv
    params = fanart_params()
    if params:
        section = "movies" if media_type == "movie" else "tv"
        try:
            data = await _get_json(client, f"{FANART_URL}/{section}/{provider_id}", params)
            if data:
                sources.append("fanart.tv")
                fields.update(parse_fanart(data, media_type))
                gallery.extend(parse_fanart_gallery(data, media_type))
        except (httpx.HTTPError, ValueError) as exc:
            failed = True
            logger.debug("fanart.tv %s %s : %s", media_type, provider_id, exc)

    # 3. TMDB : logos (si fanart.tv n'en a pas), et toutes ses images pour la galerie
    tmdb_id = provider_id if media_type == "movie" else tmdb_tv_id
    if settings.TMDB_API_KEY and tmdb_id:
        kind = "movie" if media_type == "movie" else "tv"
        try:
            data = await _get_json(
                client,
                f"{TMDB_URL}/{kind}/{tmdb_id}/images",
                {"api_key": settings.TMDB_API_KEY, "include_image_language": "fr,en,null"},
            )
            if data is not None:
                sources.append("tmdb")
                gallery.extend(parse_tmdb_gallery(data))
                logo = parse_tmdb_logo(data)
                if logo and not fields.get("clearlogo"):
                    fields["clearlogo"] = logo
        except (httpx.HTTPError, ValueError) as exc:
            failed = True
            logger.debug("TMDB images %s %s : %s", kind, tmdb_id, exc)

    # Les images du dossier passent devant (ce sont celles de l'utilisateur)
    if local_best.get("discart"):
        fields.pop("disc_type", None)  # type du disque inconnu pour un fichier local
    fields.update(local_best)

    found = any(fields.get(f) for f in FIELDS)
    status = "ok" if found else ("error" if failed else "empty")
    return {
        "fields": fields,
        "gallery": sort_gallery(gallery),
        "sources": sources,
        "status": status,
    }


# ── Base de données ─────────────────────────────────────────────────────────


async def load_rows(db: AsyncSession) -> dict[str, MediaArtwork]:
    """Toutes les lignes, SANS la galerie (colonne chargée à la demande)."""
    rows = (await db.execute(select(MediaArtwork))).scalars().all()
    return {row.key: row for row in rows}


async def upsert(db: AsyncSession, values: list[dict[str, Any]]) -> None:
    """INSERT … ON CONFLICT (key) DO UPDATE, PostgreSQL comme SQLite."""
    if not values:
        return
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(MediaArtwork).values(values)
    updated = {c: stmt.excluded[c] for c in values[0] if c != "key"}
    await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_=updated))
    await db.commit()


def _row_values(item: dict[str, Any], result: dict[str, Any], now: datetime) -> dict[str, Any]:
    fields = result["fields"]
    gallery = result.get("gallery") or []
    return {
        "key": artwork_key(item["media_type"], item["provider_id"]),
        "media_type": item["media_type"],
        "provider_id": int(item["provider_id"]),
        "title": str(item.get("title") or "")[:300],
        **{f: str(fields.get(f) or "")[:1000] for f in FIELDS},
        "disc_type": str(fields.get("disc_type") or "")[:20],
        "gallery": gallery,
        "gallery_count": len(gallery),
        "sources": ",".join(result["sources"])[:60],
        "status": result["status"],
        "fetched_at": now,
    }


def as_images(row: MediaArtwork | None) -> dict[str, str]:
    """Ligne en base → {champ: url} (champs vides omis)."""
    if row is None:
        return {}
    images = {f: getattr(row, f) for f in FIELDS if getattr(row, f)}
    if row.discart and row.disc_type:
        images["disc_type"] = row.disc_type
    return images


# ── Fusion dans les réponses existantes ─────────────────────────────────────


async def apply_to_library(items: list[dict[str, Any]]) -> None:
    """Complète les éléments de la médiathèque (mêmes clés que media_aggregator).

    Le logo trouvé ici (dossier, puis français d'abord) passe devant celui de
    Radarr/Sonarr ; l'affiche et le fond de Radarr/Sonarr restent prioritaires
    (choisis par l'utilisateur), ceux d'ici ne servent qu'à combler un manque.

    Lecture dans une session À PART : la médiathèque est parfois calculée en
    parallèle d'autres lectures sur la session de l'appelant (tableau de bord
    Kodi), et une connexion PostgreSQL refuse deux requêtes simultanées.
    """
    try:
        async with session_factory() as db:
            rows = await load_rows(db)
    except Exception as exc:  # jamais bloquant pour la médiathèque
        logger.debug("Artworks indisponibles : %s", exc)
        return
    if not rows:
        return
    for item in items:
        if item.get("type") not in ("movie", "series") or not item.get("tmdb_id"):
            continue
        images = as_images(rows.get(artwork_key(item["type"], item["tmdb_id"])))
        if not images:
            continue
        if images.get("clearlogo"):
            item["clearlogo_url"] = images["clearlogo"]
        for field in ("discart", "clearart", "banner", "landscape"):
            if images.get(field):
                item[f"{field}_url"] = images[field]
        if images.get("disc_type"):
            item["disc_type"] = images["disc_type"]
        for field in ("poster", "fanart"):
            if images.get(field) and not item.get(f"{field}_url"):
                item[f"{field}_url"] = images[field]


async def merge_detail_images(
    db: AsyncSession, media_type: str, provider_id: Any, images: dict[str, Any]
) -> dict[str, Any]:
    """Complète le dict `images` d'une fiche (poster, fanart, banner, clearlogo…)."""
    if not provider_id:
        return images
    try:
        row = (
            await db.execute(
                select(MediaArtwork).where(MediaArtwork.key == artwork_key(media_type, provider_id))
            )
        ).scalar_one_or_none()
    except Exception as exc:
        logger.debug("Artworks indisponibles : %s", exc)
        return images
    found = as_images(row)
    merged = dict(images)
    if found.get("clearlogo"):
        merged["clearlogo"] = found["clearlogo"]
    for field in ("discart", "disc_type", "clearart", "landscape"):
        if found.get(field):
            merged[field] = found[field]
    for field in ("poster", "fanart", "banner"):
        if found.get(field) and not merged.get(field):
            merged[field] = found[field]
    return merged


# ── Récupération sur toute la médiathèque ───────────────────────────────────

_progress: dict[str, Any] = {
    "running": False,
    "total": 0,
    "done": 0,
    "found": 0,
    "errors": 0,
    "skipped": 0,
    "force": False,
    "started_at": None,
    "finished_at": None,
    "message": "",
}
_task: asyncio.Task | None = None


def library_targets(library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Titres de la médiathèque à traiter : films (TMDB) et séries (TVDB) identifiés."""
    targets = []
    seen = set()
    for item in library:
        media_type = item.get("type")
        provider_id = item.get("tmdb_id")  # séries : TVDB (convention media_aggregator)
        if media_type not in ("movie", "series") or not str(provider_id or "").isdigit():
            continue
        key = artwork_key(media_type, provider_id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "media_type": media_type,
                "provider_id": int(provider_id),
                "tmdb_tv_id": item.get("tmdb_tv_id"),
                "title": item.get("title") or "",
                "external_id": item.get("external_id"),
                "folder": media_folder(item),
            }
        )
    return targets


def _stale(row: MediaArtwork | None, now: datetime, force: bool) -> bool:
    """À redemander : délai dépassé, ou titre servi avant la galerie (1.20.1)."""
    if row is not None and row.status == "ok" and not row.gallery_count:
        return True
    return needs_refresh(row.status if row else None, row.fetched_at if row else None, now, force)


async def refresh_targets(
    db: AsyncSession, targets: list[dict[str, Any]], force: bool = False, track: bool = True
) -> dict[str, int]:
    """Récupère les artworks des `targets` qui en ont besoin et les range en base.

    `track` : met à jour la progression affichée par la web app (faux pour le
    bouton d'une fiche, qui ne doit pas brouiller une récupération globale).
    """
    progress = _progress if track else {"done": 0}
    now = datetime.now(UTC)
    rows = await load_rows(db)
    todo = [
        t
        for t in targets
        if _stale(rows.get(artwork_key(t["media_type"], t["provider_id"])), now, force)
    ]
    counts = {"total": len(todo), "found": 0, "errors": 0, "skipped": len(targets) - len(todo)}
    progress.update(total=len(todo), done=0, found=0, errors=0, skipped=counts["skipped"])
    if not todo:
        return counts

    semaphore = asyncio.Semaphore(CONCURRENCY)
    batch: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:

        async def _one(target: dict[str, Any]) -> None:
            async with semaphore:
                result = await fetch_artwork(
                    client,
                    target["media_type"],
                    target["provider_id"],
                    target.get("tmdb_tv_id"),
                    target.get("folder"),
                )
            batch.append(_row_values(target, result, datetime.now(UTC)))
            if result["status"] == "ok":
                counts["found"] += 1
            elif result["status"] == "error":
                counts["errors"] += 1
            progress.update(
                done=progress["done"] + 1, found=counts["found"], errors=counts["errors"]
            )

        # Par paquets : la base reçoit les résultats au fil de l'eau (un arrêt
        # du serveur en cours de route ne perd pas tout le travail fait).
        for start in range(0, len(todo), 50):
            await asyncio.gather(*(_one(t) for t in todo[start : start + 50]))
            await upsert(db, batch)
            batch.clear()
    return counts


def _invalidate_library_cache() -> None:
    from app.utils.cache import cache

    cache.invalidate("media:all")


async def refresh_library(force: bool = False) -> dict[str, int]:
    """Toute la médiathèque (bouton de la web app, tâche planifiée)."""
    from app.services import media_aggregator
    from app.services.activity_log import log_event

    started = time.monotonic()
    _progress.update(
        running=True,
        force=force,
        started_at=datetime.now(UTC).isoformat(),
        finished_at=None,
        message="Lecture de la médiathèque…",
    )
    counts = {"total": 0, "found": 0, "errors": 0, "skipped": 0}
    try:
        if not any(sources_configured().values()):
            _progress["message"] = (
                "Aucune source configurée (FANART_CLIENT_KEY, TMDB_API_KEY ou dossiers des médias)"
            )
            return counts
        async with session_factory() as db:
            library = await media_aggregator.fetch_all_media(db)
            _progress["message"] = "Récupération en cours…"
            counts = await refresh_targets(db, library_targets(library), force)
        _invalidate_library_cache()
        _progress["message"] = (
            f"{counts['found']} titre(s) avec des artworks sur {counts['total']} interrogé(s)"
            + (f", {counts['errors']} en échec" if counts["errors"] else "")
        )
        if counts["total"]:
            await log_event(
                category="library",
                action="artwork_refresh",
                status="error" if counts["errors"] and not counts["found"] else "ok",
                title="Artworks récupérés",
                detail=_progress["message"],
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        logger.info("Artworks : %s", _progress["message"])
        return counts
    except Exception as exc:
        logger.error("Récupération des artworks interrompue : %s", exc)
        _progress["message"] = f"Interrompue : {exc}"
        return counts
    finally:
        _progress.update(running=False, finished_at=datetime.now(UTC).isoformat())


def start_refresh(force: bool = False) -> bool:
    """Lance la récupération en arrière-plan ; False si elle tourne déjà."""
    global _task
    if _progress["running"] or (_task is not None and not _task.done()):
        return False
    _progress["running"] = True  # avant même le premier `await` du travail
    _task = asyncio.get_running_loop().create_task(refresh_library(force))
    return True


async def wait_for_refresh() -> None:
    """Attend la fin de la récupération en cours (tests, arrêt propre)."""
    if _task is not None:
        await _task


async def _library_item(db: AsyncSession, media_type: str, arr_id: int) -> dict[str, Any] | None:
    """Titre de la médiathèque d'après son numéro Radarr / Sonarr."""
    from app.services import media_aggregator

    library = await media_aggregator.fetch_all_media(db)
    return next(
        (
            m
            for m in library
            if m.get("type") == media_type and str(m.get("external_id")) == str(arr_id)
        ),
        None,
    )


async def refresh_one(db: AsyncSession, media_type: str, arr_id: int) -> dict[str, Any] | None:
    """Un seul titre, tout de suite (bouton d'une fiche). None si titre inconnu."""
    item = await _library_item(db, media_type, arr_id)
    targets = library_targets([item] if item else [])
    if not targets:
        return None
    await refresh_targets(db, targets, force=True, track=False)
    _invalidate_library_cache()
    row = (
        await db.execute(
            select(MediaArtwork).where(
                MediaArtwork.key == artwork_key(media_type, targets[0]["provider_id"])
            )
        )
    ).scalar_one_or_none()
    return {"status": row.status if row else "empty", "images": as_images(row)}


async def title_gallery(db: AsyncSession, media_type: str, arr_id: int) -> dict[str, Any] | None:
    """Toutes les images d'un titre (onglet Artworks). None si titre inconnu.

    En plus de la galerie rangée en base : l'affiche, le fond et le logo
    choisis dans Radarr / Sonarr (source « radarr » / « sonarr »), pour que
    l'onglet ne soit jamais vide, même avant la première récupération.
    """
    item = await _library_item(db, media_type, arr_id)
    if item is None:
        return None
    row = None
    provider_id = item.get("tmdb_id")
    if str(provider_id or "").isdigit():
        row = (
            await db.execute(
                select(MediaArtwork)
                .options(undefer(MediaArtwork.gallery))
                .where(MediaArtwork.key == artwork_key(media_type, provider_id))
            )
        ).scalar_one_or_none()
    arr = "radarr" if media_type == "movie" else "sonarr"
    from_arr = [
        _gallery_item(kind, str(item[field]), arr)
        for kind, field in (
            ("clearlogo", "clearlogo_url"),
            ("poster", "poster_url"),
            ("fanart", "fanart_url"),
        )
        if str(item.get(field) or "").startswith(("http://", "https://"))
    ]
    stored = list(row.gallery or []) if row is not None else []
    return {
        "title": item.get("title") or "",
        "status": row.status if row is not None else "never",
        "fetched_at": row.fetched_at.isoformat() if row is not None and row.fetched_at else None,
        "sources": [s for s in (row.sources.split(",") if row is not None else []) if s],
        "best": as_images(row),
        "images": sort_gallery(stored + from_arr),
    }


async def status(db: AsyncSession) -> dict[str, Any]:
    """Progression en cours + bilan de la base (pour la web app)."""
    rows = await db.execute(
        select(
            func.count(MediaArtwork.id),
            func.count(MediaArtwork.id).filter(MediaArtwork.clearlogo != ""),
            func.count(MediaArtwork.id).filter(MediaArtwork.discart != ""),
            func.count(MediaArtwork.id).filter(MediaArtwork.clearart != ""),
            func.coalesce(func.sum(MediaArtwork.gallery_count), 0),
        )
    )
    total, logos, discs, cleararts, images = rows.one()
    return {
        **_progress,
        "sources": sources_configured(),
        "stored": {
            "titles": total,
            "logos": logos,
            "discs": discs,
            "clearart": cleararts,
            "images": int(images or 0),
        },
    }

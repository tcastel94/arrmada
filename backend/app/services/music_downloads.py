"""Musique restée dans le dossier de téléchargements : la voir, l'importer.

Le problème
-----------
Un album téléchargé n'arrive pas toujours dans la bibliothèque : Lidarr ne
l'a pas reconnu (nom de dossier fantaisiste, étiquettes manquantes),
l'import a été refusé, ou l'album a été posé là à la main. Les fichiers
restent alors dans le dossier « terminés » de SABnzbd, invisibles.

Ce que fait ArrMada
-------------------
1. Il demande à **Lidarr** de passer en revue ce dossier et ses
   sous-dossiers (``/manualimport``, comme l'écran « Import manuel » de
   Lidarr) : pour chaque fichier audio, Lidarr dit à quel artiste, quel
   album et quelles pistes il correspond, ou pourquoi il le refuse.
2. Il regroupe ces fichiers par dossier d'album et dit, pour chacun, s'il
   est **prêt à importer** ou pourquoi il ne l'est pas.
3. Sur demande (web app ou TV), il lance l'import manuel de Lidarr pour un
   dossier (commande ``ManualImport``) : Lidarr range, renomme et ajoute à
   la bibliothèque, comme pour un téléchargement normal.

Quel dossier ?
--------------
Le dossier « terminés » déclaré dans SABnzbd (``complete_dir``), puis, en
secours, ``ARR_DOWNLOADS_PATH`` (le chemin des téléchargements tel que le
voient les *arr). C'est Lidarr qui lit le dossier : le chemin doit être
valable dans SON conteneur (c'est le cas avec des montages communs /data,
façon TRaSH).

Garde-fous (tout ou rien par dossier)
-------------------------------------
- seuls les fichiers que Lidarr a reconnus sans réserve (artiste, album et
  pistes trouvés, aucun refus) sont importés ;
- un dossier dont un seul fichier pose problème n'est pas importé : il est
  signalé avec la raison donnée par Lidarr ;
- jamais de remplacement d'un fichier déjà dans la bibliothèque ;
- l'import ne vise qu'un dossier situé sous l'un des dossiers passés en
  revue (un appareil ne peut pas faire importer n'importe quel chemin).

Bonus de films ignorés
----------------------
Un film téléchargé arrive parfois avec sa bande originale ou des chansons
dans ses bonus (« Movie Xtras/Soundtrack », « Featurettes »…). Lidarr les
voit comme de l'audio, mais ce ne sont pas des albums : ces dossiers sont
écartés de la liste (et refusés à l'import). Un dossier est un bonus de
film si l'un de ses dossiers, sous le dossier passé en revue :
- porte un nom de bonus (Extras, Xtras, Bonus, Featurettes, Trailers…) ;
- ou a un nom de sortie vidéo (1080p, 4K, UHD, BluRay, WEB-DL, x265,
  S01E02…).
"""

from __future__ import annotations

import posixpath
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.lidarr import LidarrClient
from app.services.sabnzbd import SabnzbdClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Dossiers à passer en revue ────────────────────────────────


async def sabnzbd_complete_dir(db: AsyncSession) -> str | None:
    """Dossier « terminés » de SABnzbd (``misc.complete_dir``), ou None."""
    res = await db.execute(
        select(Service).where(
            Service.type.in_(["sabnzbd", "SABnzbd"]),
            Service.is_enabled == True,  # noqa: E712
        )
    )
    svc = res.scalars().first()
    if svc is None:
        return None
    client = SabnzbdClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))
    try:
        data = await client._call("get_config")
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Musique : SABnzbd ne répond pas (%s)", exc)
        return None
    finally:
        await client.close()
    config = data.get("config", data) if isinstance(data, dict) else {}
    folder = str((config.get("misc") or {}).get("complete_dir") or "").strip()
    return folder.rstrip("/") or None


def download_roots(sab_complete: str | None) -> list[str]:
    """Dossiers à passer en revue : celui de SABnzbd, puis celui des *arr (sans doublon)."""
    roots: list[str] = []
    for folder in (sab_complete, settings.ARR_DOWNLOADS_PATH):
        clean = (folder or "").strip().rstrip("/")
        if clean.startswith("/") and clean not in roots:
            roots.append(clean)
    return roots


def is_under(folder: str, roots: list[str]) -> bool:
    """Vrai si ``folder`` est l'un des dossiers passés en revue ou se trouve dessous."""
    clean = posixpath.normpath(folder or "/")
    return any(clean == root or clean.startswith(root + "/") for root in roots)


# ── Bonus de films (sans réseau) ──────────────────────────────

# Noms de dossiers de bonus, comparés sans casse, espaces ni ponctuation
# (« Movie Xtras » → « moviextras »). Conventions Plex / Jellyfin / Kodi.
_EXTRA_DIRS = {
    "extras",
    "xtras",
    "moviextras",
    "movieextras",
    "bonus",
    "bonusfeatures",
    "bonusmaterial",
    "featurette",
    "featurettes",
    "behindthescenes",
    "deletedscenes",
    "interviews",
    "trailer",
    "trailers",
    "makingof",
    "sample",
    "samples",
}

# Marques d'une sortie vidéo dans un nom de dossier : définition, source,
# codec, épisode. Mot entier seulement (« 4K » oui, « 4Kids » non).
_VIDEO_TOKEN = re.compile(
    r"(?<![a-z0-9])("
    r"2160p|1080p|720p|480p|4k|uhd|hdr|blu-?ray|bdrip|brrip|webrip|web-?dl|remux"
    r"|[xh]\.?26[45]|hevc|dvdrip|hdtv|s\d{1,2}e\d{1,3}"
    r")(?![a-z0-9])",
    re.IGNORECASE,
)


def _plain(name: str) -> str:
    """« Movie Xtras » → « moviextras »."""
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def is_film_extra(folder: str, roots: list[str]) -> bool:
    """Vrai si ``folder`` est (ou est rangé dans) un bonus de film.

    Seuls les dossiers situés sous le dossier passé en revue comptent : le
    nom des dossiers de téléchargements eux-mêmes n'entre pas en jeu.
    """
    clean = posixpath.normpath(folder or "/")
    below = clean
    for root in sorted(roots, key=len, reverse=True):
        if clean == root or clean.startswith(root + "/"):
            below = clean[len(root) :]
            break
    for part in (p for p in below.split("/") if p):
        if _plain(part) in _EXTRA_DIRS or _VIDEO_TOKEN.search(part):
            return True
    return False


# ── Regroupement par album (sans réseau) ──────────────────────


def _album_folder(item: dict[str, Any]) -> str:
    """Dossier de l'album d'un fichier : le dossier qui le contient (CD1 / CD2 remontent d'un cran)."""
    folder = posixpath.dirname(item.get("path") or "")
    if posixpath.basename(folder).lower().replace(" ", "") in {f"cd{n}" for n in range(1, 10)} | {
        f"disc{n}" for n in range(1, 10)
    }:
        folder = posixpath.dirname(folder)
    return folder


def _ready(item: dict[str, Any]) -> bool:
    """Fichier reconnu sans réserve : artiste, album, pistes, aucun refus."""
    return bool(
        (item.get("artist") or {}).get("id")
        and (item.get("album") or {}).get("id")
        and item.get("tracks")
        and not item.get("rejections")
    )


def _reason(items: list[dict[str, Any]]) -> str | None:
    """Pourquoi un dossier n'est pas prêt, dans les mots de Lidarr (première raison trouvée)."""
    for item in items:
        for rejection in item.get("rejections") or []:
            if rejection.get("reason"):
                return str(rejection["reason"])
    for item in items:
        if not (item.get("artist") or {}).get("id"):
            return "Artiste non reconnu par Lidarr (suis-le d'abord, ou corrige les étiquettes)"
        if not (item.get("album") or {}).get("id"):
            return "Album non reconnu par Lidarr"
        if not item.get("tracks"):
            return "Pistes non reconnues par Lidarr"
    return None


def group_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fichiers vus par Lidarr → un élément par dossier d'album, prêt ou non.

    Rangés : prêts d'abord, puis par artiste et album.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("path"):
            groups.setdefault(_album_folder(item), []).append(item)

    albums = []
    for folder, files in groups.items():
        ready = all(_ready(f) for f in files)
        first = next((f for f in files if (f.get("album") or {}).get("id")), files[0])
        artist = (first.get("artist") or {}).get("artistName")
        album = (first.get("album") or {}).get("title")
        albums.append(
            {
                "folder": folder,
                "name": posixpath.basename(folder) or folder,
                "artist": artist,
                "album": album,
                "tracks": len(files),
                "size_bytes": sum(int(f.get("size") or 0) for f in files),
                "ready": ready,
                "reason": None if ready else _reason(files),
            }
        )
    albums.sort(
        key=lambda a: (not a["ready"], (a["artist"] or a["name"]).casefold(), a["album"] or "")
    )
    return albums


def import_payload(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fichiers de la commande ``ManualImport`` de Lidarr."""
    return [
        {
            "path": item["path"],
            "artistId": item["artist"]["id"],
            "albumId": item["album"]["id"],
            "albumReleaseId": item.get("albumReleaseId"),
            "trackIds": [t["id"] for t in item.get("tracks") or []],
            "quality": item.get("quality") or {},
            "indexerFlags": item.get("indexerFlags", 0),
            "downloadId": item.get("downloadId"),
            "disableReleaseSwitching": item.get("disableReleaseSwitching", False),
        }
        for item in items
    ]


# ── Appels à Lidarr ───────────────────────────────────────────


async def scan(client: LidarrClient, roots: list[str]) -> list[dict[str, Any]]:
    """Fichiers audio des dossiers (et sous-dossiers) vus par Lidarr, sans doublon."""
    seen: dict[str, dict[str, Any]] = {}
    for root in roots:
        try:
            items = await client.get(
                "/manualimport", params={"folder": root, "filterExistingFiles": "true"}
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("Musique : Lidarr ne peut pas lire %s (%s)", root, exc)
            continue
        for item in items if isinstance(items, list) else []:
            if item.get("path") and not item.get("additionalFile"):
                seen.setdefault(item["path"], item)
    return list(seen.values())


async def import_folder(client: LidarrClient, roots: list[str], folder: str) -> dict[str, Any]:
    """Importe un dossier d'album, tout ou rien. Rend {status, message}."""
    if not is_under(folder, roots):
        return {"status": "refused", "message": "Dossier hors des téléchargements"}
    if is_film_extra(folder, roots):
        return {"status": "refused", "message": "Bonus d'un film, pas un album"}
    try:
        items = await client.get(
            "/manualimport", params={"folder": folder, "filterExistingFiles": "true"}
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Musique : import de %s impossible (%s)", folder, exc)
        return {"status": "error", "message": "Lidarr ne répond pas"}
    files = [i for i in (items if isinstance(items, list) else []) if not i.get("additionalFile")]
    if not files:
        return {"status": "empty", "message": "Plus aucun fichier à importer dans ce dossier"}
    if not all(_ready(f) for f in files):
        return {"status": "not_ready", "message": _reason(files) or "Fichiers non reconnus"}
    await client.post(
        "/command",
        data={
            "name": "ManualImport",
            "files": import_payload(files),
            "importMode": "auto",  # déplacer, ou lien dur si le torrent partage encore
            "replaceExistingFiles": False,
        },
    )
    album = (files[0].get("album") or {}).get("title") or posixpath.basename(folder)
    return {"status": "ok", "message": f"Import lancé : {album} ({len(files)} pistes)"}

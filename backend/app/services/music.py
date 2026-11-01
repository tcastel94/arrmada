"""Musique : Lidarr (bibliothèque, demandes) et Jellyfin (écoute).

Comme pour les films (Radarr) et les séries (Sonarr), Lidarr est la source
de vérité de la bibliothèque musicale : artistes suivis, albums présents ou
manquants, file de téléchargement. Jellyfin sert l'écoute : sa bibliothèque
« Musique » doit pointer sur le dossier de Lidarr.

Ce module met en forme les réponses de Lidarr pour la web app et l'appli TV
(un seul format, en français, sans champs internes), et vérifie que Jellyfin
a bien une bibliothèque Musique.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services import jellyfin
from app.services.encryption import decrypt_api_key
from app.services.lidarr import LidarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Accès à Lidarr ────────────────────────────────────────────


async def lidarr_service(db: AsyncSession) -> Service | None:
    """Le Lidarr activé, ou None."""
    res = await db.execute(
        select(Service).where(Service.type == "lidarr", Service.is_enabled == True)  # noqa: E712
    )
    return res.scalars().first()


async def lidarr_client(db: AsyncSession, *, timeout: int = 15) -> LidarrClient:
    """Client du Lidarr activé ; 400 si aucun n'est déclaré (message lisible par la TV)."""
    svc = await lidarr_service(db)
    if svc is None:
        raise HTTPException(status_code=400, detail="Lidarr n'est pas configuré dans ArrMada")
    return LidarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key), timeout=timeout)


# ── Mise en forme ─────────────────────────────────────────────


def _image(images: list[dict[str, Any]] | None, *kinds: str) -> str | None:
    """Adresse publique de la première image du type demandé (affiche, fond…)."""
    for kind in kinds:
        for img in images or []:
            if img.get("coverType") == kind:
                url = img.get("remoteUrl") or img.get("url")
                if url and str(url).startswith("http"):
                    return str(url)
    return None


def _year(date: str | None) -> int | None:
    """« 1997-05-21T00:00:00Z » → 1997."""
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def _stats(item: dict[str, Any]) -> tuple[int, int]:
    """(pistes présentes, pistes attendues) d'un artiste ou d'un album Lidarr."""
    stats = item.get("statistics") or {}
    have = int(stats.get("trackFileCount") or 0)
    total = int(stats.get("trackCount") or stats.get("totalTrackCount") or 0)
    return have, total


def artist_summary(artist: dict[str, Any]) -> dict[str, Any]:
    """Artiste de la bibliothèque Lidarr, pour une grille ou une fiche."""
    have, total = _stats(artist)
    stats = artist.get("statistics") or {}
    return {
        "id": artist.get("id"),
        "mbid": artist.get("foreignArtistId"),  # identifiant MusicBrainz (lien avec Jellyfin)
        "name": artist.get("artistName") or "",
        "overview": artist.get("overview") or None,
        "genres": list(artist.get("genres") or [])[:3],
        "poster": _image(artist.get("images"), "poster", "cover", "banner"),
        "fanart": _image(artist.get("images"), "fanart", "banner"),
        "albums": int(stats.get("albumCount") or 0),
        "tracks_have": have,
        "tracks_total": total,
        "size_bytes": int(stats.get("sizeOnDisk") or 0),
        "monitored": bool(artist.get("monitored")),
    }


def album_summary(album: dict[str, Any]) -> dict[str, Any]:
    """Album d'un artiste : présent, partiel ou manquant."""
    have, total = _stats(album)
    if total and have >= total:
        status = "complete"
    elif have:
        status = "partial"
    else:
        status = "missing"
    return {
        "id": album.get("id"),
        "mbid": album.get("foreignAlbumId"),
        "title": album.get("title") or "",
        "year": _year(album.get("releaseDate")),
        "type": album.get("albumType") or "Album",  # Album, EP, Single…
        "cover": _image(album.get("images"), "cover", "poster", "disc"),
        "tracks_have": have,
        "tracks_total": total,
        "status": status,
        "monitored": bool(album.get("monitored")),
    }


def sort_albums(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Albums studio d'abord, puis EP et singles ; du plus récent au plus ancien."""
    order = {"Album": 0, "EP": 1, "Single": 2}
    return sorted(
        albums, key=lambda a: (order.get(a["type"], 3), -(a["year"] or 0), a["title"].lower())
    )


def lookup_result(item: dict[str, Any], library_mbids: set[str]) -> dict[str, Any]:
    """Résultat de recherche d'artiste (Lidarr / MusicBrainz), avec « déjà suivi ? »."""
    mbid = item.get("foreignArtistId") or ""
    return {
        "mbid": mbid,
        "name": item.get("artistName") or "",
        "overview": item.get("overview") or None,
        "type": item.get("artistType") or None,  # Person, Group…
        "genres": list(item.get("genres") or [])[:3],
        "poster": _image(item.get("images"), "poster", "cover", "banner"),
        "in_library": mbid in library_mbids,
    }


def add_payload(
    found: dict[str, Any], quality_profile: int, metadata_profile: int, root_folder: str
) -> dict[str, Any]:
    """Corps d'ajout d'un artiste à Lidarr : suivi complet, recherche des albums tout de suite."""
    return {
        **found,
        "qualityProfileId": quality_profile,
        "metadataProfileId": metadata_profile,
        "rootFolderPath": root_folder,
        "monitored": True,
        "monitorNewItems": "all",
        "addOptions": {"monitor": "all", "searchForMissingAlbums": True},
    }


def queue_item(record: dict[str, Any]) -> dict[str, Any]:
    """Téléchargement en cours dans Lidarr."""
    size = float(record.get("size") or 0)
    left = float(record.get("sizeleft") or 0)
    progress = round((size - left) / size, 3) if size > 0 else 0.0
    artist = (record.get("artist") or {}).get("artistName")
    album = (record.get("album") or {}).get("title")
    return {
        "id": record.get("id"),
        "title": " – ".join(p for p in (artist, album) if p) or record.get("title") or "",
        "status": record.get("trackedDownloadState") or record.get("status") or "",
        "progress": progress,
        "time_left": record.get("timeleft"),
    }


# ── Jellyfin : la bibliothèque Musique existe-t-elle ? ─────────


async def jellyfin_music_libraries(db: AsyncSession) -> list[str] | None:
    """Noms des bibliothèques Musique de Jellyfin ; None si Jellyfin est absent ou muet."""
    config = await jellyfin.get_config(db)
    if config is None:
        return None
    base, key = config
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{base}/Library/VirtualFolders", headers=jellyfin.auth_header(key)
            )
            resp.raise_for_status()
            folders = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Musique : Jellyfin ne répond pas (%s)", exc)
        return None
    return [
        str(f.get("Name") or "Musique")
        for f in folders
        if isinstance(f, dict) and str(f.get("CollectionType") or "").lower() == "music"
    ]

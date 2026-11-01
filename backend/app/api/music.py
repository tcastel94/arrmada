"""Musique (Lidarr + Jellyfin) : bibliothèque, recherche, ajout, file.

Mêmes routes pour la web app et l'appli TV (jeton d'appareil : lecture,
recherche et ajout d'un artiste ; voir services/devices.py). L'écoute
elle-même passe par Jellyfin.
"""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import music, tv_playback
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/music", tags=["music"], dependencies=[Depends(get_current_user)])


def _unreachable(exc: Exception) -> HTTPException:
    logger.warning("Musique : Lidarr ne répond pas (%s)", exc)
    return HTTPException(status_code=502, detail="Lidarr ne répond pas")


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)) -> dict:
    """Ce qui est prêt pour la musique : Lidarr déclaré, bibliothèque Musique dans Jellyfin."""
    lidarr = await music.lidarr_service(db) is not None
    libraries = await music.jellyfin_music_libraries(db)
    if not lidarr:
        hint = "Ajoute Lidarr dans Services pour gérer ta musique."
    elif libraries is None:
        hint = "Jellyfin est absent ou ne répond pas : l'écoute ne sera pas possible."
    elif not libraries:
        hint = (
            "Dans Jellyfin, ajoute une bibliothèque de type « Musique » qui pointe sur "
            "le dossier musique de Lidarr pour pouvoir écouter."
        )
    else:
        hint = None
    return {
        "lidarr": lidarr,
        "jellyfin": libraries is not None,
        "jellyfin_libraries": libraries or [],
        "ready": lidarr and bool(libraries),
        "hint": hint,
    }


@router.get("/artists")
async def artists(db: AsyncSession = Depends(get_db)) -> dict:
    """Artistes suivis par Lidarr, par ordre alphabétique."""
    client = await music.lidarr_client(db)
    try:
        items = await client.get_artists()
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    found = [music.artist_summary(a) for a in items]
    found.sort(key=lambda a: a["name"].casefold())
    return {"artists": found, "total": len(found)}


@router.get("/artists/{artist_id}")
async def artist(artist_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Fiche d'un artiste et ses albums (présents, partiels, manquants)."""
    client = await music.lidarr_client(db)
    try:
        detail, albums = await asyncio.gather(
            client.get_artist(artist_id), client.get_albums(artist_id)
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Artiste inconnu") from exc
        raise _unreachable(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    return {
        **music.artist_summary(detail),
        "album_list": music.sort_albums([music.album_summary(a) for a in albums]),
    }


@router.get("/lookup")
async def lookup(
    term: str = Query(..., min_length=2, max_length=100), db: AsyncSession = Depends(get_db)
) -> dict:
    """Recherche d'un artiste (MusicBrainz, via Lidarr), en indiquant ceux déjà suivis."""
    client = await music.lidarr_client(db)
    try:
        results, library = await asyncio.gather(client.lookup_artist(term), client.get_artists())
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    mbids = {a.get("foreignArtistId") for a in library if a.get("foreignArtistId")}
    return {"results": [music.lookup_result(r, mbids) for r in results[:20]]}


class AddArtist(BaseModel):
    mbid: str = Field(..., min_length=8, max_length=64, pattern=r"^[0-9a-fA-F-]+$")


@router.post("/artists", status_code=201)
async def add_artist(body: AddArtist, db: AsyncSession = Depends(get_db)) -> dict:
    """Suit un artiste dans Lidarr et lance la recherche de ses albums.

    Réglages pris dans Lidarr : premier profil de qualité, premier profil de
    métadonnées, premier dossier racine (ceux posés par l'installation).
    """
    client = await music.lidarr_client(db, timeout=30)
    try:
        found, library, qualities, metadata, roots = await asyncio.gather(
            client.lookup_artist(f"lidarr:{body.mbid}"),
            client.get_artists(),
            client.get_quality_profiles(),
            client.get_metadata_profiles(),
            client.get_root_folders(),
        )
        existing = next((a for a in library if a.get("foreignArtistId") == body.mbid), None)
        if existing is not None:
            raise HTTPException(
                status_code=409, detail=f"{existing.get('artistName')} est déjà suivi"
            )
        match = next((a for a in found if a.get("foreignArtistId") == body.mbid), None)
        if match is None:
            raise HTTPException(status_code=404, detail="Artiste introuvable sur MusicBrainz")
        if not (qualities and metadata and roots):
            raise HTTPException(
                status_code=400,
                detail="Lidarr n'a pas de profil de qualité, de métadonnées ou de dossier racine",
            )
        added = await client.add_artist(
            music.add_payload(match, qualities[0]["id"], metadata[0]["id"], roots[0]["path"])
        )
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    return music.artist_summary(added)


@router.get("/albums/{album_id}/tracks")
async def album_tracks(album_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Pistes d'un album à écouter (Jellyfin), dans l'ordre du disque.

    ``available`` faux avec une raison en clair si Jellyfin n'a pas l'album.
    """
    client = await music.lidarr_client(db)
    try:
        album = await client.get_album(album_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Album inconnu") from exc
        raise _unreachable(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    return await music.album_tracks(db, album)


@router.get("/stream/{item_id}")
async def stream(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Piste d'origine relayée depuis Jellyfin (avance dans la piste par « Range »)."""
    try:
        status_code, headers, body = await tv_playback.open_audio(
            db, item_id, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return StreamingResponse(body, status_code=status_code, headers=headers)


@router.get("/queue")
async def queue(db: AsyncSession = Depends(get_db)) -> dict:
    """Albums en cours de téléchargement."""
    client = await music.lidarr_client(db)
    try:
        page = await client.get_queue()
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    records = page.get("records", []) if isinstance(page, dict) else []
    return {"items": [music.queue_item(r) for r in records]}

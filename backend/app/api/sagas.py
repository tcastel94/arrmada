"""Sagas de films (collections Radarr / TMDB), voir docs/adr/016-sagas.md.

Mêmes routes pour la web app et l'appli TV :

- ``GET  /api/sagas``                  sagas de la bibliothèque, avec compteurs ;
- ``GET  /api/sagas/{id}``             une saga et tous ses films, dans l'ordre ;
- ``GET  /api/sagas/movie/{movie_id}`` la saga d'un film de Radarr (fiche film) ;
- ``POST /api/sagas/{id}/complete``    ajoute à Radarr les films manquants ;
- ``GET  /api/sagas/in-progress``      sagas commencées, pas finies (TV : accueil).

Le « vu » et la reprise sont ceux du profil famille de l'appel (ADR-008).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import sagas
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/sagas", tags=["sagas"], dependencies=[Depends(get_current_user)])


def _unreachable(exc: Exception) -> HTTPException:
    logger.warning("Sagas : Radarr ne répond pas (%s)", exc)
    return HTTPException(status_code=502, detail="Radarr ne répond pas")


async def _all_sagas(db: AsyncSession, profile_id: int | None) -> list[dict]:
    """Toutes les sagas (deux films au moins), avec le vu du profil, ordre alphabétique."""
    client = await sagas.radarr_client(db)
    try:
        collections, library = await sagas.load(client)
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    watch = await sagas.movie_watch(db, profile_id)
    year = sagas.this_year()
    items = sagas.sort_sagas([sagas.saga_summary(c, library, year, watch) for c in collections])
    # Une « collection » d'un seul film n'est pas une saga
    return [s for s in items if s["total"] > 1]


@router.get("")
async def list_sagas(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Sagas dont au moins un film est dans Radarr, ordre alphabétique."""
    items = await _all_sagas(db, user.get("profile_id"))
    return {
        "sagas": items,
        "total": len(items),
        "incomplete": sum(1 for s in items if not s["complete"]),
        "upcoming": sum(s["upcoming"] for s in items),
    }


@router.get("/in-progress")
async def sagas_in_progress(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Sagas commencées (un film vu ou en cours) et pas finies, la plus récente d'abord.

    Accueil de la TV : « Reprendre la saga » et rangée « Sagas à terminer ».
    """
    items = sagas.in_progress(await _all_sagas(db, user.get("profile_id")))
    return {"sagas": items, "total": len(items)}


@router.get("/movie/{movie_id}")
async def saga_of_movie(
    movie_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """La saga d'un film de Radarr et sa place dedans (bloc « Saga » de la fiche film).

    ``saga`` vaut null si le film n'appartient à aucune saga. ``following`` :
    le film suivant de la saga sur le NAS (fin d'un film sur la TV), ou null.
    """
    client = await sagas.radarr_client(db)
    try:
        movie = await client.get_movie_by_id(movie_id)
        tmdb = int((movie.get("collection") or {}).get("tmdbId") or 0)
        if not tmdb:
            return {"saga": None, "position": None, "following": None}
        collections, library = await sagas.load(client)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Film inconnu") from exc
        raise _unreachable(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    found = next((c for c in collections if int(c.get("tmdbId") or 0) == tmdb), None)
    if found is None:
        return {"saga": None, "position": None, "following": None}
    watch = await sagas.movie_watch(db, user.get("profile_id"))
    detail = sagas.saga_detail(found, library, sagas.this_year(), watch)
    if detail["total"] < 2:
        return {"saga": None, "position": None, "following": None}
    position = next(
        (i + 1 for i, f in enumerate(detail["films"]) if f["movie_id"] == movie_id), None
    )
    following = (
        next((f for f in detail["films"][position:] if f["state"] == "available"), None)
        if position
        else None
    )
    return {"saga": detail, "position": position, "following": following}


@router.get("/{saga_id}")
async def get_saga(
    saga_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Une saga et tous ses films (sur le NAS, attendus, manquants, annoncés)."""
    client = await sagas.radarr_client(db)
    try:
        collection = await client.get_collection(saga_id)
        library = sagas.library_by_tmdb(await client.get_movies())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Saga inconnue") from exc
        raise _unreachable(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    watch = await sagas.movie_watch(db, user.get("profile_id"))
    return sagas.saga_detail(collection, library, sagas.this_year(), watch)


class CompleteBody(BaseModel):
    # Identifiants TMDB des films à ajouter ; absent : tous les films manquants
    tmdb_ids: list[int] | None = Field(default=None, max_length=100)


@router.post("/{saga_id}/complete")
async def complete_saga(
    saga_id: int, body: CompleteBody | None = None, db: AsyncSession = Depends(get_db)
) -> dict:
    """« Compléter la saga » : ajoute à Radarr les films manquants (déjà sortis) et les cherche."""
    client = await sagas.radarr_client(db, timeout=60)
    try:
        collection = await client.get_collection(saga_id)
        library = sagas.library_by_tmdb(await client.get_movies())
        added = await sagas.complete(client, collection, library, body.tmdb_ids if body else None)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Saga inconnue") from exc
        raise _unreachable(exc) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise _unreachable(exc) from exc
    finally:
        await client.close()
    if not added:
        return {
            "status": "empty",
            "added": [],
            "message": "Aucun film sorti ne manque à cette saga",
        }
    count = len(added)
    s = "s" if count > 1 else ""
    return {
        "status": "ok",
        "added": added,
        "message": f"{count} film{s} ajouté{s} à Radarr, recherche lancée",
    }

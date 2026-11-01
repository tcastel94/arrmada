"""Sagas de films : les « collections » de Radarr (TMDB), voir docs/adr/016-sagas.md.

D'où viennent les sagas
-----------------------
Radarr range chaque film dans sa collection TMDB (Le Seigneur des anneaux,
Harry Potter…) dès qu'un film de la collection est dans la bibliothèque. Il
expose ces collections (``/api/v3/collection``) avec la liste COMPLÈTE de
leurs films, présents ou non. ArrMada n'ajoute aucune source : il croise
cette liste avec les films de Radarr (``/api/v3/movie``) pour dire, film par
film, s'il est sur le NAS, attendu, manquant ou pas encore sorti.

États d'un film dans une saga
-----------------------------
- ``available`` : dans Radarr, fichier présent (on peut le regarder) ;
- ``wanted``    : dans Radarr, pas encore de fichier (Radarr le cherche) ;
- ``missing``   : pas dans Radarr, déjà sorti (on peut l'ajouter) ;
- ``upcoming``  : pas dans Radarr, pas encore sorti (annoncé) ;
- ``excluded``  : écarté à la main dans Radarr (liste d'exclusions) : jamais
  ajouté par « Compléter la saga ».

Ordre : l'ordre de sortie (année, puis titre), le seul que TMDB donne.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Statuts TMDB / Radarr d'un film déjà sorti (au cinéma ou en vidéo)
_RELEASED = {"released", "inCinemas"}

_STATES = ("available", "wanted", "missing", "upcoming", "excluded")


async def radarr_client(db: AsyncSession, *, timeout: int = 30) -> RadarrClient:
    """Client du Radarr activé ; 400 si aucun n'est déclaré (message lisible par la TV)."""
    res = await db.execute(
        select(Service).where(Service.type == "radarr", Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if svc is None:
        raise HTTPException(status_code=400, detail="Radarr n'est pas configuré dans ArrMada")
    return RadarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key), timeout=timeout)


# ── Mise en forme (sans réseau) ───────────────────────────────


def _image(images: list[dict[str, Any]] | None, kind: str) -> str | None:
    """Adresse publique (TMDB) d'une image : affiche ou fond."""
    for img in images or []:
        if img.get("coverType") == kind:
            url = img.get("remoteUrl") or img.get("url")
            if url and str(url).startswith("http"):
                return str(url)
    return None


def _state(film: dict[str, Any], library: dict[int, dict[str, Any]], year_now: int) -> str:
    """État d'un film de saga, voir l'en-tête du module."""
    movie = library.get(int(film.get("tmdbId") or 0))
    if movie is not None:
        return "available" if movie.get("hasFile") else "wanted"
    if film.get("isExcluded"):
        return "excluded"
    status = film.get("status") or ""
    year = int(film.get("year") or 0)
    if status in _RELEASED or (status not in {"announced", "tba"} and 0 < year < year_now):
        return "missing"
    return "upcoming"


def film_summary(
    film: dict[str, Any], library: dict[int, dict[str, Any]], year_now: int
) -> dict[str, Any]:
    """Un film d'une saga, avec son état et, s'il est dans Radarr, son identifiant."""
    tmdb_id = int(film.get("tmdbId") or 0)
    movie = library.get(tmdb_id)
    return {
        "tmdb_id": tmdb_id,
        "movie_id": movie.get("id") if movie else None,
        "title": film.get("title") or "",
        "year": film.get("year") or None,
        "overview": film.get("overview") or None,
        "runtime": film.get("runtime") or None,
        "poster": _image(film.get("images"), "poster")
        or (_image(movie.get("images"), "poster") if movie else None),
        "state": _state(film, library, year_now),
    }


def _ordered(films: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordre de sortie ; un film sans année (annoncé) en dernier."""
    return sorted(films, key=lambda f: (f["year"] or 9999, f["title"].casefold()))


def saga_summary(
    collection: dict[str, Any], library: dict[int, dict[str, Any]], year_now: int
) -> dict[str, Any]:
    """Une saga pour la grille : compteurs et trois affiches pour l'éventail."""
    films = _ordered([film_summary(f, library, year_now) for f in collection.get("movies") or []])
    count = {s: sum(1 for f in films if f["state"] == s) for s in _STATES}
    posters = [f["poster"] for f in films if f["poster"]][:3]
    return {
        "id": collection.get("id"),
        "tmdb_id": collection.get("tmdbId"),
        "title": collection.get("title") or "",
        "overview": collection.get("overview") or None,
        "poster": _image(collection.get("images"), "poster") or (posters[0] if posters else None),
        "fanart": _image(collection.get("images"), "fanart"),
        "posters": posters,
        "monitored": bool(collection.get("monitored")),
        "total": len(films),
        "available": count["available"],
        "wanted": count["wanted"],
        "missing": count["missing"],
        "upcoming": count["upcoming"],
        # Rien à ajouter : tous les films sortis sont dans Radarr
        "complete": count["missing"] == 0,
        "years": [y for y in (films[0]["year"], films[-1]["year"]) if y] if films else [],
    }


def saga_detail(
    collection: dict[str, Any], library: dict[int, dict[str, Any]], year_now: int
) -> dict[str, Any]:
    """Fiche d'une saga : le résumé et tous ses films, dans l'ordre de sortie."""
    films = _ordered([film_summary(f, library, year_now) for f in collection.get("movies") or []])
    return {**saga_summary(collection, library, year_now), "films": films}


def sort_sagas(sagas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordre alphabétique (sans l'article « The » / « Le »…)."""

    def key(s: dict[str, Any]) -> str:
        title = s["title"].casefold()
        for article in ("the ", "le ", "la ", "les ", "l'"):
            if title.startswith(article):
                return title[len(article) :]
        return title

    return sorted(sagas, key=key)


def library_by_tmdb(movies: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Films de Radarr indexés par identifiant TMDB."""
    return {int(m["tmdbId"]): m for m in movies if m.get("tmdbId")}


def this_year() -> int:
    return datetime.now(UTC).year


# ── Appels à Radarr ───────────────────────────────────────────


async def load(client: RadarrClient) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """Collections de Radarr et films de la bibliothèque (par TMDB)."""
    collections = await client.get_collections()
    movies = await client.get_movies()
    return (collections if isinstance(collections, list) else []), library_by_tmdb(movies)


async def complete(
    client: RadarrClient,
    collection: dict[str, Any],
    library: dict[int, dict[str, Any]],
    tmdb_ids: list[int] | None,
) -> list[str]:
    """Ajoute à Radarr les films manquants d'une saga (ou ceux demandés) et les fait chercher.

    Seuls les films « manquants » (sortis, pas dans Radarr, pas exclus) sont
    ajoutés : un film annoncé n'a encore aucune release à trouver. Réglages
    de la saga dans Radarr (profil, dossier) s'ils existent, sinon les
    premiers de Radarr, comme pour une demande de film. Rend les titres ajoutés.
    """
    year_now = this_year()
    targets = [
        f
        for f in collection.get("movies") or []
        if _state(f, library, year_now) == "missing"
        and (tmdb_ids is None or int(f.get("tmdbId") or 0) in tmdb_ids)
    ]
    if not targets:
        return []
    profile = collection.get("qualityProfileId") or 0
    root = collection.get("rootFolderPath") or ""
    if not profile:
        profiles = await client.get_quality_profiles()
        profile = profiles[0]["id"] if profiles else 0
    if not root:
        folders = await client.get_root_folders()
        root = folders[0]["path"] if folders else ""
    if not profile or not root:
        raise HTTPException(
            status_code=409, detail="Radarr n'a ni profil de qualité ni dossier racine"
        )

    added: list[str] = []
    for film in targets:
        payload = {
            "title": film.get("title"),
            "tmdbId": film.get("tmdbId"),
            "year": film.get("year"),
            "images": film.get("images") or [],
            "qualityProfileId": profile,
            "rootFolderPath": root,
            "monitored": True,
            "minimumAvailability": collection.get("minimumAvailability") or "released",
            "addOptions": {"searchForMovie": True},
        }
        await client.add_movie(payload)
        added.append(str(film.get("title") or ""))
    logger.info("Saga « %s » : %d film(s) ajouté(s)", collection.get("title"), len(added))
    return added

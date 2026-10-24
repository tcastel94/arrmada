"""TMDB Recommendations API — real movie/series recommendations from TMDB."""

from __future__ import annotations

import random
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.services.media_aggregator import fetch_all_media
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"

router = APIRouter(
    prefix="/api/recommendations",
    tags=["recommendations"],
    dependencies=[Depends(get_current_user)],
)


async def _tvdb_to_tmdb(tvdb_id: int) -> int | None:
    """ID TVDB (Sonarr) → ID TMDB de la série, via /find de TMDB."""
    try:
        data = await _tmdb_get(f"/find/{tvdb_id}", {"external_source": "tvdb_id"})
    except Exception as exc:
        logger.debug("TMDB find tvdb:%s failed: %s", tvdb_id, exc)
        return None
    results = (data or {}).get("tv_results") or []
    return results[0].get("id") if results else None


async def _tmdb_get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    """Call the TMDB API."""
    if not settings.TMDB_API_KEY:
        return None

    all_params = {"api_key": settings.TMDB_API_KEY, "language": "fr-FR"}
    if params:
        all_params.update(params)

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{TMDB_BASE}{endpoint}", params=all_params)
        resp.raise_for_status()
        return resp.json()


async def _rate(db: AsyncSession, items: list[dict[str, Any]]) -> None:
    """Note IMDb des films proposés (TMDB en secours) ; jamais bloquant."""
    from app.services import ratings

    try:
        await ratings.enrich(db, items)
    except Exception as exc:  # Radarr ou base indisponible : la note TMDB reste
        logger.warning("Notes IMDb indisponibles : %s", exc)


def _format_tmdb_movie(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a TMDB movie result."""
    return {
        "tmdb_id": raw.get("id"),
        "title": raw.get("title", "Unknown"),
        "original_title": raw.get("original_title", ""),
        "type": "movie",
        "year": (raw.get("release_date") or "")[:4] or None,
        "release_date": raw.get("release_date"),
        "overview": raw.get("overview", ""),
        "rating": raw.get("vote_average"),
        "vote_count": raw.get("vote_count", 0),
        "popularity": raw.get("popularity", 0),
        "poster_url": f"{TMDB_IMG}/w342{raw['poster_path']}" if raw.get("poster_path") else None,
        "backdrop_url": f"{TMDB_IMG}/w780{raw['backdrop_path']}"
        if raw.get("backdrop_path")
        else None,
        "genre_ids": raw.get("genre_ids", []),
    }


def _format_tmdb_series(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a TMDB TV series result."""
    return {
        "tmdb_id": raw.get("id"),
        "title": raw.get("name", "Unknown"),
        "original_title": raw.get("original_name", ""),
        "type": "series",
        "year": (raw.get("first_air_date") or "")[:4] or None,
        "release_date": raw.get("first_air_date"),
        "overview": raw.get("overview", ""),
        "rating": raw.get("vote_average"),
        "vote_count": raw.get("vote_count", 0),
        "popularity": raw.get("popularity", 0),
        "poster_url": f"{TMDB_IMG}/w342{raw['poster_path']}" if raw.get("poster_path") else None,
        "backdrop_url": f"{TMDB_IMG}/w780{raw['backdrop_path']}"
        if raw.get("backdrop_path")
        else None,
        "genre_ids": raw.get("genre_ids", []),
    }


async def _history_bases(db: AsyncSession, profile_id: int, media: list[dict]) -> list[dict]:
    """Titres de la médiathèque regardés récemment par un profil (4 au plus).

    « Pour toi » d'un profil (ADR-008) : les recommandations TMDB partent
    de ce que CE profil a vu ou commencé, du plus récent au plus ancien.
    """
    from sqlalchemy import select

    from app.models.watch_state import WatchState

    rows = await db.execute(
        select(WatchState)
        .where(WatchState.profile_id == profile_id)
        .order_by(WatchState.updated_at.desc())
        .limit(200)
    )
    movies = {
        str(m.get("tmdb_id")): m for m in media if m.get("type") == "movie" and m.get("tmdb_id")
    }
    # Série : `tmdb_id` de l'agrégateur = identifiant TVDB (Sonarr), celui du vu partagé
    series = {
        str(m.get("tmdb_id")): m for m in media if m.get("type") == "series" and m.get("tmdb_id")
    }
    bases: list[dict] = []
    seen: set[str] = set()
    for row in rows.scalars():
        if not (row.watched or row.position):
            continue
        item = (movies if row.media_type == "movie" else series).get(str(row.external_id))
        key = f"{row.media_type}:{row.external_id}"
        if item is None or key in seen:
            continue
        seen.add(key)
        bases.append(item)
        if len(bases) >= 4:
            break
    return bases


@router.get("")
async def get_recommendations(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Smart recommendations based on library analysis + TMDB.

    Returns:
    - trending_movies: current trending movies
    - trending_series: current trending series
    - because_you_have: recommendations based on user library movies & series
      (for a family profile: on what this profile watched, ADR-008)
    - library_select_items: items from user library for custom recommendation selector
    - wanted: monitored but not downloaded items from library
    """

    async def _fetch():
        result: dict[str, Any] = {
            "trending_movies": [],
            "trending_series": [],
            "because_you_have": [],
            "library_select_items": [],
            "wanted": [],
            "tmdb_available": bool(settings.TMDB_API_KEY),
        }

        # 1. Fetch library for context
        media = await fetch_all_media(db)
        existing_titles = {m.get("title", "").lower() for m in media}
        # Uniquement les FILMS : pour les séries, le champ `tmdb_id` de
        # l'agrégateur contient en réalité l'ID TVDB (Sonarr) ; mélanger les
        # deux espaces d'IDs marquait à tort des films comme « déjà présents ».
        existing_tmdb_ids = {
            m.get("tmdb_id") for m in media if m.get("type") == "movie" and m.get("tmdb_id")
        }

        # Format items for user selector dropdown
        result["library_select_items"] = [
            {
                # id Radarr/Sonarr (les médias n'ont pas de clé "id")
                "id": m.get("external_id"),
                "title": m.get("title"),
                "type": m.get("type"),
                "year": m.get("year"),
                "poster_url": m.get("poster_url"),
                "tmdb_id": m.get("tmdb_id"),
                # Pour une série, `tmdb_id` est en réalité l'ID TVDB (Sonarr) :
                # le client doit appeler /based_on/…?source=tvdb.
                "id_source": "tvdb" if m.get("type") == "series" else "tmdb",
            }
            for m in media
            if m.get("title") and m.get("has_file")
        ][:50]

        # 2. Wanted (monitored, no file)
        result["wanted"] = [
            {
                "id": m.get("external_id"),  # id Radarr/Sonarr → fiche
                "title": m["title"],
                "type": m["type"],
                "year": m.get("year"),
                "poster_url": m.get("poster_url"),
                "source_service": m.get("source_service"),
                "tmdb_id": m.get("tmdb_id"),
            }
            for m in media
            if m.get("monitored") and not m.get("has_file")
        ][:20]

        if not settings.TMDB_API_KEY:
            return result

        # 3. Trending movies
        try:
            trending_movies = await _tmdb_get("/trending/movie/week")
            if trending_movies:
                for raw in trending_movies.get("results", [])[:12]:
                    item = _format_tmdb_movie(raw)
                    item["in_library"] = (
                        item["tmdb_id"] in existing_tmdb_ids
                        or item["title"].lower() in existing_titles
                    )
                    result["trending_movies"].append(item)
        except Exception as exc:
            logger.error("TMDB trending movies failed: %s", exc)

        # 4. Trending series
        try:
            trending_series = await _tmdb_get("/trending/tv/week")
            if trending_series:
                for raw in trending_series.get("results", [])[:12]:
                    item = _format_tmdb_series(raw)
                    item["in_library"] = (
                        item["tmdb_id"] in existing_tmdb_ids
                        or item["title"].lower() in existing_titles
                    )
                    result["trending_series"].append(item)
        except Exception as exc:
            logger.error("TMDB trending series failed: %s", exc)

        # 5. "Because you have X" — a profile's recent viewing first, then
        # random library movies AND series with tmdb_id to fill up to 4
        media_with_tmdb = [m for m in media if m.get("tmdb_id") and m.get("has_file")]
        sample_items = await _history_bases(db, profile_id, media) if profile_id else []
        rest = [m for m in media_with_tmdb if m not in sample_items]
        sample_items += random.sample(rest, min(4 - len(sample_items), len(rest)))
        result["based_on_history"] = bool(profile_id)

        for base_item in sample_items:
            m_type = base_item.get("type", "movie")
            formatter = _format_tmdb_movie if m_type == "movie" else _format_tmdb_series

            try:
                if m_type == "movie":
                    tmdb_endpoint = f"/movie/{base_item['tmdb_id']}/recommendations"
                else:
                    # Pour une série, `tmdb_id` contient l'ID TVDB (Sonarr) :
                    # il faut le traduire en ID TMDB, sinon TMDB renvoie les
                    # recommandations d'une tout autre série.
                    tv_id = await _tvdb_to_tmdb(base_item["tmdb_id"])
                    if not tv_id:
                        continue
                    tmdb_endpoint = f"/tv/{tv_id}/recommendations"
                recs = await _tmdb_get(tmdb_endpoint)
                if recs:
                    rec_items = []
                    for raw in recs.get("results", [])[:6]:
                        item = formatter(raw)
                        item["in_library"] = (
                            item["tmdb_id"] in existing_tmdb_ids
                            or item["title"].lower() in existing_titles
                        )
                        if not item["in_library"]:
                            rec_items.append(item)

                    if rec_items:
                        result["because_you_have"].append(
                            {
                                # id Radarr/Sonarr → lien vers la fiche du média
                                "base_id": base_item.get("external_id"),
                                "base_title": base_item["title"],
                                "base_type": m_type,
                                "base_poster": base_item.get("poster_url"),
                                "recommendations": rec_items[:4],
                            }
                        )
            except Exception as exc:
                logger.debug("TMDB recs for %s failed: %s", base_item.get("title"), exc)

        # Note la plus fiable (IMDb) à la place de celle de TMDB, pour tous les films proposés
        await _rate(
            db,
            result["trending_movies"]
            + result["trending_series"]
            + [rec for group in result["because_you_have"] for rec in group["recommendations"]],
        )
        return result

    profile_id = user.get("profile_id")
    key = "recommendations:full" if profile_id is None else f"recommendations:full:p{profile_id}"
    return await cache.get_or_set(key, _fetch, ttl_seconds=3600)


@router.get("/details/{media_type}/{tmdb_id}")
async def get_tmdb_detail(
    media_type: str,
    tmdb_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetch rich details for a TMDB movie or series for the detail modal."""
    if not settings.TMDB_API_KEY:
        raise HTTPException(status_code=400, detail="TMDB_API_KEY non configurée")

    endpoint = f"/movie/{tmdb_id}" if media_type == "movie" else f"/tv/{tmdb_id}"
    cache_key = f"tmdb_detail:{media_type}:{tmdb_id}"

    async def _fetch():
        raw = await _tmdb_get(endpoint, {"append_to_response": "credits,videos"})
        if not raw:
            raise HTTPException(status_code=404, detail="Média non trouvé sur TMDB")

        # Parse trailer
        trailer_key = None
        if "videos" in raw and "results" in raw["videos"]:
            for v in raw["videos"]["results"]:
                if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                    trailer_key = v.get("key")
                    break

        # Parse cast
        cast = []
        if "credits" in raw and "cast" in raw["credits"]:
            for c in raw["credits"]["cast"][:8]:
                cast.append(
                    {
                        "name": c.get("name"),
                        "character": c.get("character"),
                        "profile_path": f"{TMDB_IMG}/w185{c['profile_path']}"
                        if c.get("profile_path")
                        else None,
                    }
                )

        # Parse director
        director = None
        if media_type == "movie" and "credits" in raw and "crew" in raw["credits"]:
            for cr in raw["credits"]["crew"]:
                if cr.get("job") == "Director":
                    director = cr.get("name")
                    break
        elif media_type == "series" and raw.get("created_by"):
            creator_names = [c.get("name") for c in raw["created_by"] if c.get("name")]
            if creator_names:
                director = ", ".join(creator_names)

        # Genres
        genres = [g.get("name") for g in raw.get("genres", []) if g.get("name")]

        # Check library status
        media = await fetch_all_media(db)
        existing_tmdb_ids = {m.get("tmdb_id"): m for m in media if m.get("tmdb_id")}
        existing_titles = {m.get("title", "").lower(): m for m in media if m.get("title")}

        library_match = existing_tmdb_ids.get(tmdb_id) or existing_titles.get(
            (raw.get("title") or raw.get("name") or "").lower()
        )

        title = raw.get("title") or raw.get("name") or "Inconnu"
        release_date = raw.get("release_date") or raw.get("first_air_date")

        detail = {
            "tmdb_id": raw.get("id"),
            "title": title,
            "original_title": raw.get("original_title") or raw.get("original_name") or "",
            "type": media_type,
            "year": (release_date or "")[:4] or None,
            "release_date": release_date,
            "overview": raw.get("overview") or "Aucun synopsis disponible.",
            "rating": raw.get("vote_average"),
            "vote_count": raw.get("vote_count", 0),
            "popularity": raw.get("popularity", 0),
            "runtime": raw.get("runtime")
            or (raw.get("episode_run_time")[0] if raw.get("episode_run_time") else None),
            "poster_url": f"{TMDB_IMG}/w500{raw['poster_path']}"
            if raw.get("poster_path")
            else None,
            "backdrop_url": f"{TMDB_IMG}/w1280{raw['backdrop_path']}"
            if raw.get("backdrop_path")
            else None,
            "genres": genres,
            "cast": cast,
            "director": director,
            "trailer_key": trailer_key,
            "in_library": library_match is not None,
            "library_item": {
                "id": library_match.get("external_id"),
                "type": library_match.get("type"),
            }
            if library_match
            else None,
        }
        await _rate(db, [detail])
        return detail

    return await cache.get_or_set(cache_key, _fetch, ttl_seconds=3600)


@router.get("/based_on/{media_type}/{tmdb_id}")
async def get_recommendations_based_on(
    media_type: str,
    tmdb_id: int,
    source: str = Query("tmdb", description="tmdb | tvdb (séries de la bibliothèque Sonarr)"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch specific TMDB recommendations for a targeted movie or series.

    ``source=tvdb`` : l'identifiant reçu est un ID TVDB (séries Sonarr) et
    doit d'abord être traduit en ID TMDB.
    """
    if not settings.TMDB_API_KEY:
        return {"items": []}

    is_movie = media_type == "movie"
    formatter = _format_tmdb_movie if is_movie else _format_tmdb_series
    cache_key = f"recs_based_on:{media_type}:{source}:{tmdb_id}"

    async def _fetch():
        target_id: int | None = tmdb_id
        if not is_movie and source == "tvdb":
            target_id = await _tvdb_to_tmdb(tmdb_id)
            if not target_id:
                return {"items": []}
        endpoint = (
            f"/movie/{target_id}/recommendations"
            if is_movie
            else f"/tv/{target_id}/recommendations"
        )
        media = await fetch_all_media(db)
        existing_titles = {m.get("title", "").lower() for m in media}
        existing_tmdb_ids = {m.get("tmdb_id") for m in media if m.get("tmdb_id")}

        data = await _tmdb_get(endpoint)
        if not data:
            return {"items": []}

        items = []
        for raw in data.get("results", [])[:12]:
            item = formatter(raw)
            item["in_library"] = (
                item["tmdb_id"] in existing_tmdb_ids or item["title"].lower() in existing_titles
            )
            items.append(item)

        await _rate(db, items)
        return {"items": items}

    return await cache.get_or_set(cache_key, _fetch, ttl_seconds=1800)


@router.get("/discover")
async def discover_media(
    genre: str = Query(None, description="Genre name to filter"),
    media_type: str = Query("movie", description="movie or tv"),
    sort_by: str = Query("popularity.desc", description="TMDB sort field"),
    page: int = Query(1, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """Discover new media from TMDB with filters."""
    if not settings.TMDB_API_KEY:
        return {"error": "TMDB_API_KEY not configured", "items": []}

    cache_key = f"discover:{media_type}:{genre}:{sort_by}:{page}"

    async def _fetch():
        params: dict[str, Any] = {
            "sort_by": sort_by,
            "page": page,
            "include_adult": "false",
            "vote_count.gte": "50",
        }

        # Map genre name to TMDB genre ID
        if genre:
            genre_data = await _tmdb_get(f"/genre/{media_type}/list")
            if genre_data:
                genre_id = next(
                    (
                        g["id"]
                        for g in genre_data.get("genres", [])
                        if g["name"].lower() == genre.lower()
                    ),
                    None,
                )
                if genre_id:
                    params["with_genres"] = str(genre_id)

        data = await _tmdb_get(f"/discover/{media_type}", params)
        if not data:
            return {"items": [], "total": 0}

        formatter = _format_tmdb_movie if media_type == "movie" else _format_tmdb_series
        items = [formatter(raw) for raw in data.get("results", [])]
        await _rate(db, items)

        return {
            "items": items,
            "total": data.get("total_results", 0),
            "page": page,
            "total_pages": min(data.get("total_pages", 1), 10),
        }

    return await cache.get_or_set(cache_key, _fetch, ttl_seconds=1800)

"""TMDB Recommendations API — real movie/series recommendations from TMDB."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, Query
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
        "backdrop_url": f"{TMDB_IMG}/w780{raw['backdrop_path']}" if raw.get("backdrop_path") else None,
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
        "backdrop_url": f"{TMDB_IMG}/w780{raw['backdrop_path']}" if raw.get("backdrop_path") else None,
        "genre_ids": raw.get("genre_ids", []),
    }


@router.get("")
async def get_recommendations(db: AsyncSession = Depends(get_db)):
    """Smart recommendations based on library analysis + TMDB.

    Returns:
    - trending: current trending movies & series
    - because_you_have: recommendations based on random library items
    - wanted: monitored but not downloaded items from library
    - missing_collections: sequels/prequels you might be missing
    """
    async def _fetch():
        result: dict[str, Any] = {
            "trending_movies": [],
            "trending_series": [],
            "because_you_have": [],
            "wanted": [],
            "tmdb_available": bool(settings.TMDB_API_KEY),
        }

        # 1. Fetch library for context
        media = await fetch_all_media(db)
        existing_titles = {m.get("title", "").lower() for m in media}
        existing_tmdb_ids = {m.get("tmdb_id") for m in media if m.get("tmdb_id")}

        # 2. Wanted (monitored, no file)
        result["wanted"] = [
            {
                "title": m["title"],
                "type": m["type"],
                "year": m.get("year"),
                "poster_url": m.get("poster_url"),
                "source_service": m.get("source_service"),
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
                    item["in_library"] = item["title"].lower() in existing_titles
                    result["trending_series"].append(item)
        except Exception as exc:
            logger.error("TMDB trending series failed: %s", exc)

        # 5. "Because you have X" — pick random library items with tmdb_id
        import random
        movies_with_tmdb = [
            m for m in media
            if m.get("type") == "movie" and m.get("tmdb_id") and m.get("has_file")
        ]
        sample_movies = random.sample(movies_with_tmdb, min(3, len(movies_with_tmdb)))

        for base_movie in sample_movies:
            try:
                recs = await _tmdb_get(f"/movie/{base_movie['tmdb_id']}/recommendations")
                if recs:
                    rec_items = []
                    for raw in recs.get("results", [])[:6]:
                        item = _format_tmdb_movie(raw)
                        item["in_library"] = (
                            item["tmdb_id"] in existing_tmdb_ids
                            or item["title"].lower() in existing_titles
                        )
                        if not item["in_library"]:
                            rec_items.append(item)

                    if rec_items:
                        result["because_you_have"].append({
                            "base_title": base_movie["title"],
                            "base_poster": base_movie.get("poster_url"),
                            "recommendations": rec_items[:4],
                        })
            except Exception as exc:
                logger.debug("TMDB recs for %s failed: %s", base_movie.get("title"), exc)

        return result

    return await cache.get_or_set("recommendations:full", _fetch, ttl_seconds=3600)


@router.get("/discover")
async def discover_media(
    genre: str = Query(None, description="Genre name to filter"),
    media_type: str = Query("movie", description="movie or tv"),
    sort_by: str = Query("popularity.desc", description="TMDB sort field"),
    page: int = Query(1, ge=1, le=10),
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
                    (g["id"] for g in genre_data.get("genres", []) if g["name"].lower() == genre.lower()),
                    None,
                )
                if genre_id:
                    params["with_genres"] = str(genre_id)

        data = await _tmdb_get(f"/discover/{media_type}", params)
        if not data:
            return {"items": [], "total": 0}

        formatter = _format_tmdb_movie if media_type == "movie" else _format_tmdb_series
        items = [formatter(raw) for raw in data.get("results", [])]

        return {
            "items": items,
            "total": data.get("total_results", 0),
            "page": page,
            "total_pages": min(data.get("total_pages", 1), 10),
        }

    return await cache.get_or_set(cache_key, _fetch, ttl_seconds=1800)

"""People / cast filmography — cross an actor's TMDB movie credits with the
local Radarr library.

Given a TMDB person id, return the actor's info plus two lists:
- ``in_library``: their movies already in Radarr (linkable to the media detail),
- ``discover``: their other movies, not owned yet (addable via a request).
"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"


def _profile_url(path: str | None) -> str | None:
    return f"{TMDB_IMG}/w342{path}" if path else None


def _poster_url(path: str | None) -> str | None:
    return f"{TMDB_IMG}/w342{path}" if path else None


async def _radarr_library_map(db: AsyncSession) -> dict[int, dict[str, Any]]:
    """Return {tmdbId: {"radarr_id", "has_file", "title"}} for the whole
    Radarr library, so we can tell which of an actor's movies are owned."""
    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "radarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    svc = result.scalars().first()
    if not svc:
        return {}

    radarr = RadarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))
    try:
        movies = await radarr.get("/movie")
    except Exception as exc:
        logger.warning("Could not fetch Radarr library for person lookup: %s", exc)
        return {}
    finally:
        await radarr.close()

    out: dict[int, dict[str, Any]] = {}
    for m in movies if isinstance(movies, list) else []:
        tid = m.get("tmdbId")
        if tid:
            out[int(tid)] = {
                "radarr_id": m.get("id"),
                "has_file": m.get("hasFile", False),
                "title": m.get("title", ""),
            }
    return out


async def get_person_filmography(
    db: AsyncSession, person_id: int
) -> dict[str, Any]:
    """Fetch a TMDB person's movie filmography split by library ownership."""
    if not settings.TMDB_API_KEY:
        return {"error": "TMDB non configuré", "person": None, "in_library": [], "discover": []}

    params = {"api_key": settings.TMDB_API_KEY, "language": "fr-FR"}
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            person_resp, credits_resp = None, None
            person_resp = await client.get(f"{TMDB_BASE}/person/{person_id}", params=params)
            credits_resp = await client.get(
                f"{TMDB_BASE}/person/{person_id}/movie_credits", params=params
            )
        except httpx.HTTPError as exc:
            logger.warning("TMDB person fetch failed (%s): %s", person_id, exc)
            return {"error": "TMDB injoignable", "person": None, "in_library": [], "discover": []}

    if person_resp.status_code != 200:
        return {"error": "Acteur introuvable", "person": None, "in_library": [], "discover": []}

    pdata = person_resp.json()
    person = {
        "tmdb_id": person_id,
        "name": pdata.get("name", ""),
        "photo": _profile_url(pdata.get("profile_path")),
        "biography": pdata.get("biography", ""),
        "known_for": pdata.get("known_for_department", ""),
        "birthday": pdata.get("birthday"),
        "place_of_birth": pdata.get("place_of_birth"),
    }

    cast = (credits_resp.json().get("cast", []) if credits_resp.status_code == 200 else [])

    lib = await _radarr_library_map(db)

    in_library: list[dict[str, Any]] = []
    discover: list[dict[str, Any]] = []
    seen: set[int] = set()

    for m in cast:
        tid = m.get("id")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        year = (m.get("release_date") or "")[:4] or None
        base = {
            "tmdb_id": tid,
            "title": m.get("title") or m.get("original_title") or "",
            "year": int(year) if year and year.isdigit() else None,
            "character": m.get("character", ""),
            "poster": _poster_url(m.get("poster_path")),
            "vote_average": round(m.get("vote_average") or 0, 1),
            "popularity": m.get("popularity") or 0,
        }
        owned = lib.get(int(tid))
        if owned:
            in_library.append({
                **base,
                "radarr_id": owned["radarr_id"],
                "has_file": owned["has_file"],
            })
        else:
            discover.append(base)

    # In-library first, newest first; discover ranked by popularity.
    in_library.sort(key=lambda x: (x["year"] or 0), reverse=True)
    discover.sort(key=lambda x: x["popularity"], reverse=True)

    return {
        "person": person,
        "in_library": in_library,
        "discover": discover[:40],
        "counts": {
            "in_library": len(in_library),
            "discover": len(discover),
        },
    }

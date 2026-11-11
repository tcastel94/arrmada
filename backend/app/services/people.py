"""People / cast filmography — cross an actor's TMDB movie credits with the
local Radarr library.

Given a TMDB person id, return the actor's info plus two lists:
- ``in_library``: their movies already in Radarr (linkable to the media detail),
- ``discover``: their other movies, not owned yet (addable via a request).
"""

from __future__ import annotations

import time
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


# Distribution d'une série, gardée 24 h (la fiche est ouverte bien plus souvent
# qu'un casting ne change) : {id TVDB ou « tmdb:N » → (heure, distribution)}
_SERIES_CAST_TTL = 24 * 3600.0
_SERIES_CAST_MAX = 500
_series_cast: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def parse_series_cast(data: Any, limit: int = 20) -> list[dict[str, Any]]:
    """Réponse TMDB `/tv/{id}/aggregate_credits` → distribution au format des
    fiches film ([{name, character, tmdb_id, photo, order}], par ordre d'affiche)."""
    cast = []
    raw = data.get("cast") if isinstance(data, dict) else None
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict) or not c.get("name"):
            continue
        roles = [r for r in c.get("roles") or [] if isinstance(r, dict)]
        # Rôle tenu dans le plus d'épisodes (un acteur peut en avoir plusieurs)
        roles.sort(key=lambda r: r.get("episode_count") or 0, reverse=True)
        cast.append({
            "name": c["name"],
            "character": str((roles[0].get("character") if roles else c.get("character")) or ""),
            "type": "cast",
            "job": "",
            "tmdb_id": c.get("id"),
            "order": c.get("order", 999),
            "photo": _profile_url(c.get("profile_path")),
        })  # fmt: skip
    cast.sort(key=lambda p: p.get("order", 999))
    return cast[:limit]


async def get_series_cast(tvdb_id: Any, tmdb_id: Any = None) -> list[dict[str, Any]]:
    """Distribution d'une série (Sonarr n'en a pas) : TMDB, par l'ID TMDB que
    Sonarr v4 connaît, sinon retrouvé par l'ID TVDB. Vide sans clé TMDB, si
    la série est inconnue ou TMDB injoignable : la fiche s'affiche sans."""
    if not settings.TMDB_API_KEY or not (tvdb_id or tmdb_id):
        return []
    key = str(tvdb_id) if tvdb_id else f"tmdb:{tmdb_id}"
    cached = _series_cast.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _SERIES_CAST_TTL:
        return cached[1]
    params = {"api_key": settings.TMDB_API_KEY, "language": "fr-FR"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            if not tmdb_id:
                found = await client.get(
                    f"{TMDB_BASE}/find/{tvdb_id}", params={**params, "external_source": "tvdb_id"}
                )
                results = found.json().get("tv_results") or [] if found.status_code == 200 else []
                tmdb_id = results[0].get("id") if results else None
                if not tmdb_id:
                    return []
            resp = await client.get(f"{TMDB_BASE}/tv/{tmdb_id}/aggregate_credits", params=params)
            if resp.status_code != 200:
                return []
            cast = parse_series_cast(resp.json())
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("Distribution de la série %s : TMDB injoignable (%s)", key, exc)
        return []
    if len(_series_cast) >= _SERIES_CAST_MAX:
        _series_cast.clear()
    _series_cast[key] = (now, cast)
    return cast


async def _radarr_library_map(db: AsyncSession) -> dict[int, dict[str, Any]]:
    """Return {tmdbId: {"radarr_id", "has_file", "title"}} for the whole
    Radarr library, so we can tell which of an actor's movies are owned."""
    stmt = select(Service).where(
        Service.is_enabled == True,
        Service.type == "radarr",  # noqa: E712
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


async def get_person_filmography(db: AsyncSession, person_id: int) -> dict[str, Any]:
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

    cast = credits_resp.json().get("cast", []) if credits_resp.status_code == 200 else []

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
            in_library.append(
                {
                    **base,
                    "radarr_id": owned["radarr_id"],
                    "has_file": owned["has_file"],
                }
            )
        else:
            discover.append(base)

    # In-library first, newest first; discover ranked by popularity.
    in_library.sort(key=lambda x: x["year"] or 0, reverse=True)
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

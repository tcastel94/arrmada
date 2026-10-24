"""Note affichée d'un film : la plus fiable disponible.

Choix de la source (une seule note par affiche, pour pouvoir comparer) :

  1. **IMDb**, dès 1 000 votes (nombre inconnu : gardée). C'est la note la plus fiable pour un film :
     des centaines de milliers de votes par titre connu, une moyenne
     pondérée contre le « bourrage » de votes, et une échelle sur 10 que tout
     le monde sait lire. Metacritic (critiques de presse) est plus exigeant,
     mais absent pour beaucoup de films français ou anciens ; Rotten Tomatoes
     donne un % d'avis positifs, pas une note de qualité : tous deux restent
     affichés sur la fiche du film, à côté d'IMDb.
  2. À défaut, **TMDB** (base communautaire), dès 50 votes.
  3. Sinon, pas de note : mieux vaut rien qu'un 9,5 sur 4 votes.

D'où viennent les notes :
  - films de la médiathèque : dans les données de Radarr (aucun appel en plus) ;
  - films proposés (TMDB) : recherche Radarr par identifiant TMDB, une fois,
    gardée 14 jours en base (table movie_ratings). Une liste de suggestions
    ne déclenche jamais plus de MAX_LOOKUPS recherches, en 8 s au plus : les
    titres restants gardent leur note TMDB et seront complétés au passage
    suivant.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_rating import MovieRating

logger = logging.getLogger(__name__)

IMDB_MIN_VOTES = 1_000
TMDB_MIN_VOTES = 50
REFRESH_AFTER = timedelta(days=14)
MAX_LOOKUPS = 40  # recherches Radarr par liste de suggestions
PARALLEL = 6
LOOKUP_BUDGET_S = 8.0


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def from_radarr(ratings: Any) -> dict[str, Any]:
    """Bloc `ratings` de Radarr ({imdb: {value, votes}, tmdb, metacritic, rottenTomatoes})."""
    ratings = ratings if isinstance(ratings, dict) else {}

    def part(name: str) -> dict[str, Any]:
        value = ratings.get(name)
        return value if isinstance(value, dict) else {}

    def votes(name: str) -> int | None:
        # Absent (ancien Radarr) : None, « inconnu » ; présent : le compte, même 0
        raw = part(name).get("votes")
        try:
            return max(0, int(raw)) if raw is not None else None
        except (TypeError, ValueError):
            return None

    meta, rotten = _num(part("metacritic").get("value")), _num(part("rottenTomatoes").get("value"))
    return {
        "imdb": _num(part("imdb").get("value")),
        "imdb_votes": votes("imdb"),
        "metacritic": int(meta) if meta else None,
        "rotten_tomatoes": int(rotten) if rotten else None,
        "tmdb": _num(part("tmdb").get("value")),
        "tmdb_votes": votes("tmdb"),
    }


def best(scores: dict[str, Any]) -> dict[str, Any]:
    """{rating, rating_source, rating_votes} selon l'ordre IMDb → TMDB → rien."""
    # Nombre de votes inconnu (None, ancien Radarr) : la note est gardée ; seul un
    # nombre CONNU et trop petit l'écarte
    imdb, imdb_votes = scores.get("imdb"), scores.get("imdb_votes")
    if imdb and (imdb_votes is None or imdb_votes >= IMDB_MIN_VOTES):
        return {"rating": round(imdb, 1), "rating_source": "imdb", "rating_votes": imdb_votes}
    tmdb, tmdb_votes = scores.get("tmdb"), scores.get("tmdb_votes")
    if tmdb and (tmdb_votes is None or tmdb_votes >= TMDB_MIN_VOTES):
        return {"rating": round(tmdb, 1), "rating_source": "tmdb", "rating_votes": tmdb_votes}
    return {"rating": None, "rating_source": None, "rating_votes": None}


def _row_scores(row: MovieRating) -> dict[str, Any]:
    return {
        "imdb": row.imdb,
        "imdb_votes": row.imdb_votes,
        "metacritic": row.metacritic,
        "rotten_tomatoes": row.rotten_tomatoes,
        "tmdb": row.tmdb,
        "tmdb_votes": row.tmdb_votes,
    }


def _fresh(row: MovieRating, now: datetime) -> bool:
    fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=UTC)
    return now - fetched < REFRESH_AFTER


async def _lookup_many(db: AsyncSession, tmdb_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Notes Radarr de films absents de la médiathèque ({} si Radarr est absent ou lent)."""
    from app.services.kodi import _get_radarr_client

    radarr = await _get_radarr_client(db)
    if radarr is None or not tmdb_ids:
        return {}
    found: dict[int, dict[str, Any]] = {}
    gate = asyncio.Semaphore(PARALLEL)

    async def one(tmdb_id: int) -> None:
        async with gate:
            try:
                results = await radarr.lookup_movie(f"tmdb:{tmdb_id}")
            except Exception as exc:  # un film introuvable n'arrête pas les autres
                logger.debug("Note IMDb de tmdb:%s : %s", tmdb_id, exc)
                return
        movie = next(
            (m for m in results or [] if isinstance(m, dict) and m.get("tmdbId") == tmdb_id),
            None,
        )
        if movie is not None:
            found[tmdb_id] = from_radarr(movie.get("ratings"))

    try:
        await asyncio.wait_for(asyncio.gather(*(one(i) for i in tmdb_ids)), timeout=LOOKUP_BUDGET_S)
    except TimeoutError:
        logger.info("Notes IMDb : %d/%d films complétés (délai atteint)", len(found), len(tmdb_ids))
    finally:
        await radarr.close()
    return found


async def scores_for(db: AsyncSession, tmdb_ids: list[int]) -> dict[int, dict[str, Any]]:
    """Notes de films proposés : base d'abord, Radarr pour les manquantes ou anciennes."""
    ids = sorted({int(i) for i in tmdb_ids if i})
    if not ids:
        return {}
    now = datetime.now(UTC)
    rows = {
        row.tmdb_id: row
        for row in (await db.execute(select(MovieRating).where(MovieRating.tmdb_id.in_(ids))))
        .scalars()
        .all()
    }
    scores = {tmdb_id: _row_scores(row) for tmdb_id, row in rows.items()}
    missing = [i for i in ids if i not in rows or not _fresh(rows[i], now)][:MAX_LOOKUPS]
    fetched = await _lookup_many(db, missing)
    for tmdb_id, found in fetched.items():
        row = rows.get(tmdb_id)
        if row is None:
            row = MovieRating(tmdb_id=tmdb_id, fetched_at=now)
            db.add(row)
        for field, value in found.items():
            setattr(row, field, value)
        row.fetched_at = now
        scores[tmdb_id] = found
    if fetched:
        try:
            await db.commit()
        except Exception as exc:  # deux listes calculées en même temps : la note reste affichée
            await db.rollback()
            logger.debug("Notes IMDb non enregistrées : %s", exc)
    return scores


async def enrich(db: AsyncSession, items: list[dict[str, Any]]) -> None:
    """Remplace la note TMDB des films proposés par la note la plus fiable (sur place).

    `items` : films au format des suggestions ({tmdb_id, type, rating,
    vote_count}). Les séries gardent leur note TMDB (pas d'équivalent IMDb
    fiable côté Sonarr).
    """
    movies = [i for i in items if i.get("type") == "movie" and i.get("tmdb_id")]
    scores = await scores_for(db, [m["tmdb_id"] for m in movies]) if movies else {}
    for item in items:
        own = {"tmdb": _num(item.get("rating")), "tmdb_votes": item.get("vote_count")}
        if item.get("type") == "movie":
            found = scores.get(int(item["tmdb_id"])) if item.get("tmdb_id") else None
            if found:
                # TMDB à jour vient de la liste elle-même ; le reste de Radarr
                own = {**found, "tmdb": own["tmdb"] or found.get("tmdb"),
                       "tmdb_votes": own["tmdb_votes"] if own["tmdb_votes"] is not None
                       else found.get("tmdb_votes")}  # fmt: skip
        item.update(best(own))
        if item.get("type") == "movie":
            item["metacritic"] = own.get("metacritic")
            item["rotten_tomatoes"] = own.get("rotten_tomatoes")

"""Synopsis en français : TMDB (`language=fr-FR`), anglais en secours.

D'où venait l'anglais : la médiathèque et les fiches reprennent le résumé de
Radarr (réglé sur « English » pour les infos des films) et de Sonarr (qui ne
connaît que l'anglais). Changer la langue de Radarr traduirait aussi les
titres, donc les noms de dossiers au prochain renommage : on ne touche pas à
Radarr, on traduit ici.

Fonctionnement, comme les artworks :
  - le résumé français de chaque titre est demandé UNE fois à TMDB puis gardé
    en base (table media_translations), redemandé au bout de 30 jours (7 si
    TMDB n'avait pas de traduction, 1 h après une panne) ;
  - la médiathèque (accueil, grilles, Ma liste, web app) lit la base, sans
    appel réseau ; une tâche planifiée remplit les titres manquants ;
  - la fiche d'un film ou d'une série demande TMDB tout de suite si le titre
    n'est pas encore en base (première ouverture : 1 appel, 4 s au plus).
Pas de traduction française chez TMDB (résumé vide) : on garde l'anglais.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.translation import MediaTranslation
from app.utils.logger import get_logger

logger = get_logger(__name__)

TMDB_URL = "https://api.themoviedb.org/3"
LANGUAGE = "fr-FR"

# Base utilisée par la lecture de la médiathèque et la tâche planifiée
# (remplacée par celle des tests)
session_factory = async_session_factory

REFRESH_OK = timedelta(days=30)
REFRESH_EMPTY = timedelta(days=7)  # TMDB n'avait pas (encore) de traduction
REFRESH_ERROR = timedelta(hours=1)
CONCURRENCY = 4
DETAIL_TIMEOUT = 4.0  # s : ouverture d'une fiche, jamais bloquée plus longtemps


def translation_key(media_type: str, provider_id: Any) -> str:
    """« movie:438631 » (TMDB) / « series:280619 » (TVDB), comme les artworks."""
    return f"{media_type}:{int(provider_id)}"


def pick(french: str | None, fallback: str | None) -> str:
    """Résumé affiché : le français s'il existe, sinon celui de Radarr / Sonarr."""
    text = (french or "").strip()
    return text or (fallback or "")


def parse_overview(data: Any) -> str:
    """Réponse TMDB `/movie/{id}` ou `/tv/{id}` → résumé (vide sans traduction)."""
    if not isinstance(data, dict):
        return ""
    overview = data.get("overview")
    return overview.strip() if isinstance(overview, str) else ""


def needs_refresh(row: MediaTranslation | None, now: datetime) -> bool:
    if row is None:
        return True
    fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=UTC)
    return now - fetched >= (REFRESH_OK if row.overview else REFRESH_EMPTY)


async def fetch_overview(client: httpx.AsyncClient, media_type: str, tmdb_id: int) -> str | None:
    """Résumé français d'un titre chez TMDB ; None si TMDB ne répond pas."""
    kind = "movie" if media_type == "movie" else "tv"
    try:
        response = await client.get(
            f"{TMDB_URL}/{kind}/{tmdb_id}",
            params={"api_key": settings.TMDB_API_KEY, "language": LANGUAGE},
        )
    except httpx.HTTPError as exc:
        logger.debug("TMDB %s %s : %s", kind, tmdb_id, exc)
        return None
    if response.status_code == 404:
        return ""  # inconnu de TMDB : rien à traduire
    if response.status_code != 200:
        return None
    try:
        return parse_overview(response.json())
    except ValueError:
        return None


async def _upsert(db: AsyncSession, values: list[dict[str, Any]]) -> None:
    """INSERT … ON CONFLICT (key) DO UPDATE, PostgreSQL comme SQLite."""
    if not values:
        return
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(MediaTranslation).values(values)
    updated = {c: stmt.excluded[c] for c in values[0] if c != "key"}
    await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_=updated))
    await db.commit()


def _values(media_type: str, provider_id: int, overview: str, now: datetime) -> dict[str, Any]:
    return {
        "key": translation_key(media_type, provider_id),
        "media_type": media_type,
        "provider_id": int(provider_id),
        "overview": overview,
        "fetched_at": now,
    }


# ── Lecture : médiathèque et fiches ─────────────────────────────────────────


async def apply_to_library(items: list[dict[str, Any]]) -> None:
    """Remplace le résumé anglais des titres de la médiathèque (sur place, sans réseau).

    Session à part, comme les artworks : la médiathèque est parfois calculée
    en parallèle d'autres lectures sur la session de l'appelant.
    """
    try:
        async with session_factory() as db:
            rows = {
                row.key: row.overview
                for row in (await db.execute(select(MediaTranslation))).scalars().all()
                if row.overview
            }
    except Exception as exc:  # jamais bloquant pour la médiathèque
        logger.debug("Synopsis français indisponibles : %s", exc)
        return
    if not rows:
        return
    for item in items:
        media_type = item.get("type")
        provider_id = item.get("tmdb_id")  # séries : TVDB (convention media_aggregator)
        if media_type not in ("movie", "series") or not str(provider_id or "").isdigit():
            continue
        french = rows.get(translation_key(media_type, provider_id))
        if french:
            item["overview"] = french


async def detail_overview(
    db: AsyncSession,
    media_type: str,
    provider_id: Any,
    tmdb_id: Any,
    fallback: str | None,
) -> str:
    """Résumé d'une fiche : base, sinon TMDB tout de suite (puis gardé), sinon l'anglais."""
    if not str(provider_id or "").isdigit():
        return fallback or ""
    key = translation_key(media_type, provider_id)
    now = datetime.now(UTC)
    try:
        row = (
            await db.execute(select(MediaTranslation).where(MediaTranslation.key == key))
        ).scalar_one_or_none()
    except Exception as exc:
        logger.debug("Synopsis français indisponible (%s) : %s", key, exc)
        return fallback or ""
    if not needs_refresh(row, now) or not settings.TMDB_API_KEY or not str(tmdb_id or "").isdigit():
        return pick(row.overview if row else None, fallback)

    async with httpx.AsyncClient(timeout=DETAIL_TIMEOUT) as client:
        french = await fetch_overview(client, media_type, int(tmdb_id))
    if french is None:  # TMDB en panne : l'ancienne traduction, sinon l'anglais
        return pick(row.overview if row else None, fallback)
    try:
        await _upsert(db, [_values(media_type, int(provider_id), french, now)])
    except Exception as exc:  # deux fiches ouvertes en même temps : affichée quand même
        await db.rollback()
        logger.debug("Synopsis français non enregistré (%s) : %s", key, exc)
    return pick(french, fallback)


# ── Remplissage de toute la médiathèque (tâche planifiée) ───────────────────


def library_targets(library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Titres à traduire : films (TMDB) et séries (TVDB + TMDB connu de Sonarr)."""
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in library:
        media_type = item.get("type")
        provider_id = item.get("tmdb_id")
        tmdb_id = provider_id if media_type == "movie" else item.get("tmdb_tv_id")
        if media_type not in ("movie", "series") or not str(provider_id or "").isdigit():
            continue
        if not str(tmdb_id or "").isdigit():
            continue  # série sans identifiant TMDB : pas de traduction possible
        key = translation_key(media_type, provider_id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {"media_type": media_type, "provider_id": int(provider_id), "tmdb_id": int(tmdb_id)}
        )
    return targets


async def fill(db: AsyncSession, targets: list[dict[str, Any]]) -> dict[str, int]:
    """Demande à TMDB les titres jamais traduits ou trop anciens ; renvoie les compteurs."""
    counts = {"total": 0, "french": 0, "errors": 0}
    if not settings.TMDB_API_KEY or not targets:
        return counts
    now = datetime.now(UTC)
    rows = {row.key: row for row in (await db.execute(select(MediaTranslation))).scalars().all()}
    todo = [
        t
        for t in targets
        if needs_refresh(rows.get(translation_key(t["media_type"], t["provider_id"])), now)
    ]
    if not todo:
        return counts
    gate = asyncio.Semaphore(CONCURRENCY)
    values: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=15) as client:

        async def one(target: dict[str, Any]) -> None:
            async with gate:
                french = await fetch_overview(client, target["media_type"], target["tmdb_id"])
            counts["total"] += 1
            if french is None:
                counts["errors"] += 1
                # Panne : on retentera dans 1 h, l'ancienne traduction reste affichée
                old = rows.get(translation_key(target["media_type"], target["provider_id"]))
                retry_at = (
                    now - (REFRESH_OK if old and old.overview else REFRESH_EMPTY) + REFRESH_ERROR
                )
                values.append(
                    _values(
                        target["media_type"],
                        target["provider_id"],
                        old.overview if old else "",
                        retry_at,
                    )
                )
                return
            if french:
                counts["french"] += 1
            values.append(_values(target["media_type"], target["provider_id"], french, now))

        await asyncio.gather(*(one(t) for t in todo))

    # Par paquets : une grosse médiathèque d'un coup dépasserait la limite de
    # paramètres d'une requête SQLite
    for start in range(0, len(values), 200):
        await _upsert(db, values[start : start + 200])
    return counts


def _invalidate_library_cache() -> None:
    from app.utils.cache import cache

    cache.invalidate("media:all")


async def refresh_library() -> dict[str, int]:
    """Toute la médiathèque : appelée par la tâche planifiée."""
    from app.services import media_aggregator

    try:
        async with session_factory() as db:
            library = await media_aggregator.fetch_all_media(db)
            counts = await fill(db, library_targets(library))
    except Exception as exc:
        logger.error("Synopsis français : passage interrompu : %s", exc)
        return {"total": 0, "french": 0, "errors": 1}
    if counts["total"]:
        _invalidate_library_cache()
        logger.info(
            "Synopsis français : %d titre(s) traduit(s) sur %d demandé(s)%s",
            counts["french"],
            counts["total"],
            f", {counts['errors']} en échec" if counts["errors"] else "",
        )
    return counts

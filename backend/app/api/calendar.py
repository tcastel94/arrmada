"""Calendar API — upcoming (and past) episodes and movies from Sonarr/Radarr.

Fenêtre de dates
----------------
Historiquement la route ne savait renvoyer que « aujourd'hui → +N jours »
(N ≤ 90) : le calendrier du frontend affichait donc des mois passés vides.
On accepte désormais `start` / `end` (YYYY-MM-DD) pour charger n'importe quel
mois, tout en gardant `days` pour la compatibilité (dashboard : ?days=14).

Autres corrections :
  • Sonarr ne renvoie l'objet `series` du calendrier que si on demande
    `includeSeries=true` — sans ça tous les épisodes s'appelaient « Unknown »
    et n'avaient pas d'affiche.
  • Radarr : on choisit la date de sortie (cinéma / numérique / physique) qui
    tombe DANS la fenêtre demandée, et on indique laquelle (`release_type`).
  • `unmonitored=true` (optionnel) inclut les éléments non surveillés, pour
    le filtre « surveillés seulement » du frontend. Par défaut : inchangé.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/calendar",
    tags=["calendar"],
    dependencies=[Depends(get_current_user)],
)

# Garde-fou : une fenêtre trop large ferait remonter des milliers d'épisodes
# (et des appels *arr très lents). Un mois affiché + semaines débordantes +
# marge de fuseau horaire tient largement dans 62 jours.
MAX_SPAN_DAYS = 120

# Ordre de préférence des dates de sortie Radarr (la plus « utile » d'abord :
# la sortie numérique est celle qui déclenche réellement un téléchargement).
_RADARR_RELEASES: tuple[tuple[str, str], ...] = (
    ("digital", "digitalRelease"),
    ("physical", "physicalRelease"),
    ("cinema", "inCinemas"),
)


def _parse_day(value: str, field: str) -> date:
    """Parse « YYYY-MM-DD » (ou un ISO complet dont on garde la date)."""
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Date « {field} » invalide : {value!r}") from exc


def _resolve_window(start: str | None, end: str | None, days: int) -> tuple[str, str]:
    """Calcule la fenêtre [start, end] à interroger.

    - ni start ni end : aujourd'hui (UTC) → +days  (comportement historique)
    - start seul      : start → start + days
    - end seul        : end - days → end
    - les deux        : tels quels (bornés à MAX_SPAN_DAYS, et remis dans
                        l'ordre si inversés)
    """
    if start:
        d_start = _parse_day(start, "start")
    elif end:
        d_start = _parse_day(end, "end") - timedelta(days=days)
    else:
        d_start = datetime.now(UTC).date()

    d_end = _parse_day(end, "end") if end else d_start + timedelta(days=days)

    if d_end < d_start:
        d_start, d_end = d_end, d_start
    if (d_end - d_start).days > MAX_SPAN_DAYS:
        d_end = d_start + timedelta(days=MAX_SPAN_DAYS)

    return d_start.isoformat(), d_end.isoformat()


def _pick_radarr_release(movie: dict[str, Any], start: str, end: str) -> tuple[str | None, str | None]:
    """Choisit la date de sortie à afficher pour un film.

    Radarr renvoie un film dès qu'UNE de ses dates tombe dans la fenêtre.
    Avant, on prenait toujours la sortie numérique en priorité — même si
    c'était la sortie cinéma qui tombait dans le mois affiché : le film
    apparaissait alors à une date hors de la grille. On privilégie donc la
    date incluse dans [start, end], puis on retombe sur l'ordre habituel.
    """
    candidates = [(kind, movie.get(field)) for kind, field in _RADARR_RELEASES if movie.get(field)]
    for kind, value in candidates:
        if start <= str(value)[:10] <= end:
            return value, kind
    if candidates:
        return candidates[0][1], candidates[0][0]
    return None, None


async def _fetch_calendar_data(
    db: AsyncSession, start: str, end: str, unmonitored: bool = False
) -> list[dict[str, Any]]:
    """Fetch calendar entries from all Sonarr/Radarr instances."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    entries: list[dict[str, Any]] = []
    unmonitored_param = "true" if unmonitored else "false"

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
                try:
                    # includeSeries=true : indispensable pour avoir le titre
                    # et l'affiche de la série dans chaque épisode.
                    episodes = await client.get(
                        "/calendar",
                        params={
                            "start": start,
                            "end": end,
                            "unmonitored": unmonitored_param,
                            "includeSeries": "true",
                        },
                    )
                    for ep in episodes or []:
                        series = ep.get("series") or {}
                        series_title = series.get("title") or "Série inconnue"
                        images = series.get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )
                        entries.append({
                            "id": f"sonarr-{ep.get('id')}",
                            "title": series_title,
                            "subtitle": ep.get("title", ""),
                            "type": "episode",
                            "season": ep.get("seasonNumber"),
                            "episode": ep.get("episodeNumber"),
                            "label": f"S{ep.get('seasonNumber') or 0:02d}E{ep.get('episodeNumber') or 0:02d}",
                            # airDateUtc = date + heure de diffusion en UTC :
                            # le frontend la convertit en heure locale.
                            "air_date": ep.get("airDateUtc") or ep.get("airDate"),
                            "has_file": ep.get("hasFile", False),
                            "monitored": ep.get("monitored", False),
                            "poster_url": poster,
                            "overview": ep.get("overview", ""),
                            "service": svc.name,
                            "service_type": "sonarr",
                            "series_id": ep.get("seriesId"),
                            "network": series.get("network"),
                        })
                finally:
                    await client.close()

            elif svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
                try:
                    movies = await client.get(
                        "/calendar",
                        params={"start": start, "end": end, "unmonitored": unmonitored_param},
                    )
                    for movie in movies or []:
                        images = movie.get("images", [])
                        poster = next(
                            (img.get("remoteUrl") for img in images if img.get("coverType") == "poster" and img.get("remoteUrl")),
                            None,
                        )
                        release_date, release_type = _pick_radarr_release(movie, start, end)
                        entries.append({
                            "id": f"radarr-{movie.get('id')}",
                            "title": movie.get("title", "Film inconnu"),
                            "subtitle": "",
                            "type": "movie",
                            "season": None,
                            "episode": None,
                            "label": str(movie.get("year", "")),
                            "air_date": release_date,
                            # digital | physical | cinema → badge côté frontend
                            "release_type": release_type,
                            "has_file": movie.get("hasFile", False),
                            "monitored": movie.get("monitored", False),
                            "poster_url": poster,
                            "overview": movie.get("overview", ""),
                            "service": svc.name,
                            "service_type": "radarr",
                            "movie_id": movie.get("id"),
                            "genres": movie.get("genres", []),
                        })
                finally:
                    await client.close()

        except Exception as exc:
            logger.error("Calendar fetch failed for %s: %s", svc.name, exc)

    # Sort by air date
    entries.sort(key=lambda e: e.get("air_date") or "9999")

    return entries


@router.get("")
async def get_calendar(
    start: str | None = Query(None, description="Date de début YYYY-MM-DD (optionnelle)"),
    end: str | None = Query(None, description="Date de fin YYYY-MM-DD (optionnelle)"),
    days: int = Query(30, ge=1, le=90, description="Nombre de jours si start/end ne sont pas tous deux fournis"),
    unmonitored: bool = Query(False, description="Inclure les épisodes / films non surveillés"),
    db: AsyncSession = Depends(get_db),
):
    """Fetch calendar events from Sonarr and Radarr.

    Returns episodes and movie releases within the date range.
    """
    start, end = _resolve_window(start, end, days)

    cache_key = f"calendar:{start}:{end}:{'all' if unmonitored else 'monitored'}"

    async def _fetch():
        return await _fetch_calendar_data(db, start, end, unmonitored)

    data = await cache.get_or_set(cache_key, _fetch, ttl_seconds=300)

    # Regroupement par jour (UTC) conservé pour la compatibilité ; le
    # frontend du calendrier regroupe lui-même en heure LOCALE.
    by_date: dict[str, list] = {}
    for entry in data:
        air_date = (entry.get("air_date") or "")[:10]  # YYYY-MM-DD
        by_date.setdefault(air_date, []).append(entry)

    return {
        "start": start,
        "end": end,
        "total": len(data),
        "items": data,
        "by_date": by_date,
    }

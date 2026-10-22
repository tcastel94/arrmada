"""Séries maison (Naruto Kai, One Pace…) : un dossier vidéo vu comme une série.

Appareils : liste (grille Séries), détail (écran Série), index des épisodes
(rangée Reprendre). Web app : déclarer / modifier / retirer, recherche TMDB
de la série officielle dont on emprunte l'affiche. Voir services/local_series.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.config import settings
from app.models.local_series import LocalSeries
from app.models.video_root import VideoRoot
from app.services import local_series as scanner
from app.services import video_files
from app.services.video_files import NotFound, Root
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/videos/series", tags=["videos"], dependencies=[Depends(get_current_user)]
)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"
MAX_SERIES = 100

# Scans en cache : série → (empreinte du dossier, résultat)
_scans: dict[int, tuple[tuple, scanner.Scan]] = {}


# ─── Outils ──────────────────────────────────────────────────────────────────


async def _series_with_roots(db: AsyncSession) -> list[tuple[LocalSeries, Root | None]]:
    roots = {
        r.id: Root(r.id, r.name, r.path) for r in (await db.execute(select(VideoRoot))).scalars()
    }
    rows = (await db.execute(select(LocalSeries).order_by(LocalSeries.title))).scalars()
    return [(s, roots.get(s.root_id)) for s in rows]


def _scan(series: LocalSeries, root: Root | None) -> scanner.Scan | None:
    """Saisons et épisodes (refait seulement si le dossier a changé) ; None si dossier absent."""
    if root is None:
        return None
    try:
        _, real, relative = video_files.resolve(
            {root.id: root}, video_files.encode_token(root.id, series.path)
        )
    except NotFound:
        return None
    if not real.is_dir():
        return None
    stamp = scanner.signature(real)
    cached = _scans.get(series.id)
    if cached and cached[0] == stamp:
        return cached[1]
    result = scanner.scan(root, real, relative, series.title)
    _scans[series.id] = (stamp, result)
    return result


def _summary(series: LocalSeries, scan: scanner.Scan | None) -> dict[str, Any]:
    """Une carte de la grille Séries (même champs que la médiathèque)."""
    episodes = sum(len(s.episodes) for s in scan.seasons) if scan else 0
    return {
        "id": series.id,
        "title": series.title,
        "badge": series.badge,
        "year": series.year or (scan.year if scan else None),
        "overview": series.overview or (scan.overview if scan else None),
        # Images posées dans le dossier d'abord (choix de l'utilisateur), sinon TMDB
        "poster_url": scanner.image_url(scan.poster if scan else None) or series.poster_url,
        "fanart_url": scanner.image_url(scan.fanart if scan else None) or series.fanart_url,
        "added": series.created_at.isoformat() if series.created_at else None,
        "seasons": len(scan.seasons) if scan else 0,
        "episodes": episodes,
        "available": scan is not None,
        "root_id": series.root_id,
        "path": series.path,
        "tmdb_id": series.tmdb_id,
    }


def _detail(series: LocalSeries, scan: scanner.Scan) -> dict[str, Any]:
    return {
        **_summary(series, scan),
        "seasons": [
            {
                "season_number": season.number,
                "name": season.name,
                "episodes": [
                    {
                        "season_number": ep.season,
                        "episode_number": ep.number,
                        "title": ep.title,
                        "overview": ep.overview,
                        "air_date": ep.aired,
                        "token": ep.token,
                        "watch_id": ep.watch_id,
                        "image": scanner.image_url(ep.image),
                    }
                    for ep in season.episodes
                ],
            }
            for season in scan.seasons
        ],
    }


async def _tmdb(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    if not settings.TMDB_API_KEY:
        return None
    query = {"api_key": settings.TMDB_API_KEY, "language": "fr-FR", **(params or {})}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{TMDB_BASE}{endpoint}", params=query)
        response.raise_for_status()
        return response.json()


async def _apply_tmdb(series: LocalSeries, tmdb_id: int | None) -> None:
    """Affiche, fond, résumé et année de la série officielle (Naruto pour Naruto Kai)."""
    series.tmdb_id = tmdb_id
    if not tmdb_id:
        return
    try:
        raw = await _tmdb(f"/tv/{tmdb_id}") or {}
    except httpx.HTTPError as exc:
        logger.warning("Série maison : TMDB /tv/%s injoignable (%s)", tmdb_id, exc)
        return
    if raw.get("poster_path"):
        series.poster_url = f"{TMDB_IMG}/w500{raw['poster_path']}"
    if raw.get("backdrop_path"):
        series.fanart_url = f"{TMDB_IMG}/w1280{raw['backdrop_path']}"
    series.overview = raw.get("overview") or series.overview
    year = (raw.get("first_air_date") or "")[:4]
    series.year = int(year) if year.isdigit() else series.year


async def _checked_folder(db: AsyncSession, root_id: Any, path: Any) -> tuple[int, str]:
    """(dossier racine, chemin relatif propre) d'un dossier existant, sinon 422."""
    try:
        root_id = int(root_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Dossier vidéo à choisir") from exc
    root = await db.get(VideoRoot, root_id)
    if root is None:
        raise HTTPException(status_code=422, detail="Dossier vidéo inconnu")
    relative = str(path or "").strip().strip("/")
    try:
        _, real, clean = video_files.resolve(
            {root.id: Root(root.id, root.name, root.path)},
            video_files.encode_token(root.id, relative),
        )
    except NotFound as exc:
        raise HTTPException(
            status_code=422, detail=f"Sous-dossier introuvable : {relative or '/'}"
        ) from exc
    if not real.is_dir():
        raise HTTPException(status_code=422, detail="Ce chemin n'est pas un dossier")
    return root.id, clean


# ─── Appareils (et web app) ──────────────────────────────────────────────────


@router.get("")
async def list_series(db: AsyncSession = Depends(get_db)) -> dict:
    """Séries maison pour la grille Séries."""
    return {"items": [_summary(s, _scan(s, root)) for s, root in await _series_with_roots(db)]}


@router.get("/index")
async def episode_index(db: AsyncSession = Depends(get_db)) -> dict:
    """Empreinte de chaque épisode → série, saison, épisode, jeton (rangée Reprendre de l'appli)."""
    items = []
    for series, root in await _series_with_roots(db):
        scan = _scan(series, root)
        for season in scan.seasons if scan else []:
            for ep in season.episodes:
                items.append(
                    {
                        "watch_id": ep.watch_id,
                        "series_id": series.id,
                        "season": ep.season,
                        "episode": ep.number,
                        "title": ep.title,
                        "token": ep.token,
                    }
                )
    return {"items": items}


@router.get("/tmdb/search", dependencies=[Depends(require_admin)])
async def tmdb_search(q: str = Query(..., min_length=2, max_length=100)) -> dict:
    """Séries TMDB pour choisir l'affiche d'une série maison (web app)."""
    if not settings.TMDB_API_KEY:
        raise HTTPException(status_code=400, detail="Clé TMDB absente des réglages du serveur")
    try:
        data = await _tmdb("/search/tv", {"query": q}) or {}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"TMDB injoignable : {exc}") from exc
    return {
        "items": [
            {
                "tmdb_id": r.get("id"),
                "title": r.get("name") or "",
                "year": (r.get("first_air_date") or "")[:4] or None,
                "poster_url": f"{TMDB_IMG}/w185{r['poster_path']}"
                if r.get("poster_path")
                else None,
            }
            for r in (data.get("results") or [])[:10]
        ]
    }


@router.get("/{series_id}")
async def series_detail(series_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Écran Série : saisons (arcs) et épisodes."""
    series = await db.get(LocalSeries, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Série inconnue")
    root_row = await db.get(VideoRoot, series.root_id)
    root = Root(root_row.id, root_row.name, root_row.path) if root_row else None
    scan = _scan(series, root)
    if scan is None:
        raise HTTPException(status_code=404, detail="Dossier de la série introuvable sur le NAS")
    return _detail(series, scan)


# ─── Web app ─────────────────────────────────────────────────────────────────


def _clean_title(value: Any) -> str:
    title = str(value or "").strip()[:120]
    if not title:
        raise HTTPException(status_code=422, detail="Nom de la série obligatoire")
    return title


def _clean_badge(value: Any) -> str:
    return str(value if value is not None else "Kai").strip()[:20]


def _tmdb_id(value: Any) -> int | None:
    if value in (None, "", 0):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Identifiant TMDB invalide") from exc


@router.post("", dependencies=[Depends(require_admin)])
async def create_series(data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    data = data or {}
    root_id, path = await _checked_folder(db, data.get("root_id"), data.get("path"))
    existing = (await db.execute(select(LocalSeries))).scalars().all()
    if len(existing) >= MAX_SERIES:
        raise HTTPException(status_code=422, detail=f"{MAX_SERIES} séries maison au plus")
    if any(s.root_id == root_id and s.path == path for s in existing):
        raise HTTPException(status_code=409, detail="Ce dossier est déjà une série maison")
    series = LocalSeries(
        root_id=root_id,
        path=path,
        title=_clean_title(data.get("title")),
        badge=_clean_badge(data.get("badge")),
        created_at=datetime.now(UTC),
    )
    await _apply_tmdb(series, _tmdb_id(data.get("tmdb_id")))
    db.add(series)
    await db.commit()
    await db.refresh(series)
    root = await db.get(VideoRoot, root_id)
    return _summary(series, _scan(series, Root(root.id, root.name, root.path)))


@router.patch("/{series_id}", dependencies=[Depends(require_admin)])
async def update_series(series_id: int, data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    series = await db.get(LocalSeries, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Série inconnue")
    data = data or {}
    if "title" in data:
        series.title = _clean_title(data["title"])
    if "badge" in data:
        series.badge = _clean_badge(data["badge"])
    if "root_id" in data or "path" in data:
        series.root_id, series.path = await _checked_folder(
            db, data.get("root_id", series.root_id), data.get("path", series.path)
        )
    if "tmdb_id" in data:
        tmdb_id = _tmdb_id(data["tmdb_id"])
        if not tmdb_id:
            series.poster_url = series.fanart_url = None
        await _apply_tmdb(series, tmdb_id)
    await db.commit()
    _scans.pop(series.id, None)
    root = await db.get(VideoRoot, series.root_id)
    return _summary(series, _scan(series, Root(root.id, root.name, root.path) if root else None))


@router.delete("/{series_id}", dependencies=[Depends(require_admin)])
async def delete_series(series_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Retire la série de la grille (les vidéos restent dans l'écran Vidéos et sur le disque)."""
    series = await db.get(LocalSeries, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Série inconnue")
    await db.delete(series)
    await db.commit()
    _scans.pop(series_id, None)
    return {"status": "ok"}

"""Subtitles API — Bazarr integration (status, auto/interactive download).

Exposes Bazarr subtitle management to the frontend:
- a library-wide status aggregate (which media have / miss subtitles in a
  given language) used for the media-grid badges and filter,
- one-click automatic download (Bazarr picks the best subtitle),
- interactive provider search + download of a specific subtitle,
- deletion of an existing subtitle file.

Identity keys line up with the rest of Arrmada: a movie is addressed by its
Radarr id (== Bazarr ``radarrId`` == the media-detail ``id``), a series by its
Sonarr id (== Bazarr ``sonarrSeriesId``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.bazarr import BazarrClient
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/subtitles",
    tags=["subtitles"],
    dependencies=[Depends(get_current_user)],
)

DEFAULT_LANGUAGE = "fr"


# ── Helpers ───────────────────────────────────────────────────
async def _get_bazarr(db: AsyncSession) -> BazarrClient:
    """Return a configured Bazarr client, or raise 503 if none enabled."""
    stmt = select(Service).where(
        Service.is_enabled == True, Service.type == "bazarr"  # noqa: E712
    )
    result = await db.execute(stmt)
    svc = result.scalars().first()
    if not svc:
        raise HTTPException(status_code=503, detail="Bazarr n'est pas configuré")
    return BazarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))


def _has_lang(subs: list[dict[str, Any]], code2: str) -> bool:
    return any((s or {}).get("code2") == code2 for s in subs or [])


# ── Library-wide status aggregate ─────────────────────────────
@router.get("/status")
async def subtitle_status(
    language: str = Query(DEFAULT_LANGUAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Per-media subtitle status for *language*, keyed by Radarr/Sonarr id.

    Returns::

        {
          "language": "fr",
          "available": true,
          "movies": { "<radarrId>": "present" | "missing" },
          "series": { "<sonarrSeriesId>": {"state": ..., "missing_episodes": n} }
        }

    ``present`` means Bazarr has a subtitle in that language; ``missing`` means
    Bazarr wants one (per its language profile) but has none. Media absent from
    both maps simply have no opinion (e.g. language not in their profile).
    Cached 120s; invalidated when a download/delete succeeds.
    """
    code2 = language.lower()

    async def _compute() -> dict[str, Any]:
        try:
            bazarr = await _get_bazarr(db)
        except HTTPException:
            return {"language": code2, "available": False, "movies": {}, "series": {}}
        try:
            movies_raw = await bazarr.get_movies()
            wanted_eps = await bazarr.get_wanted_series()
        except Exception as exc:  # Bazarr unreachable / error → empty, non-fatal
            logger.warning("Subtitle status fetch failed: %s", exc)
            return {"language": code2, "available": False, "movies": {}, "series": {}}
        finally:
            await bazarr.close()

        movies: dict[str, str] = {}
        for m in movies_raw.get("data", []) if isinstance(movies_raw, dict) else []:
            rid = m.get("radarrId")
            if rid is None:
                continue
            if _has_lang(m.get("subtitles", []), code2):
                movies[str(rid)] = "present"
            elif _has_lang(m.get("missing_subtitles", []), code2):
                movies[str(rid)] = "missing"

        series: dict[str, dict[str, Any]] = {}
        for ep in wanted_eps.get("data", []) if isinstance(wanted_eps, dict) else []:
            if not _has_lang(ep.get("missing_subtitles", []), code2):
                continue
            sid = ep.get("sonarrSeriesId")
            if sid is None:
                continue
            entry = series.setdefault(
                str(sid), {"state": "missing", "missing_episodes": 0}
            )
            entry["missing_episodes"] += 1

        return {
            "language": code2,
            "available": True,
            "movies": movies,
            "series": series,
        }

    return await cache.get_or_set(
        f"subtitles:status:{code2}", _compute, ttl_seconds=120
    )


def _invalidate_status() -> None:
    cache.invalidate_pattern("subtitles:status:*")


# ── Enabled languages ─────────────────────────────────────────
@router.get("/languages")
async def subtitle_languages(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Languages enabled in Bazarr (name/code2/code3)."""
    bazarr = await _get_bazarr(db)
    try:
        langs = await bazarr.get_languages()
        return [l for l in (langs or []) if l.get("enabled")]
    finally:
        await bazarr.close()


# ── Automatic (one-click) download ────────────────────────────
@router.post("/movie/{radarr_id}/search")
async def auto_download_movie(
    radarr_id: int,
    language: str = Query(DEFAULT_LANGUAGE),
    forced: bool = Query(False),
    hi: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Let Bazarr automatically search & download the best subtitle for a movie."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.download_movie_subtitle(
            radarr_id, language.lower(), forced=forced, hi=hi
        )
        # Nudge Bazarr to re-index so Arrmada reflects the new subtitle promptly.
        try:
            await bazarr.scan_movie_disk(radarr_id)
        except Exception as exc:
            logger.debug("scan-disk after movie sub download failed: %s", exc)
    finally:
        await bazarr.close()
    _invalidate_status()
    from app.services.activity_log import log_event
    await log_event(
        category="subtitle", action="sub_download", source="arrmada",
        media_type="movie", media_id=radarr_id, subtitle=language.upper(),
    )
    return {"status": "ok", "result": res}


@router.post("/episode/{series_id}/{episode_id}/search")
async def auto_download_episode(
    series_id: int,
    episode_id: int,
    language: str = Query(DEFAULT_LANGUAGE),
    forced: bool = Query(False),
    hi: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Let Bazarr automatically search & download the best subtitle for an episode."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.download_episode_subtitle(
            series_id, episode_id, language.lower(), forced=forced, hi=hi
        )
    finally:
        await bazarr.close()
    _invalidate_status()
    from app.services.activity_log import log_event
    await log_event(
        category="subtitle", action="sub_download", source="arrmada",
        media_type="series", media_id=series_id, subtitle=f"{language.upper()} · ep {episode_id}",
    )
    return {"status": "ok", "result": res}


@router.post("/series/{series_id}/search")
async def auto_download_series(
    series_id: int,
    language: str = Query(DEFAULT_LANGUAGE),
    forced: bool = Query(False),
    hi: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger an automatic download for every episode of *series_id* that is
    missing a subtitle in *language* (per Bazarr's wanted list)."""
    code2 = language.lower()
    bazarr = await _get_bazarr(db)
    triggered = 0
    try:
        wanted = await bazarr.get_wanted_series()
        eps = wanted.get("data", []) if isinstance(wanted, dict) else []
        targets = [
            ep
            for ep in eps
            if ep.get("sonarrSeriesId") == series_id
            and _has_lang(ep.get("missing_subtitles", []), code2)
        ]
        for ep in targets:
            try:
                await bazarr.download_episode_subtitle(
                    series_id, ep.get("sonarrEpisodeId"), code2, forced=forced, hi=hi
                )
                triggered += 1
            except Exception as exc:
                logger.debug("Episode sub download failed: %s", exc)
    finally:
        await bazarr.close()
    _invalidate_status()
    return {"status": "ok", "triggered": triggered}


# ── Interactive provider search ───────────────────────────────
@router.get("/movie/{radarr_id}/providers")
async def movie_providers(
    radarr_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List candidate subtitles from providers for a movie."""
    bazarr = await _get_bazarr(db)
    try:
        raw = await bazarr.get_movie_provider_subtitles(radarr_id)
    finally:
        await bazarr.close()
    if isinstance(raw, str):  # Bazarr returns a plain error string on failure
        raise HTTPException(status_code=502, detail=raw)
    items = raw.get("data", []) if isinstance(raw, dict) else []
    return {"items": [_normalize_provider(s) for s in items], "total": len(items)}


@router.get("/episode/{episode_id}/providers")
async def episode_providers(
    episode_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List candidate subtitles from providers for an episode."""
    bazarr = await _get_bazarr(db)
    try:
        raw = await bazarr.get_episode_provider_subtitles(episode_id)
    finally:
        await bazarr.close()
    if isinstance(raw, str):
        raise HTTPException(status_code=502, detail=raw)
    items = raw.get("data", []) if isinstance(raw, dict) else []
    return {"items": [_normalize_provider(s) for s in items], "total": len(items)}


def _normalize_provider(s: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Bazarr provider candidate into the shape the frontend uses
    (and that the download endpoints expect back)."""
    ri = s.get("release_info")
    if isinstance(ri, list):
        release_info = ", ".join(str(x) for x in ri)
    else:
        release_info = str(ri or "")
    return {
        "subtitle": s.get("subtitle"),
        "provider": s.get("provider"),
        "language": s.get("language"),
        "release_info": release_info,
        "score": s.get("score"),
        "uploader": s.get("uploader"),
        "url": s.get("url"),
        "original_format": s.get("original_format", ""),
        "hi": str(s.get("hearing_impaired")).lower() in ("true", "1"),
        "forced": str(s.get("forced")).lower() in ("true", "1"),
    }


# ── Download a chosen provider subtitle ───────────────────────
class ProviderDownload(BaseModel):
    subtitle: str
    provider: str
    original_format: str = ""
    hi: bool = False
    forced: bool = False


@router.post("/movie/{radarr_id}/download")
async def download_movie_provider(
    radarr_id: int,
    body: ProviderDownload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Download a specific provider subtitle (from /providers) for a movie."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.download_movie_provider_subtitle(
            radarr_id,
            subtitle=body.subtitle,
            provider=body.provider,
            original_format=body.original_format,
            hi=body.hi,
            forced=body.forced,
        )
        try:
            await bazarr.scan_movie_disk(radarr_id)
        except Exception as exc:
            logger.debug("scan-disk after provider download failed: %s", exc)
    finally:
        await bazarr.close()
    _invalidate_status()
    return {"status": "ok", "result": res}


@router.post("/episode/{series_id}/{episode_id}/download")
async def download_episode_provider(
    series_id: int,
    episode_id: int,
    body: ProviderDownload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Download a specific provider subtitle (from /providers) for an episode."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.download_episode_provider_subtitle(
            series_id,
            episode_id,
            subtitle=body.subtitle,
            provider=body.provider,
            original_format=body.original_format,
            hi=body.hi,
            forced=body.forced,
        )
    finally:
        await bazarr.close()
    _invalidate_status()
    return {"status": "ok", "result": res}


# ── Delete an existing subtitle file ──────────────────────────
class SubtitleDelete(BaseModel):
    language: str
    path: str
    forced: bool = False
    hi: bool = False


@router.delete("/movie/{radarr_id}")
async def delete_movie_subtitle(
    radarr_id: int,
    body: SubtitleDelete,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove an existing subtitle file from a movie."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.delete_movie_subtitle(
            radarr_id,
            body.language.lower(),
            body.path,
            forced=body.forced,
            hi=body.hi,
        )
    finally:
        await bazarr.close()
    _invalidate_status()
    return {"status": "ok", "result": res}


@router.delete("/episode/{series_id}/{episode_id}")
async def delete_episode_subtitle(
    series_id: int,
    episode_id: int,
    body: SubtitleDelete,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove an existing subtitle file from an episode."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.delete_episode_subtitle(
            series_id,
            episode_id,
            body.language.lower(),
            body.path,
            forced=body.forced,
            hi=body.hi,
        )
    finally:
        await bazarr.close()
    _invalidate_status()
    return {"status": "ok", "result": res}


# ── Synchronise a subtitle to the media (ffsubsync, audio ref) ─
class SubtitleSync(BaseModel):
    path: str
    language: str
    forced: bool = False
    hi: bool = False
    # Reference stream for ffsubsync; "a:0" = first audio track (avoids the
    # PGS-embedded-subtitle hang on BluRay remuxes). "" lets Bazarr auto-pick.
    reference: str = "a:0"


@router.post("/movie/{radarr_id}/sync")
async def sync_movie_subtitle(
    radarr_id: int,
    body: SubtitleSync,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Time-align a movie subtitle to its video (Bazarr ffsubsync)."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.sync_subtitle(
            media_type="movie",
            media_id=radarr_id,
            path=body.path,
            language=body.language.lower(),
            forced=body.forced,
            hi=body.hi,
            reference=body.reference or "a:0",
        )
    finally:
        await bazarr.close()
    from app.services.activity_log import log_event
    await log_event(
        category="subtitle", action="sub_sync", source="arrmada",
        media_type="movie", media_id=radarr_id, subtitle=body.language.upper(),
    )
    return {"status": "ok", "result": res}


@router.post("/episode/{series_id}/{episode_id}/sync")
async def sync_episode_subtitle(
    series_id: int,
    episode_id: int,
    body: SubtitleSync,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Time-align an episode subtitle to its video (Bazarr ffsubsync)."""
    bazarr = await _get_bazarr(db)
    try:
        res = await bazarr.sync_subtitle(
            media_type="episode",
            media_id=episode_id,
            path=body.path,
            language=body.language.lower(),
            forced=body.forced,
            hi=body.hi,
            reference=body.reference or "a:0",
        )
    finally:
        await bazarr.close()
    from app.services.activity_log import log_event
    await log_event(
        category="subtitle", action="sub_sync", source="arrmada",
        media_type="series", media_id=series_id, subtitle=f"{body.language.upper()} · ep {episode_id}",
    )
    return {"status": "ok", "result": res}

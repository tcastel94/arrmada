"""Lecture dans l'appli Android native (ADR-007) : infos de lecture et flux relayé."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import tv_playback

router = APIRouter(
    prefix="/api/tv",
    tags=["tv"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/play/movie/{tmdb_id}")
async def play_movie(tmdb_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Film à lancer : adresse du flux relayé, durée, chapitres, reprise."""
    return await tv_playback.movie(db, tmdb_id)


@router.get("/trailer/movie/{tmdb_id}")
async def movie_trailer(tmdb_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Bande-annonce locale (NAS) d'un film, lue en fond sur sa fiche."""
    return await tv_playback.movie_trailer(db, tmdb_id)


@router.get("/play/episode/{tvdb_id}/{season}/{episode}")
async def play_episode(
    tvdb_id: int, season: int, episode: int, db: AsyncSession = Depends(get_db)
) -> dict:
    """Épisode à lancer : comme un film, plus les marqueurs intro / récap / générique."""
    return await tv_playback.episode(db, tvdb_id, season, episode)


@router.get("/series/{tvdb_id}/season/{season}")
async def season(tvdb_id: int, season: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Épisodes d'une saison présents dans Jellyfin (vignette, résumé, durée)."""
    return await tv_playback.season_episodes(db, tvdb_id, season)


@router.get("/stream/{item_id}")
async def stream(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Fichier vidéo d'origine, relayé depuis Jellyfin (avance rapide par « Range »)."""
    try:
        status_code, headers, body = await tv_playback.open_stream(
            db, item_id, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return StreamingResponse(body, status_code=status_code, headers=headers)


@router.get("/hls/{item_id}/{path:path}")
async def hls(item_id: str, path: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Remux HLS de Jellyfin (formats que la TV ne lit pas directement)."""
    try:
        status_code, headers, body = await tv_playback.open_hls(
            db, item_id, path, request.url.query, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    if isinstance(body, bytes):
        return Response(body, status_code=status_code, headers=headers)
    return StreamingResponse(body, status_code=status_code, headers=headers)


@router.post("/hls/{item_id}/stop")
async def hls_stop(item_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """La TV quitte la lecture : Jellyfin arrête le remux."""
    await tv_playback.stop_hls(db, item_id)
    return {"status": "ok"}


@router.get("/chapter-image/{item_id}/{index}")
async def chapter_image(item_id: str, index: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Vignette d'un chapitre (menu pause)."""
    try:
        content, media_type = await tv_playback.chapter_image(db, item_id, index)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    # Une vignette ne change pas : la TV peut la garder une journée.
    return Response(
        content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/item-image/{item_id}")
async def item_image(item_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Vignette d'un épisode (écran Série)."""
    try:
        content, media_type = await tv_playback.item_image(db, item_id)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return Response(
        content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"}
    )

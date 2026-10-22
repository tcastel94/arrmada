"""Écran « Vidéos » : dossiers hors médiathèque (services/video_files.py).

Appareils (jeton d'appareil, réseau local ou VPN) : parcourir, infos de
lecture, flux (avec Range : avance / retour rapide), sous-titres.
Web app : déclarer les dossiers (Réglages › Dossiers vidéo).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.models.local_series import LocalSeries
from app.models.video_root import VideoRoot
from app.services import video_files
from app.services.video_files import NotFound, Root

router = APIRouter(prefix="/api/videos", tags=["videos"], dependencies=[Depends(get_current_user)])

MAX_ROOTS = 30


async def _roots(db: AsyncSession) -> list[Root]:
    rows = (
        await db.execute(select(VideoRoot).order_by(VideoRoot.position, VideoRoot.id))
    ).scalars()
    return [Root(r.id, r.name, r.path) for r in rows]


async def _resolve(db: AsyncSession, token: str):
    roots = {r.id: r for r in await _roots(db)}
    try:
        return video_files.resolve(roots, token)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ─── Explorateur (appareils et web app) ─────────────────────────────────────


@router.get("/browse")
async def browse(path: str = "", db: AsyncSession = Depends(get_db)) -> dict:
    """Sans [path] : les dossiers déclarés. Avec : le contenu de ce dossier."""
    if not path:
        return video_files.roots_listing(await _roots(db))
    root, real, relative = await _resolve(db, path)
    try:
        return video_files.listing(root, real, relative)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/play/{token}")
async def play(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Infos de lecture d'une vidéo (même format que /api/tv/play) + sous-titres à côté."""
    root, real, relative = await _resolve(db, token)
    try:
        return video_files.play_info(root, real, relative)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/stream/{token}")
async def stream(token: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    """La vidéo telle quelle ; Range géré par FileResponse (avance rapide, reprise)."""
    _, real, _ = await _resolve(db, token)
    if not real.is_file() or real.suffix.lower().lstrip(".") not in video_files.VIDEO_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Pas une vidéo")
    return FileResponse(real, media_type=video_files.video_mime(real))


@router.get("/image/{token}")
async def image(token: str, db: AsyncSession = Depends(get_db)) -> FileResponse:
    """Image posée dans un dossier vidéo (poster.jpg, vignette d'épisode) : séries maison."""
    _, real, _ = await _resolve(db, token)
    ext = real.suffix.lower().lstrip(".")
    if not real.is_file() or ext not in video_files.IMAGE_MIME:
        raise HTTPException(status_code=404, detail="Pas une image")
    return FileResponse(real, media_type=video_files.IMAGE_MIME[ext])


@router.get("/subtitle/{token}")
async def subtitle(token: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Sous-titre posé à côté d'une vidéo, converti en UTF-8."""
    _, real, _ = await _resolve(db, token)
    try:
        content, mime = video_files.subtitle_bytes(real)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content, media_type=f"{mime}; charset=utf-8")


# ─── Dossiers déclarés (web app) ─────────────────────────────────────────────


def _public(root: VideoRoot) -> dict:
    return {
        "id": root.id,
        "name": root.name,
        "path": root.path,
        "available": os.path.isdir(root.path),
    }


def _clean_name(value: object) -> str:
    name = str(value or "").strip()[:60]
    if not name:
        raise HTTPException(status_code=422, detail="Nom du dossier obligatoire")
    return name


def _checked_path(value: object) -> str:
    try:
        return video_files.check_root_path(str(value or ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/roots", dependencies=[Depends(require_admin)])
async def list_roots(db: AsyncSession = Depends(get_db)) -> dict:
    rows = (
        await db.execute(select(VideoRoot).order_by(VideoRoot.position, VideoRoot.id))
    ).scalars()
    return {"items": [_public(r) for r in rows]}


@router.post("/roots", dependencies=[Depends(require_admin)])
async def create_root(data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    data = data or {}
    name, path = _clean_name(data.get("name")), _checked_path(data.get("path"))
    count = (await db.execute(select(func.count(VideoRoot.id)))).scalar_one()
    if count >= MAX_ROOTS:
        raise HTTPException(status_code=422, detail=f"{MAX_ROOTS} dossiers au plus")
    if (await db.execute(select(VideoRoot).where(VideoRoot.path == path))).scalars().first():
        raise HTTPException(status_code=409, detail="Ce dossier est déjà déclaré")
    root = VideoRoot(name=name, path=path, position=count, created_at=datetime.now(UTC))
    db.add(root)
    await db.commit()
    await db.refresh(root)
    return _public(root)


@router.patch("/roots/{root_id}", dependencies=[Depends(require_admin)])
async def update_root(root_id: int, data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    root = await db.get(VideoRoot, root_id)
    if root is None:
        raise HTTPException(status_code=404, detail="Dossier inconnu")
    data = data or {}
    if "name" in data:
        root.name = _clean_name(data["name"])
    if "path" in data:
        path = _checked_path(data["path"])
        duplicate = (
            (
                await db.execute(
                    select(VideoRoot).where(VideoRoot.path == path, VideoRoot.id != root_id)
                )
            )
            .scalars()
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Ce dossier est déjà déclaré")
        root.path = path
    await db.commit()
    return _public(root)


@router.delete("/roots/{root_id}", dependencies=[Depends(require_admin)])
async def delete_root(root_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Retire le dossier de l'écran Vidéos (rien n'est supprimé sur le disque)."""
    root = await db.get(VideoRoot, root_id)
    if root is None:
        raise HTTPException(status_code=404, detail="Dossier inconnu")
    # Ses séries maison disparaissent avec lui (rien n'est supprimé sur le disque)
    for series in (
        await db.execute(select(LocalSeries).where(LocalSeries.root_id == root_id))
    ).scalars():
        await db.delete(series)
    await db.delete(root)
    await db.commit()
    return {"status": "ok"}

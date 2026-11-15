"""Remux à alléger : liste, remplacement par lot, corbeille (ADR-021).

Écran : Santé médiathèque › Remux. Toute la logique est dans
``services/remux_slim.py`` ; ces routes ne font que la brancher.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services import remux_slim

router = APIRouter(
    prefix="/api/remux",
    tags=["remux"],
    dependencies=[Depends(get_current_user)],
)


class ReplaceBody(BaseModel):
    movie_ids: list[int] = Field(min_length=1)
    include_1080p: bool = False


class KeepBody(BaseModel):
    movie_ids: list[int] = Field(min_length=1)
    profile_id: int


def _unreachable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail=f"Radarr ne répond pas : {exc}")


@router.get("")
async def get_remux(
    include_1080p: bool = Query(False, description="Compter aussi les Remux-1080p"),
) -> dict[str, Any]:
    """Films dont le fichier est un remux que leur profil n'autorise plus."""
    try:
        data = await remux_slim.inventory(include_1080p=include_1080p)
    except remux_slim.Refused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise _unreachable(exc) from exc
    return {**data, "job": remux_slim.job()}


@router.get("/job")
async def get_job() -> dict[str, Any]:
    """Avancement du lot en cours (ou résultat du dernier)."""
    return {"job": remux_slim.job()}


@router.post("/replace", status_code=202)
async def replace(body: ReplaceBody) -> dict[str, Any]:
    """Lance le remplacement d'un lot de films (10 au plus), en tâche de fond.

    Pour chaque film : recherche d'un remplaçant plus léger, mise en
    téléchargement, puis suppression du fichier du remux (jamais du film). La
    page demande la confirmation avant d'appeler cette route.
    """
    try:
        return {"job": remux_slim.start(body.movie_ids, include_1080p=body.include_1080p)}
    except remux_slim.Refused as exc:
        status = 409 if remux_slim.is_running() else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/job/stop")
async def stop_job() -> dict[str, Any]:
    """Arrête le lot après le film en cours."""
    return {"job": remux_slim.stop()}


@router.post("/keep")
async def keep(body: KeepBody) -> dict[str, Any]:
    """Passe des films dans un profil qui garde le remux (« films d'exception »)."""
    try:
        return await remux_slim.keep(body.movie_ids, body.profile_id)
    except remux_slim.Refused as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise _unreachable(exc) from exc

"""Artworks : bouton « Récupérer les artworks » de la web app (services/artwork.py).

Routes réservées à la web app : une TV appairée n'y a pas accès (périmètre TV,
api/deps.py). Les écrans lisent les artworks via la médiathèque et la fiche.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import artwork

router = APIRouter(
    prefix="/api/artwork",
    tags=["artwork"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/status")
async def artwork_status(db: AsyncSession = Depends(get_db)):
    """Progression de la récupération + sources configurées + bilan en base."""
    return await artwork.status(db)


@router.post("/refresh", status_code=202)
async def artwork_refresh(
    force: bool = Query(False, description="Redemander aussi les titres déjà servis"),
    db: AsyncSession = Depends(get_db),
):
    """Lance la récupération sur toute la médiathèque, en arrière-plan.

    Sans `force`, seuls les titres jamais demandés (ou servis il y a longtemps)
    sont interrogés : relancer le bouton ne coûte presque rien.
    """
    sources = artwork.sources_configured()
    if not any(sources.values()):
        raise HTTPException(
            status_code=400,
            detail="Aucune source d'artworks : renseigne FANART_API_KEY (ou TMDB_API_KEY) "
            "dans le fichier .env du serveur",
        )
    if not artwork.start_refresh(force):
        raise HTTPException(status_code=409, detail="Récupération déjà en cours")
    return await artwork.status(db)


@router.post("/{type}/{id}/refresh")
async def artwork_refresh_one(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """Un seul titre, tout de suite (bouton de la fiche)."""
    if type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Type attendu : movie ou series")
    if not any(artwork.sources_configured().values()):
        raise HTTPException(
            status_code=400,
            detail="Aucune source d'artworks : renseigne FANART_API_KEY (ou TMDB_API_KEY)",
        )
    result = await artwork.refresh_one(db, type, id)
    if result is None:
        raise HTTPException(status_code=404, detail="Titre introuvable dans la médiathèque")
    return result

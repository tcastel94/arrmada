"""Artworks : récupération, galerie d'un titre, images des dossiers des médias.

- `router` (web app seulement : une TV appairée n'y a pas accès, périmètre TV
  dans api/deps.py) : bouton « Artworks » de la Médiathèque, galerie et
  bouton « Actualiser » de l'onglet Artworks d'une fiche.
- `files_router` (SANS authentification) : sert une image rangée à côté d'un
  film / d'une série. Une balise <img> du navigateur et Kodi ne savent pas
  envoyer de jeton ; la sécurité vient de l'adresse elle-même, signée par le
  serveur (comme une URL pré-signée S3) et limitée aux dossiers des médias,
  et du réseau : réseau local uniquement, comme le dépôt Kodi.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import artwork
from app.services import devices as devices_service

router = APIRouter(
    prefix="/api/artwork",
    tags=["artwork"],
    dependencies=[Depends(get_current_user)],
)
files_router = APIRouter(prefix="/api/artwork", tags=["artwork"])

NO_SOURCE = (
    "Aucune source d'artworks : renseigne FANART_CLIENT_KEY (clé personnelle d'un compte "
    "fanart.tv gratuit) ou TMDB_API_KEY dans le fichier .env du serveur, ou active "
    "ARTWORK_LOCAL_ENABLED (images des dossiers des médias)"
)
MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


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
    if not any(artwork.sources_configured().values()):
        raise HTTPException(status_code=400, detail=NO_SOURCE)
    if not artwork.start_refresh(force):
        raise HTTPException(status_code=409, detail="Récupération déjà en cours")
    return await artwork.status(db)


@router.get("/{type}/{id}")
async def artwork_gallery(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """Toutes les images connues d'un titre (onglet Artworks de la fiche)."""
    if type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Type attendu : movie ou series")
    gallery = await artwork.title_gallery(db, type, id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="Titre introuvable dans la médiathèque")
    return gallery


@router.post("/{type}/{id}/refresh")
async def artwork_refresh_one(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """Un seul titre, tout de suite (bouton de la fiche)."""
    if type not in ("movie", "series"):
        raise HTTPException(status_code=400, detail="Type attendu : movie ou series")
    if not any(artwork.sources_configured().values()):
        raise HTTPException(status_code=400, detail=NO_SOURCE)
    result = await artwork.refresh_one(db, type, id)
    if result is None:
        raise HTTPException(status_code=404, detail="Titre introuvable dans la médiathèque")
    return result


@files_router.get("/local/{signature}/{name}")
async def artwork_local_file(signature: str, name: str, request: Request):
    """Image du dossier d'un média, désignée par une adresse signée (local_url).

    Adresse falsifiée, fichier hors des dossiers des médias, pas une image ou
    disparu : 404, sans dire lequel (rien à apprendre pour un curieux).
    """
    host = request.client.host if request.client else ""
    if not devices_service.is_lan_request(host, request.headers.get("X-Forwarded-For")):
        raise HTTPException(status_code=403, detail="Images accessibles en réseau local")
    path = artwork.resolve_local(signature, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Image introuvable")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        # L'adresse change avec le fichier (?v=date) : on peut garder longtemps
        headers={"Cache-Control": "public, max-age=604800"},
    )

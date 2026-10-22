"""Profils famille (ADR-008) : qui regarde sur les TV de la maison.

Lecture ouverte aux TV appairées (écran « Qui regarde ? ») ; création,
modification et suppression réservées à la web app.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.services import family_profiles

router = APIRouter(
    prefix="/api/profiles", tags=["profiles"], dependencies=[Depends(get_current_user)]
)


@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db)) -> dict:
    """Profils, « Famille » en premier."""
    return {"items": await family_profiles.list_profiles(db)}


@router.post("", dependencies=[Depends(require_admin)])
async def create_profile(data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        return await family_profiles.create(db, data or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{profile_id}", dependencies=[Depends(require_admin)])
async def update_profile(profile_id: int, data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        profile = await family_profiles.update_profile(db, profile_id, data or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=404, detail="Profil inconnu")
    return profile


@router.delete("/{profile_id}", dependencies=[Depends(require_admin)])
async def delete_profile(profile_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        deleted = await family_profiles.delete_profile(db, profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Profil inconnu")
    return {"status": "ok"}

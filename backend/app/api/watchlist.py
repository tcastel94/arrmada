"""Liste « À voir » par profil famille (TV, web app, tablette).

Profil de l'appel :
  - TV (jeton d'appareil) : le profil qui regarde, annoncé par l'en-tête
    `X-Profile-Id` (ADR-008) ;
  - web app : paramètre `?profile=<id>` (sélecteur « Liste de » de la page),
    absent ou inconnu → « Famille ».

`POST` avec `request: true` : si le titre n'est pas encore dans la
médiathèque, il est aussi demandé à Radarr / Sonarr (sans priorité « pour
ce soir ») — ajouter à sa liste un titre qu'on n'a pas, c'est vouloir
le voir.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import family_profiles, watchlist

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/watchlist", tags=["watchlist"], dependencies=[Depends(get_current_user)]
)


async def _profile(db: AsyncSession, user: dict[str, Any], profile: int | None) -> int | None:
    """Profil visé : celui de la TV, sinon celui choisi dans la web app."""
    if user.get("role") == "device":
        return user.get("profile_id")
    profile_id, _name = await family_profiles.resolve(db, str(profile) if profile else None)
    return profile_id


@router.get("")
async def list_watchlist(
    profile: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    profile_id = await _profile(db, user, profile)
    return {"profile_id": profile_id, "items": await watchlist.list_items(db, profile_id)}


@router.post("")
async def add_to_watchlist(
    data: dict,
    profile: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    profile_id = await _profile(db, user, profile if profile is not None else data.get("profile"))
    try:
        item = await watchlist.add(db, profile_id, data)
    except watchlist.WatchlistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    download: dict[str, Any] | None = None
    if data.get("request") and not item["in_library"]:
        from app.services import tv_download, tv_priority

        origin = (
            tv_priority.origin_of(user)
            if user.get("role") == "device"
            else {
                "device_id": None,
                "device_name": "Web app",
                "room": None,
                "profile_id": profile_id,
            }
        )
        try:
            download = await tv_download.start_download(
                db,
                {
                    "type": item["media_type"],
                    "tmdb_id": item["tmdb_id"],
                    "tvdb_id": item["tvdb_id"],
                    "title": item["title"],
                    "year": item["year"],
                    # Une envie, pas une urgence : pas de passe-droit dans la file
                    "priority": False,
                },
                origin,
            )
        except Exception as exc:  # la liste est à jour même si Radarr / Sonarr refuse
            logger.warning("Ma liste : demande de « %s » impossible : %s", item["title"], exc)
            download = {"status": "error", "message": str(exc)}
    return {"item": item, "download": download}


@router.delete("/{media_type}/{external_id}")
async def remove_from_watchlist(
    media_type: str,
    external_id: int,
    profile: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    profile_id = await _profile(db, user, profile)
    try:
        removed = await watchlist.remove(db, profile_id, media_type, str(external_id))
    except watchlist.WatchlistError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "removed": removed}

"""Trakt : liaison des comptes (web app), notes et suivi de lecture (TV) — ADR-022.

TV (profil qui regarde, en-tête X-Profile-Id) :
  GET  /api/trakt/status    compte relié à ce profil ?
  GET  /api/trakt/prompt    notes à proposer en fin de lecture (épisode, saison, série)
  POST /api/trakt/rate      envoie une note (1 à 10 : 5 étoiles, demi-étoiles)
Web app (administrateur) :
  GET    /api/trakt/accounts          profils et comptes reliés
  POST   /api/trakt/link              code à taper sur trakt.tv/activate
  POST   /api/trakt/link/poll         le code a-t-il été tapé ?
  DELETE /api/trakt/link/{profile_id} délier (0 = « Famille »)
La lecture en direct (scrobble) ne passe pas par ici : le serveur relaie le
flux « lecture en cours » que la TV envoie déjà (/api/kodi/scrobble).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.services import family_profiles, trakt
from app.services.activity_log import log_event
from app.services.sonarr import SonarrClient
from app.services.unstick import _client as arr_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/trakt", tags=["trakt"])


def _profile(user: dict) -> int | None:
    return user.get("profile_id")


# ── TV ────────────────────────────────────────────────────────


@router.get("/status")
async def trakt_status(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    row = await trakt.account(db, _profile(user)) if trakt.configured() else None
    return {
        "configured": trakt.configured(),
        "linked": row is not None,
        "username": row.username if row else "",
    }


async def _series_info(db: AsyncSession, tvdb_id: int) -> tuple[str, bool, list[dict[str, Any]]]:
    """(titre, série terminée ?, épisodes) d'une série de Sonarr, par son TVDB."""
    client = await arr_client(db, "sonarr")
    if client is None:
        return "", False, []
    try:
        assert isinstance(client, SonarrClient)
        series = next(
            (s for s in await client.get_series() if int(s.get("tvdbId") or 0) == tvdb_id), None
        )
        if series is None:
            return "", False, []
        episodes = await client.get("/episode", params={"seriesId": series["id"]})
        return (
            str(series.get("title") or ""),
            str(series.get("status") or "").lower() == "ended",
            [e for e in episodes or [] if isinstance(e, dict)],
        )
    finally:
        await client.close()


@router.get("/prompt")
async def trakt_prompt(
    kind: Literal["movie", "episode"],
    tvdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Notes à proposer à la fin : film → [film] ; épisode → [épisode, saison ?, série ?]."""
    if not trakt.configured() or await trakt.account(db, _profile(user)) is None:
        return {"linked": False, "steps": []}
    if kind == "movie":
        return {"linked": True, "steps": [{"kind": "movie", "label": "Ce film"}]}
    if not tvdb_id or season is None or not episode:
        return {"linked": True, "steps": []}
    try:
        title, ended, episodes = await _series_info(db, tvdb_id)
    except Exception as exc:  # noqa: BLE001 : Sonarr injoignable → l'épisode seul
        logger.info("Trakt : saisons de %s illisibles (%s)", tvdb_id, exc)
        title, ended, episodes = "", False, []
    labels = {
        "episode": f"Épisode S{season:02d}E{episode:02d}",
        "season": f"Saison {season}" + (f" de {title}" if title else ""),
        "show": f"La série {title}".strip() if title else "La série",
    }
    steps = trakt.rating_steps(episodes, season, episode, ended)
    return {"linked": True, "steps": [{"kind": k, "label": labels[k]} for k in steps]}


class RateBody(BaseModel):
    kind: Literal["movie", "episode", "season", "show"]
    rating: int = Field(ge=1, le=10)
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    season: int | None = Field(default=None, ge=0)
    episode: int | None = Field(default=None, ge=1)
    title: str = Field(default="", max_length=300)


@router.post("/rate")
async def trakt_rate(
    body: RateBody, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    try:
        message = await trakt.rate(
            db,
            _profile(user),
            body.kind,
            body.rating,
            tmdb_id=body.tmdb_id,
            tvdb_id=body.tvdb_id,
            season=body.season,
            episode=body.episode,
        )
    except trakt.TraktError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    await log_event(
        category="trakt",
        action=f"rate_{body.kind}",
        source="android" if user.get("role") == "device" else "web",
        media_type=body.kind,
        media_id=body.tmdb_id or body.tvdb_id,
        title=body.title or None,
        subtitle=f"{body.rating}/10",
        device=user.get("device_name"),
        detail=message,
    )
    return {"ok": True, "message": message}


# ── Web app : liaison des comptes ─────────────────────────────


@router.get("/accounts", dependencies=[Depends(require_admin)])
async def trakt_accounts(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    linked = await trakt.accounts(db)
    profiles = []
    for p in await family_profiles.list_profiles(db):
        key = 0 if p["is_default"] else int(p["id"])
        row = linked.get(key)
        profiles.append(
            {
                **p,
                "profile_key": key,
                "linked": row is not None,
                "username": row.username if row else "",
                "linked_at": row.linked_at.isoformat() if row else None,
            }
        )
    return {"configured": trakt.configured(), "profiles": profiles}


class LinkBody(BaseModel):
    profile_key: int = Field(ge=0)  # 0 = « Famille »


class PollBody(LinkBody):
    device_code: str = Field(min_length=8, max_length=200)


def _profile_id(key: int) -> int | None:
    return key or None


@router.post("/link", dependencies=[Depends(require_admin)])
async def trakt_link(body: LinkBody) -> dict[str, Any]:
    try:
        return await trakt.start_link()
    except trakt.TraktError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/link/poll", dependencies=[Depends(require_admin)])
async def trakt_link_poll(body: PollBody, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await trakt.poll_link(db, _profile_id(body.profile_key), body.device_code)
    if result["status"] == "linked":
        await log_event(
            category="trakt",
            action="link",
            source="web",
            title=f"Compte Trakt @{result.get('username') or '?'} relié",
            detail=f"profil {body.profile_key}",
        )
    return result


@router.delete("/link/{profile_key}", dependencies=[Depends(require_admin)])
async def trakt_unlink(profile_key: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not await trakt.unlink(db, _profile_id(profile_key)):
        raise HTTPException(status_code=404, detail="Aucun compte Trakt relié à ce profil")
    return {"ok": True}

"""Profils famille (ADR-008) : liste, création, et profil d'un appel TV.

Une TV (appli Android) annonce le profil qui regarde par l'en-tête
`X-Profile-Id`, à chaque appel, comme un `sudo -u` qui dit pour qui la
commande s'exécute. Sans en-tête (TV sous Kodi, web app), ou avec un profil
inconnu, c'est le profil « Famille » : les données d'avant les profils.

Côté données, le profil « Famille » est `None` (profile_id null) : rien à
migrer, les TV sous Kodi continuent comme avant.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family_profile import FamilyProfile

DEFAULT_NAME = "Famille"
MAX_PROFILES = 8
COLORS = ("#4A9EFF", "#22E0EE", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#F472B6", "#FB923C")
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def public(p: FamilyProfile) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "color": p.color,
        "emoji": p.emoji,
        "is_default": p.is_default,
    }


async def ensure_default(db: AsyncSession) -> FamilyProfile:
    """Le profil « Famille » existe toujours (créé au premier besoin)."""
    row = (
        (await db.execute(select(FamilyProfile).where(FamilyProfile.is_default.is_(True))))
        .scalars()
        .first()
    )
    if row is None:
        row = FamilyProfile(
            name=DEFAULT_NAME, color=COLORS[0], emoji="", is_default=True, position=0,
            created_at=datetime.now(UTC),
        )  # fmt: skip
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def list_profiles(db: AsyncSession) -> list[dict[str, Any]]:
    await ensure_default(db)
    rows = await db.execute(
        select(FamilyProfile).order_by(
            FamilyProfile.is_default.desc(), FamilyProfile.position, FamilyProfile.id
        )
    )
    return [public(p) for p in rows.scalars().all()]


def _clean_name(name: Any) -> str:
    text = " ".join(str(name or "").split())[:40]
    if not text:
        raise ValueError("Nom du profil requis")
    return text


def _clean_color(color: Any, fallback: str) -> str:
    text = str(color or "").strip()
    return text.upper() if _COLOR.match(text) else fallback


async def create(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    await ensure_default(db)
    count = (await db.execute(select(func.count(FamilyProfile.id)))).scalar_one()
    if count >= MAX_PROFILES:
        raise ValueError(f"{MAX_PROFILES} profils au plus")
    profile = FamilyProfile(
        name=_clean_name(data.get("name")),
        color=_clean_color(data.get("color"), COLORS[count % len(COLORS)]),
        emoji=str(data.get("emoji") or "")[:8],
        is_default=False,
        position=count,
        created_at=datetime.now(UTC),
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return public(profile)


async def update_profile(
    db: AsyncSession, profile_id: int, data: dict[str, Any]
) -> dict[str, Any] | None:
    profile = await db.get(FamilyProfile, profile_id)
    if profile is None:
        return None
    if "name" in data:
        profile.name = _clean_name(data.get("name"))
    if "color" in data:
        profile.color = _clean_color(data.get("color"), profile.color)
    if "emoji" in data:
        profile.emoji = str(data.get("emoji") or "")[:8]
    await db.commit()
    return public(profile)


async def delete_profile(db: AsyncSession, profile_id: int) -> bool:
    """Supprime un profil, son vu / reprise ; ses demandes passent à « Famille »."""
    from app.models.tv_request import TvRequest
    from app.models.watch_state import WatchState

    profile = await db.get(FamilyProfile, profile_id)
    if profile is None:
        return False
    if profile.is_default:
        raise ValueError("Le profil « Famille » ne se supprime pas")
    await db.execute(delete(WatchState).where(WatchState.profile_id == profile_id))
    await db.execute(
        update(TvRequest)
        .where(TvRequest.profile_id == profile_id)
        .values(profile_id=None, profile_name=None)
    )
    await db.delete(profile)
    await db.commit()
    return True


async def resolve(db: AsyncSession, header: str | None) -> tuple[int | None, str | None]:
    """En-tête `X-Profile-Id` → (profil, nom) ; « Famille » ou inconnu → (None, None)."""
    try:
        profile_id = int(str(header or "").strip())
    except ValueError:
        return None, None
    if profile_id <= 0:
        return None, None
    profile = await db.get(FamilyProfile, profile_id)
    if profile is None or profile.is_default:
        return None, None
    return profile.id, profile.name


def profiled_key(key: str, profile_id: int | None) -> str:
    """Clé de vu / reprise d'un profil : « p3:movie:tmdb:438631 » (« Famille » : inchangée)."""
    return key if profile_id is None else f"p{profile_id}:{key}"

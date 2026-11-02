"""Dernier choix de pistes d'un profil, par série / film (appli Android TV).

Lu au lancement d'un épisode ou d'un film ; écrit quand quelqu'un change
de piste dans le menu pause (ou depuis la tablette). Sans ligne, la TV
applique sa règle automatique (VO + sous-titres FR, ou VF + forcés).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track_preference import TrackPreference
from app.services.watch_sync import _insert_for

# Ce que la TV a le droit de ranger : série TVDB, film TMDB, série maison
SCOPE_RE = re.compile(r"^(series:tvdb:\d{1,10}|movie:tmdb:\d{1,10}|local:\d{1,10})$")
# Code de langue ISO (« fr », « eng ») ; « off » pour des sous-titres coupés
LANG_RE = re.compile(r"^[a-z]{2,3}$")
SUBTITLES_OFF = "off"


def valid_scope(scope: str) -> bool:
    return bool(SCOPE_RE.match(scope or ""))


def _key(profile_id: int | None, scope: str) -> str:
    return f"{profile_id or 0}|{scope}"


def _language(value: Any, allow_off: bool = False) -> str:
    """Langue propre (« fr »), « off » si permis, vide sinon (valeur inconnue ignorée)."""
    text = str(value or "").strip().lower()
    if allow_off and text == SUBTITLES_OFF:
        return SUBTITLES_OFF
    return text if LANG_RE.match(text) else ""


def public(row: TrackPreference | None) -> dict[str, Any]:
    """Forme renvoyée à la TV ; `found` faux : aucun choix rangé (règle automatique)."""
    if row is None:
        return {
            "found": False,
            "audio_language": "",
            "subtitle_language": "",
            "subtitle_forced": False,
        }
    return {
        "found": True,
        "audio_language": row.audio_language,
        "subtitle_language": row.subtitle_language,
        "subtitle_forced": bool(row.subtitle_forced),
    }


async def get(db: AsyncSession, profile_id: int | None, scope: str) -> dict[str, Any]:
    row = (
        (
            await db.execute(
                select(TrackPreference).where(TrackPreference.key == _key(profile_id, scope))
            )
        )
        .scalars()
        .first()
    )
    return public(row)


async def store(
    db: AsyncSession, profile_id: int | None, scope: str, body: dict[str, Any]
) -> dict[str, Any]:
    """Range le choix (upsert ON CONFLICT sur la clé profil × titre)."""
    audio = _language(body.get("audio_language"))
    subtitle = _language(body.get("subtitle_language"), allow_off=True)
    forced = bool(body.get("subtitle_forced")) and subtitle not in ("", SUBTITLES_OFF)
    values = {
        "key": _key(profile_id, scope),
        "profile_id": profile_id,
        "scope": scope,
        "audio_language": audio,
        "subtitle_language": subtitle,
        "subtitle_forced": forced,
        "updated_at": datetime.now(UTC),
    }
    insert = _insert_for(db)
    stmt = insert(TrackPreference).values(values)
    updated = {
        c: stmt.excluded[c]
        for c in ("audio_language", "subtitle_language", "subtitle_forced", "updated_at")
    }
    await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_=updated))
    await db.commit()
    return {
        "found": True,
        "audio_language": audio,
        "subtitle_language": subtitle,
        "subtitle_forced": forced,
    }

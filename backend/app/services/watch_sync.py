"""Vu / reprise partagés entre les TV (ADR-004, phase 4.4).

Principe (comme un rsync « dernier écrit gagne », avec un curseur) :

  1. une TV termine un épisode, s'arrête à 42:10 ou coche « vu » : elle
     dépose l'état du titre ici (`POST /api/kodi/watch-state`) ;
  2. le serveur le range (une ligne par film / épisode) et publie un
     événement `watch_state` ;
  3. les autres TV, qui relèvent les événements toutes les 5 s, relisent
     ce qui a changé depuis leur dernier passage (`GET …?since=<curseur>`)
     et l'appliquent à leur propre médiathèque Kodi.

Deux façons de déposer :

  - **en direct** (`merge=False`) : l'état envoyé remplace celui du serveur.
    C'est le geste le plus récent qui compte (« vu » puis « non vu » sur une
    autre TV → non vu partout) ;
  - **fusion** (`merge=True`), au tout premier passage d'une TV : elle
    apporte ce que sa médiathèque connaît déjà, sans rien défaire. « Vu »
    l'emporte toujours ; une reprise n'est prise que si le serveur n'en a pas.

Le curseur est la date de mise à jour de la ligne, rendue strictement
croissante : deux lignes n'ont jamais la même date, la TV ne rate ni ne
relit rien.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

# « file » + « sha1 » : vidéo hors médiathèque (écran Vidéos), repérée par
# l'empreinte de son chemin sur le NAS
MEDIA_TYPES = ("movie", "episode", "file")
ID_TYPES = ("tmdb", "tvdb", "imdb", "sha1")
POSITION_TOLERANCE = 10  # s : en dessous, deux positions de reprise sont « la même »
MAX_STATES = 500  # par envoi et par page de relecture
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
_LAST_PLAYED = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

_last_stamp: datetime | None = None


def next_stamp(now: datetime | None = None) -> datetime:
    """Date de mise à jour strictement croissante (curseur des TV).

    Deux dépôts dans la même microseconde (envoi groupé) recevraient la
    même date : la TV qui relit « après » cette date en raterait un. On
    avance donc d'une microseconde si besoin, comme un numéro de séquence.
    """
    global _last_stamp
    stamp = now or datetime.now(UTC)
    if _last_stamp is not None and stamp <= _last_stamp:
        stamp = _last_stamp + timedelta(microseconds=1)
    _last_stamp = stamp
    return stamp


def as_utc(value: datetime) -> datetime:
    """SQLite rend des dates sans fuseau : elles sont en UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def parse_cursor(value: str | None) -> datetime | None:
    """« 2026-10-11T19:42:05.123456+00:00 » → date ; None si absent ou illisible."""
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    # Toujours en UTC : SQLite compare les dates comme du texte, sans fuseau.
    return as_utc(moment).astimezone(UTC)


def _int(value: Any, low: int = 0, high: int = 10**7) -> int | None:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def state_key(media_type: str, id_type: str, external_id: str, season=None, episode=None) -> str:
    """Clé d'une ligne : « movie:tmdb:438631 », « episode:tvdb:280619:2:5 »."""
    key = f"{media_type}:{id_type}:{external_id}"
    if media_type == "episode":
        key += f":{season}:{episode}"
    return key


def normalize(raw: Any) -> dict[str, Any] | None:
    """État envoyé par une TV → état propre ; None s'il est inutilisable.

    Attendu : {media_type, id_type, id, season, episode, watched, position,
    total, last_played, title}. Tout est vérifié : la TV ne peut écrire
    qu'une ligne de vu / reprise, rien d'autre.
    """
    if not isinstance(raw, dict):
        return None
    media_type = str(raw.get("media_type") or "")
    id_type = str(raw.get("id_type") or "")
    external_id = str(raw.get("id") or "").strip()
    if media_type not in MEDIA_TYPES or id_type not in ID_TYPES or not _ID.match(external_id):
        return None
    season = episode = None
    if media_type == "episode":
        season, episode = _int(raw.get("season"), 0, 9999), _int(raw.get("episode"), 0, 99999)
        if season is None or episode is None:
            return None
    position = _int(raw.get("position")) or 0
    total = _int(raw.get("total")) or 0
    last_played = str(raw.get("last_played") or "")
    return {
        "key": state_key(media_type, id_type, external_id, season, episode),
        "media_type": media_type,
        "id_type": id_type,
        "external_id": external_id,
        "season": season,
        "episode": episode,
        "title": str(raw.get("title") or "")[:300],
        "watched": bool(raw.get("watched")),
        "position": position,
        "total": total,
        "last_played": last_played if _LAST_PLAYED.match(last_played) else "",
    }


def _same(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Même vu, même reprise (à 10 s près) : rien à partager."""
    return (
        bool(old["watched"]) == bool(new["watched"])
        and abs(int(old["position"] or 0) - int(new["position"] or 0)) < POSITION_TOLERANCE
    )


def resolve(
    existing: dict[str, Any] | None, incoming: dict[str, Any], merge: bool
) -> dict[str, Any] | None:
    """Nouvel état d'une ligne, ou None s'il n'y a rien à changer.

    `existing` : la ligne actuelle (None si le titre est inconnu du serveur).
    """
    if existing is None:
        # Ni vu ni commencé : rien à partager (évite une ligne par épisode
        # à chaque scan de médiathèque).
        if not incoming["watched"] and not incoming["position"]:
            return None
        return dict(incoming)
    if merge:
        result = dict(existing)
        result["title"] = existing.get("title") or incoming["title"]
        result["total"] = existing.get("total") or incoming["total"]
        result["last_played"] = max(existing.get("last_played") or "", incoming["last_played"])
        if not existing["watched"] and incoming["watched"]:
            result["watched"], result["position"] = True, incoming["position"]
        elif not existing["watched"] and not existing["position"]:
            result["position"] = incoming["position"]
        if _same(existing, result):
            return None
        return result
    if _same(existing, incoming):
        return None
    result = dict(incoming)
    result["title"] = incoming["title"] or existing.get("title") or ""
    result["total"] = incoming["total"] or existing.get("total") or 0
    result["last_played"] = incoming["last_played"] or existing.get("last_played") or ""
    return result


def public(row: Any) -> dict[str, Any]:
    """Ligne de la table → ce que relit une TV."""
    return {
        "media_type": row.media_type,
        "id_type": row.id_type,
        "id": row.external_id,
        "season": row.season,
        "episode": row.episode,
        "title": row.title,
        "watched": bool(row.watched),
        "position": row.position,
        "total": row.total,
        "last_played": row.last_played,
        "device": row.device,
        "updated_at": as_utc(row.updated_at).isoformat(),
    }


def row_values(row: Any) -> dict[str, Any]:
    """Ligne de la table → dict comparable à `normalize()`."""
    return {
        "key": row.key,
        "media_type": row.media_type,
        "id_type": row.id_type,
        "external_id": row.external_id,
        "season": row.season,
        "episode": row.episode,
        "title": row.title,
        "watched": bool(row.watched),
        "position": row.position,
        "total": row.total,
        "last_played": row.last_played,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Base de données
# ─────────────────────────────────────────────────────────────────────────────

_CHUNK = 50  # lignes par requête (limite de paramètres des vieux SQLite)


def _insert_for(db: Any):
    """`INSERT … ON CONFLICT` du moteur en place (PostgreSQL en production)."""
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


async def store(
    db: Any, raw_states: list[Any], merge: bool, device: str, profile_id: int | None = None
) -> tuple[list[dict[str, Any]], int]:
    """Range les états envoyés par une TV ; renvoie (lignes modifiées, états refusés).

    Lecture des lignes existantes, décision en Python (`resolve`), puis
    upsert `ON CONFLICT (key) DO UPDATE` des seules lignes qui changent.
    [profile_id] : profil famille (ADR-008), None pour « Famille » ; ses
    lignes ont une clé préfixée (« p3:movie:tmdb:438631 »).
    """
    from sqlalchemy import select

    from app.models.watch_state import WatchState
    from app.services.family_profiles import profiled_key

    incoming: dict[str, dict[str, Any]] = {}
    rejected = 0
    for raw in raw_states[:MAX_STATES]:
        state = normalize(raw)
        if state is None:
            rejected += 1
            continue
        state["key"] = profiled_key(state["key"], profile_id)
        incoming[state["key"]] = state  # le dernier d'un même titre l'emporte

    existing: dict[str, dict[str, Any]] = {}
    keys = list(incoming)
    for start in range(0, len(keys), _CHUNK):
        rows = await db.execute(
            select(WatchState).where(WatchState.key.in_(keys[start : start + _CHUNK]))
        )
        existing.update({row.key: row_values(row) for row in rows.scalars()})

    changed = []
    for key, state in incoming.items():
        result = resolve(existing.get(key), state, merge)
        if result is not None:
            changed.append(
                dict(result, device=device[:100], updated_at=next_stamp(), profile_id=profile_id)
            )
    if not changed:
        return [], rejected

    insert = _insert_for(db)
    for start in range(0, len(changed), _CHUNK):
        stmt = insert(WatchState).values(changed[start : start + _CHUNK])
        updated = {
            column: stmt.excluded[column]
            for column in (
                "title", "watched", "position", "total",
                "last_played", "device", "updated_at",
            )
        }  # fmt: skip
        await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_=updated))
    await db.commit()
    return changed, rejected


async def changes(
    db: Any, since: datetime | None, limit: int = MAX_STATES, profile_id: int | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """États d'un profil modifiés après `since` (tous si None), du plus ancien au plus récent.

    Renvoie (états, il en reste d'autres).
    """
    from sqlalchemy import select

    from app.models.watch_state import WatchState

    limit = max(1, min(limit, MAX_STATES))
    query = select(WatchState).order_by(WatchState.updated_at, WatchState.id)
    query = query.where(
        WatchState.profile_id.is_(None)
        if profile_id is None
        else WatchState.profile_id == profile_id
    )
    if since is not None:
        query = query.where(WatchState.updated_at > since)
    rows = (await db.execute(query.limit(limit + 1))).scalars().all()
    return [public(row) for row in rows[:limit]], len(rows) > limit

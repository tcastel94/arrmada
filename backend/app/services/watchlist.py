"""Liste « À voir » par profil famille : lecture, ajout, retrait.

Le profil vient de l'appel (voir api/watchlist.py) : None = « Famille ».
Chaque titre de la liste est enrichi avec son état dans la médiathèque
(présent, téléchargé, identifiant Radarr / Sonarr pour ouvrir sa fiche),
lu dans le cache de la médiathèque : la liste reste à jour toute seule
quand un titre demandé arrive sur le NAS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.watchlist import WatchlistItem
from app.services.family_profiles import profiled_key

MAX_ITEMS = 200  # par profil : une liste, pas une deuxième médiathèque
MEDIA_TYPES = {"movie": "tmdb", "series": "tvdb"}


class WatchlistError(ValueError):
    """Titre invalide (type inconnu, identifiant manquant) ou liste pleine."""


def base_key(media_type: str, external_id: int | str) -> str:
    """« movie:tmdb:438631 » / « series:tvdb:280619 »."""
    if media_type not in MEDIA_TYPES:
        raise WatchlistError(f"Type inconnu : {media_type}")
    return f"{media_type}:{MEDIA_TYPES[media_type]}:{external_id}"


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    """Champs vérifiés d'un titre à ajouter (rien d'autre ne passe)."""
    media_type = str(data.get("media_type") or "")
    if media_type not in MEDIA_TYPES:
        raise WatchlistError("Type inconnu (movie ou series)")
    id_field = "tmdb_id" if media_type == "movie" else "tvdb_id"
    try:
        external_id = int(data.get(id_field) or 0)
    except (TypeError, ValueError) as exc:
        raise WatchlistError(f"{id_field} invalide") from exc
    if external_id <= 0:
        raise WatchlistError(f"{id_field} requis")
    title = " ".join(str(data.get("title") or "").split())[:300]
    if not title:
        raise WatchlistError("Titre requis")
    year = data.get("year")
    try:
        year = int(year) if year not in (None, "") else None
    except (TypeError, ValueError):
        year = None
    poster = str(data.get("poster_url") or "")[:500]
    # Seulement des adresses web (une affiche, pas un chemin local)
    if poster and not poster.startswith(("http://", "https://", "/")):
        poster = ""
    return {
        "media_type": media_type,
        "id_type": MEDIA_TYPES[media_type],
        "external_id": str(external_id),
        "title": title,
        "year": year,
        "poster_url": poster,
    }


def _library_index(library: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Médiathèque indexée par clé publique (film : TMDB ; série : TVDB)."""
    index: dict[str, dict[str, Any]] = {}
    for item in library:
        ext = item.get("tmdb_id")  # séries : l'agrégateur y range l'id TVDB
        if not ext or item.get("type") not in MEDIA_TYPES:
            continue
        index[base_key(item["type"], ext)] = item
    return index


def present(row: WatchlistItem, library_item: dict[str, Any] | None) -> dict[str, Any]:
    """Ligne publique : le titre de la liste + son état dans la médiathèque."""
    lib = library_item or {}
    has_file = bool(lib.get("has_file"))
    if row.media_type == "series" and lib:
        # Série : « disponible » dès qu'au moins un épisode est sur le disque
        has_file = has_file or (lib.get("episodes_have") or 0) > 0
    return {
        "key": base_key(row.media_type, row.external_id),
        "media_type": row.media_type,
        "id_type": row.id_type,
        "external_id": row.external_id,
        "tmdb_id": int(row.external_id) if row.media_type == "movie" else None,
        "tvdb_id": int(row.external_id) if row.media_type == "series" else None,
        "title": lib.get("title") or row.title,
        "year": lib.get("year") or row.year,
        "poster_url": lib.get("poster_url") or row.poster_url or None,
        "fanart_url": lib.get("fanart_url"),
        "overview": lib.get("overview") or "",
        "in_library": bool(lib),
        "has_file": has_file,
        # Identifiant Radarr / Sonarr : ouvrir la fiche (/media/<type>/<id>)
        "media_id": lib.get("external_id"),
        "added_at": row.added_at.isoformat() if row.added_at else None,
    }


async def _library(db: AsyncSession) -> list[dict[str, Any]]:
    from app.services.media_aggregator import cached_library

    try:
        return await cached_library(db)
    except Exception:
        # Radarr / Sonarr injoignables : la liste s'affiche quand même
        return []


async def list_items(db: AsyncSession, profile_id: int | None) -> list[dict[str, Any]]:
    """Liste du profil, la plus récente d'abord."""
    stmt = select(WatchlistItem).order_by(WatchlistItem.added_at.desc(), WatchlistItem.id.desc())
    stmt = stmt.where(
        WatchlistItem.profile_id.is_(None)
        if profile_id is None
        else WatchlistItem.profile_id == profile_id
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return []
    index = _library_index(await _library(db))
    return [present(r, index.get(base_key(r.media_type, r.external_id))) for r in rows]


async def add(db: AsyncSession, profile_id: int | None, data: dict[str, Any]) -> dict[str, Any]:
    """Ajoute (ou remonte en tête) un titre dans la liste du profil."""
    if data.get("media_type") == "series" and not data.get("tvdb_id") and data.get("tmdb_id"):
        # Série venue des suggestions TMDB : la liste la repère par son id TVDB
        # (celui de Sonarr), résolu par TMDB
        from app.services.request_service import _tmdb_series_to_tvdb

        tvdb = await _tmdb_series_to_tvdb(int(data["tmdb_id"]))
        if not tvdb:
            raise WatchlistError("Série introuvable sur TVDB : impossible de l'ajouter à la liste")
        data = {**data, "tvdb_id": tvdb}
    fields = _clean(data)
    key = profiled_key(base_key(fields["media_type"], fields["external_id"]), profile_id)
    now = datetime.now(UTC)
    row = (
        (await db.execute(select(WatchlistItem).where(WatchlistItem.key == key))).scalars().first()
    )
    if row is None:
        count = len(
            (
                await db.execute(
                    select(WatchlistItem.id).where(
                        WatchlistItem.profile_id.is_(None)
                        if profile_id is None
                        else WatchlistItem.profile_id == profile_id
                    )
                )
            ).all()
        )
        if count >= MAX_ITEMS:
            raise WatchlistError(f"Liste pleine ({MAX_ITEMS} titres) : retires-en quelques-uns")
        row = WatchlistItem(key=key, profile_id=profile_id, added_at=now, **fields)
        db.add(row)
    else:
        # Déjà dans la liste : on rafraîchit son titre / affiche, et il remonte en tête
        row.title, row.year = fields["title"], fields["year"] or row.year
        row.poster_url = fields["poster_url"] or row.poster_url
        row.added_at = now
    await db.commit()
    await db.refresh(row)
    index = _library_index(await _library(db))
    return present(row, index.get(base_key(row.media_type, row.external_id)))


async def remove(
    db: AsyncSession, profile_id: int | None, media_type: str, external_id: str
) -> bool:
    key = profiled_key(base_key(media_type, external_id), profile_id)
    row = (
        (await db.execute(select(WatchlistItem).where(WatchlistItem.key == key))).scalars().first()
    )
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    return True

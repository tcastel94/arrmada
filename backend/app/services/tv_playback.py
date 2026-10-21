"""Lecture dans l'appli Android native (ADR-007).

L'appli lit le fichier d'origine stocké dans Jellyfin, sans transcodage
(« direct play »). La clé d'API Jellyfin est une clé administrateur : elle
ne quitte jamais le serveur. Le flux vidéo et les vignettes de chapitres
passent donc par ArrMada, qui relaie la requête en ajoutant la clé, comme
un reverse proxy :

    TV ──(jeton d'appareil)──▶ ArrMada ──(clé Jellyfin)──▶ Jellyfin

Ce module rassemble ce que la TV doit savoir avant de lancer la lecture
(identifiant Jellyfin, durée, chapitres, marqueurs, reprise) et ouvre le
flux relayé.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import jellyfin, watch_sync
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Identifiant d'élément Jellyfin : 32 caractères hexadécimaux (un GUID sans
# tirets). Tout le reste est refusé avant d'appeler Jellyfin : la TV ne peut
# pas glisser un autre chemin dans l'adresse relayée.
ITEM_ID = re.compile(r"^[0-9a-f]{32}$")

# En-têtes recopiés de Jellyfin vers la TV : ceux qu'un lecteur vidéo utilise
# pour l'avance rapide (Range) et la taille du fichier.
_FORWARDED = (
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "last-modified",
    "etag",
)

# Champs demandés à Jellyfin pour un élément
_FIELDS = "Chapters,Overview,MediaSources,ProviderIds"


def stream_path(item_id: str) -> str:
    return f"/api/tv/stream/{item_id}"


def chapter_image_path(item_id: str, index: int) -> str:
    return f"/api/tv/chapter-image/{item_id}/{index}"


def item_image_path(item_id: str) -> str:
    return f"/api/tv/item-image/{item_id}"


def parse_chapters(item_id: str, raw: Any) -> list[dict[str, Any]]:
    """Chapitres Jellyfin → [{index, name, start, image}] (début en secondes).

    image : adresse relayée de la vignette, ou None si Jellyfin n'en a pas
    extrait (option « Extraire les images des chapitres » de la bibliothèque).
    """
    chapters = []
    for index, chapter in enumerate(raw or []):
        if not isinstance(chapter, dict):
            continue
        try:
            start = int(chapter.get("StartPositionTicks") or 0) / jellyfin.TICKS_PER_SECOND
        except (TypeError, ValueError):
            continue
        chapters.append({
            "index": index,
            "name": str(chapter.get("Name") or f"Chapitre {index + 1}"),
            "start": round(start, 3),
            "image": chapter_image_path(item_id, index) if chapter.get("ImageTag") else None,
        })  # fmt: skip
    return chapters


def duration_seconds(item: dict[str, Any]) -> int:
    try:
        return int(int(item.get("RunTimeTicks") or 0) / jellyfin.TICKS_PER_SECOND)
    except (TypeError, ValueError):
        return 0


async def _item_details(base: str, key: str, item_id: str) -> dict[str, Any] | None:
    params = {jellyfin.KEY_PARAM: key, "ids": item_id, "fields": _FIELDS}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{base}/Items?{urlencode(params)}")
        r.raise_for_status()
        items = r.json().get("Items") or []
    return items[0] if items else None


async def _resume(db: AsyncSession, key: str) -> dict[str, Any]:
    """Reprise et « vu » partagés (les mêmes que les TV sous Kodi)."""
    from app.models.watch_state import WatchState

    row = (await db.execute(select(WatchState).where(WatchState.key == key))).scalars().first()
    if row is None:
        return {"position": 0, "watched": False}
    return {"position": int(row.position or 0), "watched": bool(row.watched)}


def _found(item_id: str, details: dict[str, Any] | None, resume: dict[str, Any]) -> dict[str, Any]:
    details = details or {}
    return {
        "status": "ok",
        "item_id": item_id,
        "title": details.get("Name"),
        "overview": details.get("Overview"),
        "duration": duration_seconds(details),
        "stream": stream_path(item_id),
        "chapters": parse_chapters(item_id, details.get("Chapters")),
        "resume": resume,
    }


async def movie(db: AsyncSession, tmdb_id: int) -> dict[str, Any]:
    """Tout ce qu'il faut pour lancer un film (TMDB)."""
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "reason": "Jellyfin non configuré"}
    base, key = cfg
    item = await jellyfin.find_movie_item(db, tmdb_id)
    if item is None:
        return {"status": "not_found", "reason": "Film absent de Jellyfin"}
    details = await _item_details(base, key, item["id"])
    resume = await _resume(db, watch_sync.state_key("movie", "tmdb", str(tmdb_id)))
    return _found(item["id"], details, resume)


async def episode(db: AsyncSession, tvdb_id: int, season: int, number: int) -> dict[str, Any]:
    """Tout ce qu'il faut pour lancer un épisode (TVDB de la série + numéros)."""
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "reason": "Jellyfin non configuré"}
    base, key = cfg
    item = await jellyfin.find_episode_item(db, tvdb_id, season, number)
    if item is None:
        return {"status": "not_found", "reason": "Épisode absent de Jellyfin"}
    details = await _item_details(base, key, item["id"])
    resume = await _resume(
        db, watch_sync.state_key("episode", "tvdb", str(tvdb_id), season, number)
    )
    result = _found(item["id"], details, resume)
    segments = await jellyfin.episode_segments(db, tvdb_id, season, number)
    result["segments"] = segments.get("segments") or []
    return result


# ── Épisodes d'une saison (écran Série) ─────────────────────────────────────


def parse_episodes(items: Any) -> list[dict[str, Any]]:
    """Épisodes Jellyfin → [{season, episode, episode_end, item_id, title,
    overview, runtime, image}] triés ; image = vignette relayée ou None."""
    episodes = []
    for it in items or []:
        if not isinstance(it, dict) or not isinstance(it.get("IndexNumber"), int):
            continue
        item_id = str(it.get("Id") or "")
        if not ITEM_ID.match(item_id):
            continue
        has_image = bool((it.get("ImageTags") or {}).get("Primary"))
        end = it.get("IndexNumberEnd")
        episodes.append({
            "season": it.get("ParentIndexNumber"),
            "episode": it["IndexNumber"],
            "episode_end": end if isinstance(end, int) else None,
            "item_id": item_id,
            "title": it.get("Name"),
            "overview": it.get("Overview"),
            "runtime": duration_seconds(it),
            "image": item_image_path(item_id) if has_image else None,
        })  # fmt: skip
    return sorted(episodes, key=lambda e: e["episode"])


async def season_episodes(db: AsyncSession, tvdb_id: int, season: int) -> dict[str, Any]:
    """Épisodes présents dans Jellyfin pour une saison : vignettes, résumés, durées.

    L'écran Série croise cette liste avec Sonarr (épisodes manquants, à
    venir) et les états vu / reprise partagés.
    """
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "episodes": []}
    base, key = cfg
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            index = await jellyfin._series_index(client, base, key)
            series_id = index.get(str(tvdb_id))
            if series_id is None:
                index = await jellyfin._series_index(client, base, key, refresh=True)
                series_id = index.get(str(tvdb_id))
            if series_id is None:
                return {"status": "ok", "found": False, "episodes": []}
            params = {
                jellyfin.KEY_PARAM: key,
                "season": season,
                "fields": "Overview",
                "enableImageTypes": "Primary",
            }
            r = await client.get(f"{base}/Shows/{series_id}/Episodes?{urlencode(params)}")
            r.raise_for_status()
            items = r.json().get("Items")
    except httpx.HTTPError as exc:
        logger.debug("Épisodes Jellyfin TVDB %s S%s : %s", tvdb_id, season, exc)
        return {"status": "error", "episodes": []}
    episodes = [e for e in parse_episodes(items) if e["season"] == season]
    return {"status": "ok", "found": True, "episodes": episodes}


# ── Relais du flux vidéo ─────────────────────────────────────────────────────


class UpstreamError(Exception):
    """Jellyfin a refusé ou n'a pas répondu (code HTTP à renvoyer à la TV)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def open_stream(
    db: AsyncSession, item_id: str, range_header: str | None
) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
    """Ouvre le fichier d'origine chez Jellyfin et le relaie morceau par morceau.

    Rend (code HTTP, en-têtes à recopier, flux d'octets). Le « Range » de la
    TV est transmis tel quel : Jellyfin répond 206 avec le morceau demandé,
    c'est ce qui rend l'avance rapide instantanée.
    """
    if not ITEM_ID.match(item_id):
        raise UpstreamError(404, "Élément inconnu")
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    url = f"{base}/Videos/{item_id}/stream?{urlencode({jellyfin.KEY_PARAM: key, 'static': 'true'})}"
    headers = {"Range": range_header} if range_header else {}

    # Pas de délai de lecture : un film en pause peut laisser la connexion
    # inactive longtemps. Délai de connexion court : Jellyfin est sur le LAN.
    client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None))
    try:
        upstream = await client.send(client.build_request("GET", url, headers=headers), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.warning("Relais vidéo %s : Jellyfin injoignable (%s)", item_id, type(exc).__name__)
        raise UpstreamError(502, "Jellyfin injoignable") from exc

    if upstream.status_code >= 400:
        status_code = upstream.status_code
        await upstream.aclose()
        await client.aclose()
        raise UpstreamError(404 if status_code == 404 else 502, f"Jellyfin a répondu {status_code}")

    forwarded = {k: v for k, v in upstream.headers.items() if k.lower() in _FORWARDED}

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            # TV qui saute ailleurs dans le film ou s'arrête : on referme
            # aussitôt la connexion vers Jellyfin.
            await upstream.aclose()
            await client.aclose()

    return upstream.status_code, forwarded, body()


async def _image(db: AsyncSession, path: str) -> tuple[bytes, str]:
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    params = {jellyfin.KEY_PARAM: key, "maxWidth": 480, "quality": 85}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}{path}?{urlencode(params)}")
    except httpx.HTTPError as exc:
        raise UpstreamError(502, "Jellyfin injoignable") from exc
    if r.status_code >= 400:
        raise UpstreamError(404, "Vignette absente")
    return r.content, r.headers.get("content-type", "image/jpeg")


async def chapter_image(db: AsyncSession, item_id: str, index: int) -> tuple[bytes, str]:
    """Vignette d'un chapitre (JPEG), relayée depuis Jellyfin."""
    if not ITEM_ID.match(item_id) or not 0 <= index <= 999:
        raise UpstreamError(404, "Vignette inconnue")
    return await _image(db, f"/Items/{item_id}/Images/Chapter/{index}")


async def item_image(db: AsyncSession, item_id: str) -> tuple[bytes, str]:
    """Image principale d'un élément (vignette d'un épisode), relayée depuis Jellyfin."""
    if not ITEM_ID.match(item_id):
        raise UpstreamError(404, "Vignette inconnue")
    return await _image(db, f"/Items/{item_id}/Images/Primary")

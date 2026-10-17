"""Media aggregator — fetches and normalises media across all *arr services.

Dernière liste connue (17/10/2026) : quand un Radarr / Sonarr ne répond pas
(conteneur arrêté, réseau Docker cassé…), la médiathèque n'est plus vidée.
Chaque service a sa dernière liste reçue, gardée en mémoire et sur disque
(`data/library-snapshot.json`, pour survivre à un redémarrage du serveur),
comme le `proxy_cache_use_stale error` d'un nginx. Elle est servie à sa place
et `library_status()` dit qui est injoignable et depuis quand (bandeau de la
web app). Tant qu'un service est en panne, un nouvel essai part en arrière-
plan toutes les 30 s, sans faire attendre les pages ; en temps normal, la
liste reste en cache 5 min comme avant.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Normalisation helpers ──────────────────────────────────────


def _cover_url(images: list[dict[str, Any]], *cover_types: str) -> str | None:
    """URL de la première image *arr dont le type figure dans ``cover_types``.

    ``remoteUrl`` (TMDB / TheTVDB / fanart.tv) est préférée à ``url`` (chemin
    servi par Radarr/Sonarr) : elle est joignable depuis n'importe quel client,
    navigateur comme Kodi, sans passer par l'API *arr.
    """
    for img in images:
        if (img.get("coverType") or "").lower() in cover_types:
            url = img.get("remoteUrl") or img.get("url")
            if url:
                return url
    return None


def _normalise_movie(raw: dict[str, Any], service_name: str) -> dict[str, Any]:
    """Normalise a Radarr movie to a unified media item."""
    size = 0
    movie_file = raw.get("movieFile") or {}
    if movie_file:
        size = movie_file.get("size", 0)
    elif raw.get("sizeOnDisk"):
        size = raw["sizeOnDisk"]

    images = raw.get("images") or []
    poster = _cover_url(images, "poster")
    clearlogo = _cover_url(images, "clearlogo", "logo", "fanartlogo")
    fanart = _cover_url(images, "fanart")

    media_info = movie_file.get("mediaInfo") or {}
    quality_obj = movie_file.get("quality", {}).get("quality", {}) if movie_file else {}

    return {
        "external_id": str(raw.get("id", "")),
        "tmdb_id": raw.get("tmdbId"),
        "title": raw.get("title", "Unknown"),
        "type": "movie",
        "year": raw.get("year"),
        "genres": raw.get("genres", []),
        "quality": quality_obj.get("name") if movie_file else None,
        "resolution": quality_obj.get("resolution") or media_info.get("resolution"),
        "video_codec": media_info.get("videoCodec"),
        "video_dynamic_range": media_info.get("videoDynamicRange")
        or media_info.get("videoDynamicRangeType"),
        "audio_codec": media_info.get("audioCodec"),
        "audio_channels": media_info.get("audioChannels"),
        "studio": raw.get("studio"),
        "size_bytes": size,
        "poster_url": poster,
        "fanart_url": fanart,
        "clearlogo_url": clearlogo,
        "source_service": service_name,
        "has_file": raw.get("hasFile", False),
        "monitored": raw.get("monitored", False),
        "status": raw.get("status", "unknown"),
        "added": raw.get("added"),
        "rating": raw.get("ratings", {}).get("tmdb", {}).get("value"),
        "runtime": raw.get("runtime"),
        "overview": raw.get("overview", ""),
        # Dossier du film côté Radarr (artworks rangés à côté : disc.png…)
        "path": raw.get("path"),
    }


def _normalise_series(
    raw: dict[str, Any], service_name: str, profile_names: dict[int, str] | None = None
) -> dict[str, Any]:
    """Normalise a Sonarr series to a unified media item.

    ``quality`` is the quality *profile name* (Sonarr has no single file
    quality per series). It used to be the raw numeric profile id, which
    showed up as a meaningless "8" badge and polluted the quality facets.
    """
    profile_id = raw.get("qualityProfileId")
    images = raw.get("images") or []
    poster = _cover_url(images, "poster")
    clearlogo = _cover_url(images, "clearlogo", "logo", "fanartlogo")
    fanart = _cover_url(images, "fanart")

    stats = raw.get("statistics") or {}

    return {
        "external_id": str(raw.get("id", "")),
        "tmdb_id": raw.get("tvdbId"),  # Sonarr uses TVDB
        "tmdb_tv_id": raw.get("tmdbId"),  # vrai TMDB (logos TMDB d'une série)
        "title": raw.get("title", "Unknown"),
        "type": "series",
        "year": raw.get("year"),
        "genres": raw.get("genres", []),
        "quality": (profile_names or {}).get(profile_id) if profile_id is not None else None,
        "network": raw.get("network"),
        "size_bytes": stats.get("sizeOnDisk", 0),
        "poster_url": poster,
        "fanart_url": fanart,
        "clearlogo_url": clearlogo,
        "source_service": service_name,
        "has_file": stats.get("episodeFileCount", 0) > 0,
        "monitored": raw.get("monitored", False),
        "status": raw.get("status", "unknown"),
        "added": raw.get("added"),
        "rating": raw.get("ratings", {}).get("value"),
        "runtime": raw.get("runtime"),
        "overview": raw.get("overview", ""),
        "seasons": raw.get("seasonCount", 0),
        "episodes_total": stats.get("totalEpisodeCount", 0),
        "episodes_have": stats.get("episodeFileCount", 0),
        # Dossier de la série côté Sonarr (poster.jpg, clearlogo.png…)
        "path": raw.get("path"),
    }


# ── Public API ─────────────────────────────────────────────────


# ── Dernière liste connue par service (voir l'en-tête du module) ──────────

SNAPSHOT_FILE = Path("data") / "library-snapshot.json"
LIBRARY_TTL = 300  # s : médiathèque en cache en temps normal
RETRY_SECONDS = 30  # s : nouvel essai en fond tant qu'un service ne répond pas
LIBRARY_TYPES = ("radarr", "sonarr")

_snapshots: dict[str, dict[str, Any]] | None = None  # id du service → dernière liste reçue
_digests: dict[str, str] = {}  # empreinte de la liste écrite sur disque (évite de réécrire)
_status: dict[int, dict[str, Any]] = {}  # id du service → dernier essai
_retry_task: asyncio.Task | None = None


def _load_snapshots() -> dict[str, dict[str, Any]]:
    """Listes gardées sur disque, lues une fois par démarrage du serveur."""
    global _snapshots
    if _snapshots is None:
        try:
            data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        _snapshots = data if isinstance(data, dict) else {}
    return _snapshots


def _write_snapshots(snapshots: dict[str, dict[str, Any]]) -> None:
    """Écriture atomique (fichier temporaire puis renommage)."""
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshots, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, SNAPSHOT_FILE)


def _digest(items: list[dict[str, Any]]) -> str:
    raw = json.dumps(items, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _short_error(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:200]


async def _fetch_service(svc: Service) -> list[dict[str, Any]]:
    """Liste normalisée d'UN service (lève une exception s'il ne répond pas)."""
    api_key = decrypt_api_key(svc.api_key)
    items: list[dict[str, Any]] = []
    if svc.type == "radarr":
        client = RadarrClient(url=svc.url, api_key=api_key)
        try:
            for m in await client.get_movies():
                items.append(_normalise_movie(m, svc.name))
        finally:
            await client.close()
    elif svc.type == "sonarr":
        client = SonarrClient(url=svc.url, api_key=api_key)
        try:
            series = await client.get_series()
            try:
                profiles = await client.get_quality_profiles()
                profile_names = {p["id"]: p.get("name", "") for p in profiles if "id" in p}
            except Exception as exc:  # profiles are cosmetic: never block the library
                logger.debug("Sonarr quality profiles unavailable: %s", exc)
                profile_names = {}
            for s in series:
                items.append(_normalise_series(s, svc.name, profile_names))
        finally:
            await client.close()
    return items


async def fetch_all_media(db: AsyncSession) -> list[dict[str, Any]]:
    """Fetch media from all connected *arr services and return unified list.

    Un service qui ne répond pas est remplacé par sa dernière liste connue
    (marquée dans `library_status()`), jamais par une liste vide.
    """
    stmt = select(Service).where(Service.is_enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    services = [svc for svc in result.scalars().all() if svc.type in LIBRARY_TYPES]

    snapshots = await asyncio.to_thread(_load_snapshots)
    now = datetime.now(UTC).isoformat()
    all_media: list[dict[str, Any]] = []
    status: dict[int, dict[str, Any]] = {}
    to_write = False

    for svc in services:
        key = str(svc.id)
        base = {"id": svc.id, "name": svc.name, "type": svc.type, "checked_at": now}
        try:
            items = await _fetch_service(svc)
        except Exception as exc:
            error = _short_error(exc)
            known = snapshots.get(key)
            if known and isinstance(known.get("items"), list):
                logger.warning(
                    "%s injoignable (%s) : dernière liste connue servie (%d titres du %s)",
                    svc.name,
                    error,
                    len(known["items"]),
                    known.get("saved_at"),
                )
                # Copie : les artworks ajoutés plus bas ne doivent pas toucher la liste gardée
                all_media.extend(copy.deepcopy(known["items"]))
            else:
                logger.error("Failed to fetch media from %s: %s", svc.name, error)
            previous = _status.get(svc.id) or {}
            status[svc.id] = {
                **base,
                "ok": False,
                "stale": bool(known),
                "error": error,
                "count": len(known["items"]) if known else 0,
                "last_ok_at": (known or {}).get("saved_at"),
                "down_since": previous.get("down_since") or now,
            }
            continue

        status[svc.id] = {
            **base,
            "ok": True,
            "stale": False,
            "error": "",
            "count": len(items),
            "last_ok_at": now,
            "down_since": None,
        }
        digest = _digest(items)
        snapshots[key] = {"name": svc.name, "type": svc.type, "saved_at": now, "items": items}
        if _digests.get(key) != digest:
            _digests[key] = digest
            to_write = True
        all_media.extend(copy.deepcopy(items))

    _status.clear()
    _status.update(status)
    if to_write:
        try:
            await asyncio.to_thread(_write_snapshots, snapshots)
        except OSError as exc:  # disque plein, droits… : la médiathèque reste servie
            logger.warning("Dernière liste connue non enregistrée : %s", exc)

    # Logos, disques, clearart… récupérés sur fanart.tv / TMDB (services/artwork.py)
    from app.services.artwork import apply_to_library

    await apply_to_library(all_media)
    return all_media


def library_degraded() -> bool:
    """Vrai si un Radarr / Sonarr n'a pas répondu au dernier essai."""
    return any(not s["ok"] for s in _status.values())


def library_status() -> dict[str, Any]:
    """État des sources de la médiathèque (bandeau de la web app)."""
    sources = sorted(_status.values(), key=lambda s: (s["type"], s["name"].lower()))
    return {"degraded": library_degraded(), "sources": [dict(s) for s in sources]}


def _retry_in_background() -> None:
    """Un seul nouvel essai à la fois, avec sa propre session de base de données."""
    global _retry_task
    if _retry_task is not None and not _retry_task.done():
        return

    async def _run() -> None:
        from app.services import artwork  # même fabrique de sessions que les tâches de fond
        from app.utils.cache import cache

        try:
            async with artwork.session_factory() as own_db:
                media = await fetch_all_media(own_db)
            cache.set("media:all", media)
        except Exception as exc:  # jamais au point de casser une requête
            logger.warning("Nouvel essai de la médiathèque échoué : %s", exc)

    _retry_task = asyncio.create_task(_run())


async def cached_library(db: AsyncSession) -> list[dict[str, Any]]:
    """Toute la médiathèque, en cache 5 min (clé « media:all »), partout la même.

    Service en panne : la liste en cache (avec la dernière liste connue du
    service) est servie tout de suite, et un nouvel essai part en fond si le
    dernier date de plus de 30 s — la page ne l'attend pas.
    """
    from app.utils.cache import cache

    age = cache.age("media:all")
    if age is not None and age > RETRY_SECONDS and library_degraded():
        _retry_in_background()

    async def _fetch() -> list[dict[str, Any]]:
        return await fetch_all_media(db)

    return list(await cache.get_or_set("media:all", _fetch, ttl_seconds=LIBRARY_TTL))


async def find_artwork(
    db: AsyncSession, media_type: str | None, tmdb_id: Any = None, title: str | None = None
) -> dict[str, str]:
    """Affiche et fond d'un titre de la médiathèque ({"poster", "fanart"}, vides si inconnu).

    Recherche par identifiant (film : TMDB ; série : TVDB, comme Sonarr), sinon
    par titre exact (casse ignorée). Ne lève jamais : un Radarr injoignable
    donne juste un écran sans image.
    """
    empty = {"poster": "", "fanart": ""}
    wanted_id = str(tmdb_id or "").strip()
    wanted_title = str(title or "").strip().casefold()
    if not wanted_id.isdigit() and not wanted_title:
        return empty
    try:
        library = await cached_library(db)
    except Exception as exc:
        logger.debug("Médiathèque indisponible pour les images : %s", exc)
        return empty
    candidates = [m for m in library if not media_type or m.get("type") == media_type]
    match = None
    if wanted_id.isdigit():
        match = next((m for m in candidates if str(m.get("tmdb_id") or "") == wanted_id), None)
    if match is None and wanted_title:
        match = next(
            (m for m in candidates if str(m.get("title") or "").casefold() == wanted_title), None
        )
    if match is None:
        return empty

    def _url(value: Any) -> str:
        text = str(value or "")
        return text if text.startswith(("http://", "https://")) else ""

    return {"poster": _url(match.get("poster_url")), "fanart": _url(match.get("fanart_url"))}


async def get_dashboard_stats(db: AsyncSession) -> dict[str, Any]:
    """Compute dashboard statistics from all services."""
    media = await fetch_all_media(db)

    movies = [m for m in media if m["type"] == "movie"]
    series = [m for m in media if m["type"] == "series"]

    total_size = sum(m.get("size_bytes") or 0 for m in media)
    movies_with_files = [m for m in movies if m.get("has_file")]
    series_with_files = [m for m in series if m.get("has_file")]

    return {
        "movies": {
            "total": len(movies),
            "with_files": len(movies_with_files),
            "monitored": len([m for m in movies if m.get("monitored")]),
        },
        "series": {
            "total": len(series),
            "with_files": len(series_with_files),
            "monitored": len([s for s in series if s.get("monitored")]),
            "total_episodes": sum(s.get("episodes_total", 0) for s in series),
            "have_episodes": sum(s.get("episodes_have", 0) for s in series),
        },
        "total_size_bytes": total_size,
        "total_items": len(media),
    }


async def search_media(query: str, db: AsyncSession) -> list[dict[str, Any]]:
    """Search across all fetched media by title."""
    media = await fetch_all_media(db)
    q = query.lower()
    return [m for m in media if q in m.get("title", "").lower()]


async def get_queue_items(db: AsyncSession) -> list[dict[str, Any]]:
    """Fetch the download queue from all Sonarr and Radarr services."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    queue_items: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "sonarr":
                client = SonarrClient(url=svc.url, api_key=api_key)
            else:
                client = RadarrClient(url=svc.url, api_key=api_key)
            try:
                data = await client.get_queue()
                records = data.get("records", []) if isinstance(data, dict) else []
                # Sonarr renvoie une ligne PAR ÉPISODE d'un pack de saison, toutes
                # avec le même downloadId et la taille du pack entier : une seule
                # carte par téléchargement, sinon 6 cartes identiques et 6 × la
                # taille dans les totaux de la page Téléchargements.
                # Clé : téléchargement + titre suivi (une collection de films
                # dans un seul torrent garde une carte par film).
                groups: dict[tuple, list[dict[str, Any]]] = {}
                for record in records:
                    media = record.get("seriesId") or record.get("movieId")
                    key = (record.get("downloadId") or f"id:{record.get('id')}", media)
                    groups.setdefault(key, []).append(record)
                for group in groups.values():
                    item = group[0]
                    queue_items.append(
                        {
                            "id": item.get("id"),
                            "title": item.get("title", "Unknown"),
                            "status": item.get("status", "unknown"),
                            "progress": _calc_progress(item),
                            "size_bytes": item.get("size", 0),
                            "size_left_bytes": item.get("sizeleft", 0),
                            "time_left": item.get("timeleft"),
                            "source_service": svc.name,
                            "service_type": svc.type,
                            "movie_id": item.get("movieId"),
                            "series_id": item.get("seriesId"),
                            "download_client": item.get("downloadClient", ""),
                            "protocol": item.get("protocol", ""),  # usenet | torrent
                            "tracked_state": item.get(
                                "trackedDownloadState", ""
                            ),  # downloading | importPending | importing | ...
                            "error": item.get("errorMessage") or "",  # real client/download error
                            "detail": next(  # first status message (e.g. why import is pending)
                                (
                                    msg
                                    for m in (item.get("statusMessages") or [])
                                    for msg in (m.get("messages") or [])
                                    if msg
                                ),
                                "",
                            ),
                            "indexer": item.get("indexer", ""),
                            "quality": item.get("quality", {}).get("quality", {}).get("name", ""),
                            # Épisodes couverts par ce téléchargement (pack de saison)
                            "episode_count": len(group) if svc.type == "sonarr" else 0,
                            "episode_ids": [r["episodeId"] for r in group if r.get("episodeId")],
                            "season_number": item.get("seasonNumber"),
                            # nzo_id SABnzbd (ou hash torrent) : clé des actions par élément
                            "download_id": item.get("downloadId") or "",
                        }
                    )
            finally:
                await client.close()
        except Exception as exc:
            logger.error("Failed to fetch queue from %s: %s", svc.name, exc)

    await _attach_queue_artwork(queue_items)
    return queue_items


async def _attach_queue_artwork(queue_items: list[dict[str, Any]]) -> None:
    """Affiche / fond / logo du film ou de la série de chaque téléchargement.

    Lus dans la médiathèque en cache (5 min) : aucun appel *arr de plus en
    temps normal. Jamais bloquant : sans médiathèque, les cartes restent sans image.

    Session À PART pour la base : le tableau de bord Kodi lit la file en
    parallèle d'autres requêtes sur la session de l'appelant, et une connexion
    PostgreSQL refuse deux requêtes simultanées.
    """
    if not queue_items:
        return
    from app.services import artwork  # même fabrique de sessions que les tâches de fond

    try:
        async with artwork.session_factory() as own_db:
            library = await cached_library(own_db)
    except Exception as exc:
        logger.debug("Médiathèque indisponible pour les images de la file : %s", exc)
        return
    by_id = {(m.get("type"), str(m.get("external_id"))): m for m in library}
    for item in queue_items:
        if item.get("movie_id"):
            media = by_id.get(("movie", str(item["movie_id"])))
        elif item.get("series_id"):
            media = by_id.get(("series", str(item["series_id"])))
        else:
            media = None
        if media:
            item["poster_url"] = media.get("poster_url")
            item["fanart_url"] = media.get("fanart_url")
            item["clearlogo_url"] = media.get("clearlogo_url")
            item["media_title"] = media.get("title")


def _calc_progress(item: dict) -> float:
    """Calculate download progress percentage."""
    size = item.get("size", 0)
    left = item.get("sizeleft", 0)
    if size <= 0:
        return 0.0
    return round(((size - left) / size) * 100, 1)

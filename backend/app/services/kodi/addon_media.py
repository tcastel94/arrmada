"""Add-on Kodi : recherche d'un média, options d'ajout et ajout dans Radarr / Sonarr."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kodi.arr_clients import _get_radarr_client, _get_sonarr_client
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


# ── Feature: Kodi Media Discovery & Interactive Release Grab ──
async def lookup_media_for_addon(
    db: AsyncSession, q: str, media_type: str = "all"
) -> list[dict[str, Any]]:
    """Lookup movies and series across Radarr/Sonarr for Kodi UI."""
    results: list[dict[str, Any]] = []

    # 1. Movies (Radarr)
    if media_type in ("all", "movie"):
        radarr = await _get_radarr_client(db)
        if radarr:
            try:
                raw_movies = await radarr.lookup_movie(q)
                for item in raw_movies[:10]:
                    images = item.get("images", [])
                    poster = next(
                        (
                            img["remoteUrl"]
                            for img in images
                            if img.get("coverType") == "poster" and img.get("remoteUrl")
                        ),
                        None,
                    )
                    arr_id = item.get("id") or 0
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "year": item.get("year"),
                            "type": "movie",
                            "tmdb_id": item.get("tmdbId"),
                            "imdb_id": item.get("imdbId"),
                            "overview": item.get("overview") or "",
                            "poster_url": poster,
                            "in_library": arr_id > 0,
                            "arr_id": arr_id or None,
                        }
                    )
            except Exception as exc:
                logger.error("Addon Radarr lookup failed: %s", exc)

    # 2. Series (Sonarr)
    if media_type in ("all", "series", "tvshow"):
        sonarr = await _get_sonarr_client(db)
        if sonarr:
            try:
                raw_series = await sonarr.lookup_series(q)
                for item in raw_series[:10]:
                    images = item.get("images", [])
                    poster = next(
                        (
                            img["remoteUrl"]
                            for img in images
                            if img.get("coverType") == "poster" and img.get("remoteUrl")
                        ),
                        None,
                    )
                    arr_id = item.get("id") or 0
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "year": item.get("year"),
                            "type": "series",
                            "tvdb_id": item.get("tvdbId"),
                            "imdb_id": item.get("imdbId"),
                            "overview": item.get("overview") or "",
                            "poster_url": poster,
                            "in_library": arr_id > 0,
                            "arr_id": arr_id or None,
                        }
                    )
            except Exception as exc:
                logger.error("Addon Sonarr lookup failed: %s", exc)

    return results


async def get_media_options_for_addon(
    db: AsyncSession, media_type: str = "movie"
) -> dict[str, Any]:
    """Get available quality profiles and root folders for media type."""
    profiles: list[dict[str, Any]] = []
    root_folders: list[dict[str, Any]] = []

    if media_type == "movie":
        radarr = await _get_radarr_client(db)
        if radarr:
            try:
                raw_p = await radarr.get_quality_profiles()
                profiles = [{"id": p["id"], "name": p["name"]} for p in raw_p]
                raw_f = await radarr.get_root_folders()
                root_folders = [
                    {"id": f.get("id"), "path": f.get("path"), "free_space": f.get("freeSpace", 0)}
                    for f in raw_f
                ]
            except Exception as exc:
                logger.error("Failed to get Radarr options: %s", exc)
    else:
        sonarr = await _get_sonarr_client(db)
        if sonarr:
            try:
                raw_p = await sonarr.get_quality_profiles()
                profiles = [{"id": p["id"], "name": p["name"]} for p in raw_p]
                raw_f = await sonarr.get_root_folders()
                root_folders = [
                    {"id": f.get("id"), "path": f.get("path"), "free_space": f.get("freeSpace", 0)}
                    for f in raw_f
                ]
            except Exception as exc:
                logger.error("Failed to get Sonarr options: %s", exc)

    # Sort profiles so our Cinema Ultra-HD profile is first by default
    def _profile_priority(p: dict) -> int:
        n = p.get("name", "").lower()
        if "👑" in p.get("name", "") or "cinema" in n:
            return 0
        if "ultra" in n:
            return 1
        if "1080" in n:
            return 2
        return 3

    profiles.sort(key=_profile_priority)
    return {"profiles": profiles, "root_folders": root_folders}


def _int_or_none(value: Any) -> int | None:
    """« 95396 », 95396 → 95396 ; vide ou illisible → None."""
    try:
        return int(value) if value not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


# Refus de Radarr / Sonarr qui viennent du NAS (dossier racine absent ou non
# inscriptible : partage démonté, disque en erreur, droits) plutôt que du titre
_FOLDER_HINTS = ("not writable", "does not exist", "root folder", "rootfolder", "permission denied")


def _arr_error(service: str, exc: Exception, what: str = "l'ajout") -> str:
    """Message lisible d'un refus de Radarr / Sonarr, affiché tel quel sur la TV.

    Un refus de validation (HTTP 400) arrive sous forme de liste
    ``[{"propertyName": "TvdbId", "errorMessage": "…"}]`` : on renvoie les
    messages, pas « Client error '400 Bad Request' for url … ». Deux cas
    fréquents sont traduits en consigne : clé API refusée (401 / 403) et
    dossier des films / séries inaccessible sur le NAS.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return (
                f"{service} refuse la clé API d'ArrMada (HTTP {code}) : recopie-la depuis "
                f"{service} › Paramètres › Général dans Réglages › Services"
            )
        try:
            body = exc.response.json()
        except ValueError:
            body = None
        messages: list[str] = []
        if isinstance(body, list):
            messages = [
                str(item["errorMessage"])
                for item in body
                if isinstance(item, dict) and item.get("errorMessage")
            ]
        elif isinstance(body, dict) and body.get("message"):
            messages = [str(body["message"])]
        if messages:
            text = " ; ".join(messages)
            if any(hint in text.lower() for hint in _FOLDER_HINTS):
                return (
                    f"{service} ne peut pas écrire dans son dossier racine (partage ou disque "
                    f"du NAS ?) : {text}"
                )[:240]
            return f"{service} refuse {what} : {text}"[:240]
        return f"{service} a répondu HTTP {code}"
    if isinstance(exc, httpx.HTTPError):
        return f"{service} injoignable ({type(exc).__name__})"
    return f"Erreur {service} : {exc}"[:240]


async def _find_series_for_addon(
    sonarr: Any, title: str, tmdb_id: int | None, tvdb_id: int | None
) -> dict[str, Any] | None:
    """Fiche Sonarr (lookup) de la série demandée depuis la TV.

    Pourquoi : les suggestions « Pour toi » viennent de TMDB et n'ont qu'un
    ID **TMDB**, alors que Sonarr est indexé sur **TVDB**. Avant, l'add-on
    envoyait ``tvdbId: null`` et Sonarr refusait l'ajout. Même chemin que
    les demandes de la web app (``request_service``) :
      1. ID TVDB fourni (recherche de l'add-on) → utilisé tel quel ;
      2. sinon ID TMDB → TVDB par TMDB (``/tv/{id}/external_ids``) ;
      3. sinon (pas de clé TMDB) → recherche par titre dans Sonarr, en
         vérifiant la correspondance (ID TMDB renvoyé par Sonarr v4, titre).
    """
    from app.services.request_service import _pick_series, _tmdb_series_to_tvdb

    tvdb = tvdb_id or (await _tmdb_series_to_tvdb(tmdb_id) if tmdb_id else None)
    if tvdb:
        results = await sonarr.lookup_series(f"tvdb:{tvdb}")
        return results[0] if results else None
    results = await sonarr.lookup_series(title)
    return _pick_series(results or [], title, None, tmdb_id)


async def add_media_for_addon(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Ajoute un film / une série à Radarr / Sonarr depuis la TV (profil et dossier choisis).

    On part toujours de la fiche renvoyée par le lookup de Radarr / Sonarr
    (titre exact, année, images), comme la web app, et un titre déjà suivi
    n'est pas une erreur : on renvoie son numéro (et on relance sa
    recherche si demandé), pour que la TV enchaîne normalement.

    Avec recherche immédiate, la demande est notée pour passer en tête de
    SABnzbd (services/tv_priority.py), sauf `"priority": false`.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)
    priority = bool(data.get("priority", True))

    media_type = data.get("type", "movie")
    title = str(data.get("title") or "")
    tmdb_id = _int_or_none(data.get("tmdb_id"))
    tvdb_id = _int_or_none(data.get("tvdb_id"))
    profile_id = _int_or_none(data.get("quality_profile_id")) or 1
    root_folder = data.get("root_folder_path")
    search_now = bool(data.get("search_now", False))

    if media_type == "movie":
        radarr = await _get_radarr_client(db)
        if not radarr:
            return {"status": "error", "message": "Radarr n'est pas configuré"}

        try:
            results = await radarr.lookup_movie(f"tmdb:{tmdb_id}" if tmdb_id else title)
            movie = results[0] if results else None
            if not movie or not movie.get("tmdbId"):
                return {"status": "error", "message": f"« {title} » introuvable dans Radarr"}
            if movie.get("id"):  # déjà dans Radarr : rien à ajouter
                if search_now:
                    await radarr.search_movie(movie["id"])
                    await tv_priority.create_request(
                        db,
                        service_type="radarr",
                        arr_id=movie["id"],
                        title=movie.get("title") or title,
                        origin=origin,
                        priority=priority,
                    )
                return {
                    "status": "ok",
                    "arr_id": movie["id"],
                    "title": movie.get("title") or title,
                    "type": "movie",
                    "already": True,
                    "message": f"« {movie.get('title') or title} » est déjà dans Radarr",
                }
            payload = {
                "title": movie.get("title") or title,
                "tmdbId": movie["tmdbId"],
                "year": movie.get("year"),
                "qualityProfileId": profile_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "addOptions": {"searchForMovie": search_now},
                "images": movie.get("images", []),
            }
            res = await radarr.add_movie(payload)
            arr_id = res.get("id")
            if search_now and arr_id:
                await tv_priority.create_request(
                    db,
                    service_type="radarr",
                    arr_id=arr_id,
                    title=payload["title"],
                    origin=origin,
                    priority=priority,
                    added=True,
                )

            await log_event(
                category="media",
                action="kodi_add_media",
                status="ok",
                source="kodi",
                media_type="movie",
                title=payload["title"],
                tmdb_id=movie["tmdbId"],
                device=origin["device_name"],
                detail=f"Ajouté via Kodi (Search={search_now})",
            )
            return {"status": "ok", "arr_id": arr_id, "title": payload["title"], "type": "movie"}
        except Exception as exc:
            logger.error("Add movie from Kodi failed: %s", exc)
            return {"status": "error", "message": _arr_error("Radarr", exc)}
        finally:
            await radarr.close()

    else:  # series
        sonarr = await _get_sonarr_client(db)
        if not sonarr:
            return {"status": "error", "message": "Sonarr n'est pas configuré"}

        try:
            series = await _find_series_for_addon(sonarr, title, tmdb_id, tvdb_id)
            if not series or not series.get("tvdbId"):
                return {
                    "status": "error",
                    "message": f"« {title} » introuvable dans Sonarr (pas d'ID TVDB)",
                }
            if series.get("id"):  # déjà suivie par Sonarr : rien à ajouter
                if search_now:
                    await sonarr.search_series(series["id"])
                    await tv_priority.create_request(
                        db,
                        service_type="sonarr",
                        arr_id=series["id"],
                        title=series.get("title") or title,
                        origin=origin,
                        priority=priority,
                    )
                return {
                    "status": "ok",
                    "arr_id": series["id"],
                    "title": series.get("title") or title,
                    "type": "series",
                    "already": True,
                    "message": f"« {series.get('title') or title} » est déjà dans Sonarr",
                }
            payload = {
                "title": series.get("title") or title,
                "tvdbId": series["tvdbId"],
                "year": series.get("year"),
                "qualityProfileId": profile_id,
                "rootFolderPath": root_folder,
                "monitored": True,
                "seasonFolder": True,
                "addOptions": {"searchForMissingEpisodes": search_now},
                "images": series.get("images", []),
            }
            res = await sonarr.add_series(payload)
            arr_id = res.get("id")
            if search_now and arr_id:
                await tv_priority.create_request(
                    db,
                    service_type="sonarr",
                    arr_id=arr_id,
                    title=payload["title"],
                    origin=origin,
                    priority=priority,
                    added=True,
                )

            await log_event(
                category="media",
                action="kodi_add_media",
                status="ok",
                source="kodi",
                media_type="series",
                title=payload["title"],
                device=origin["device_name"],
                detail=f"Ajouté via Kodi (TVDB {series['tvdbId']}, Search={search_now})",
            )
            return {"status": "ok", "arr_id": arr_id, "title": payload["title"], "type": "series"}
        except Exception as exc:
            logger.error("Add series from Kodi failed: %s", exc)
            return {"status": "error", "message": _arr_error("Sonarr", exc)}
        finally:
            await sonarr.close()

"""Add-on Kodi : liste des releases d'un média et envoi de la release choisie."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kodi.addon_media import _arr_error, _int_or_none
from app.services.kodi.arr_clients import _get_radarr_client, _get_sonarr_client
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


def _format_size(size_bytes: int | None) -> str:
    """Format bytes to human readable GB/MB."""
    if not size_bytes:
        return "0 Mo"
    gb = size_bytes / (1024 * 1024 * 1024)
    if gb >= 1.0:
        return f"{gb:.1f} Go"
    mb = size_bytes / (1024 * 1024)
    return f"{mb:.0f} Mo"


# La TV attend la liste des releases 60 s au plus (add-on) : on répond avant,
# avec un message clair, plutôt que de laisser la TV couper la connexion.
RELEASES_TIMEOUT = 55


async def _first_season(sonarr: Any, series_id: int) -> int:
    """Première saison « normale » (≥ 1) d'une série : celle qu'on cherche par défaut.

    Sonarr ne liste les releases d'une série que pour une saison (ou un
    épisode). Depuis la TV, on vient le plus souvent d'ajouter la série :
    on commence par le début. Saisons pas encore connues (série tout juste
    ajoutée, Sonarr la rafraîchit encore) : saison 1.
    """
    try:
        series = await sonarr.get_series_by_id(series_id)
    except Exception:
        return 1
    numbers = sorted(
        int(season.get("seasonNumber") or 0)
        for season in (series.get("seasons") or [])
        if int(season.get("seasonNumber") or 0) >= 1
    )
    return numbers[0] if numbers else 1


async def list_releases_for_addon(
    db: AsyncSession, media_type: str, arr_id: int, season: int | None = None
) -> dict[str, Any]:
    """Releases proposées par les indexeurs (choix manuel depuis la TV).

    Série : recherche par saison (``season``, sinon la première saison).
    Avant, l'appel sans saison plantait pour toute série.
    """
    client = await _get_radarr_client(db) if media_type == "movie" else await _get_sonarr_client(db)
    if not client:
        return {
            "status": "error",
            "message": f"{media_type.capitalize()} n'est pas configuré",
            "releases": [],
        }
    # Une recherche interactive interroge tous les indexeurs : bien plus que
    # les 10 s par défaut du client
    client.timeout = RELEASES_TIMEOUT

    try:
        if media_type == "movie":
            raw_releases = await client.get_releases(arr_id)
        else:
            season_number = season if season is not None else await _first_season(client, arr_id)
            raw_releases = await client.get_releases(arr_id, season_number)
        formatted: list[dict[str, Any]] = []

        for r in raw_releases or []:
            if not isinstance(r, dict):
                continue
            proto = (r.get("protocol") or "torrent").lower()
            quality_info = (r.get("quality") or {}).get("quality", {})
            quality_name = quality_info.get("name") or "Inconnu"
            size_bytes = r.get("size") or 0

            formatted.append(
                {
                    "guid": r.get("guid"),
                    "indexer_id": r.get("indexerId"),
                    "indexer": r.get("indexer", "Indexeur"),
                    "title": r.get("title", ""),
                    "protocol": proto,
                    "protocol_icon": "⚡ USENET"
                    if proto == "usenet"
                    else f"📥 TORRENT ({r.get('seeders', 0)} seeds)",
                    "quality": quality_name,
                    "size_bytes": size_bytes,
                    "size_human": _format_size(size_bytes),
                    "seeders": r.get("seeders", 0),
                    "rejected": bool(r.get("rejected", False)),
                    "rejections": r.get("rejections") or [],
                }
            )

        # Sort: Non-rejected first, then higher seeders/size
        formatted.sort(key=lambda x: (x["rejected"], -(x["seeders"] or 0), -(x["size_bytes"] or 0)))

        return {"status": "ok", "releases": formatted, "count": len(formatted)}
    except httpx.TimeoutException:
        logger.warning("Kodi releases search timed out (%s %s)", media_type, arr_id)
        return {
            "status": "error",
            "message": "Les indexeurs mettent trop de temps à répondre : réessaie, "
            "ou lance la recherche automatique",
            "releases": [],
        }
    except Exception as exc:
        logger.error(f"Failed to fetch releases for Kodi: {exc}", exc_info=True)
        service = "Radarr" if media_type == "movie" else "Sonarr"
        message = _arr_error(service, exc, "la recherche")
        return {"status": "error", "message": message, "releases": []}
    finally:
        await client.close()


async def grab_release_for_addon(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send grab release order to Radarr/Sonarr (SABnzbd / Torrent).

    La release choisie sur la TV passe en tête de SABnzbd
    (services/tv_priority.py), sauf `"priority": false`. `season` (facultatif)
    limite la demande à cette saison.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)

    media_type = data.get("type", "movie")
    arr_id = data.get("arr_id")
    guid = data.get("guid")
    indexer_id = data.get("indexer_id")
    release_title = data.get("release_title", "Release")
    media_title = data.get("media_title", "")

    client = await _get_radarr_client(db) if media_type == "movie" else await _get_sonarr_client(db)
    if not client:
        return {"status": "error", "message": "Client non configuré"}

    try:
        await client.grab_release(guid, indexer_id)
        season = _int_or_none(data.get("season"))
        if media_type == "movie":
            scope: dict[str, Any] = {"scope": "movie"}
        elif season is not None:
            scope = {"scope": "season", "season": season}
        else:
            scope = {"scope": "series"}
        if _int_or_none(arr_id):
            await tv_priority.create_request(
                db,
                service_type="radarr" if media_type == "movie" else "sonarr",
                arr_id=int(arr_id),
                title=media_title or release_title,
                origin=origin,
                release_title=data.get("release_title"),
                priority=bool(data.get("priority", True)),
                **scope,
            )
            # Le *arr a déjà remis la release au client : priorité posée tout de suite
            tv_priority.kick(delay=2)
        await log_event(
            category="download",
            action="kodi_grab",
            status="ok",
            source="kodi",
            media_type=media_type,
            media_id=arr_id,
            title=media_title or release_title,
            subtitle=release_title,
            device=origin["device_name"],
            detail="Release saisie manuellement depuis Kodi",
        )
        return {"status": "ok", "message": f"Téléchargement lancé pour {release_title}"}
    except Exception as exc:
        logger.error(f"Failed to grab release from Kodi: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur lors de l'envoi au client : {str(exc)}"}

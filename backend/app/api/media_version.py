"""API « version audio & qualité » d'un film / d'une série.

  GET  /api/media-version/{type}/{id}   version actuelle + état du fichier
  PUT  /api/media-version/{type}/{id}   change la version (+ recherche / remplacement)
  POST /api/media-version/bulk          même version pour une sélection

Toute la logique est dans ``app.services.media_version`` ; ce fichier ne fait
que résoudre le service Radarr/Sonarr, traduire les erreurs en messages
lisibles et journaliser l'action.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_current_user, require_admin
from app.services import media_version as mv
from app.services.trash_guides import get_trash_cache
from app.utils.cache import cache as app_cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/media-version",
    tags=["media-version"],
    dependencies=[Depends(get_current_user)],
)

MediaType = Literal["movie", "series"]
Language = Literal["vf", "multi", "vostfr", "vo"]
Quality = Literal["1080p", "2160p"]
Dub = Literal["any", "france", "quebec"]

LANGUAGE_LABELS = {"vf": "VF", "multi": "MULTi", "vostfr": "VOSTFR", "vo": "VO"}
DUB_LABELS = {"france": "VFF", "quebec": "VFQ"}


def version_label(version: dict[str, str]) -> str:
    """« VF (VFF) · 1080p » : libellé court pour le journal d'activité."""
    label = LANGUAGE_LABELS.get(version["language"], version["language"])
    if version.get("dub") in DUB_LABELS:
        label += f" ({DUB_LABELS[version['dub']]})"
    quality = "4K" if version["quality"] == "2160p" else version["quality"]
    return f"{label} · {quality}"


class VersionPayload(BaseModel):
    language: Language
    quality: Quality
    dub: Dub = "any"
    #: none = seulement le réglage · search = recherche automatique ·
    #: replace = supprime le fichier actuel puis cherche (films)
    action: Literal["none", "search", "replace"] = "none"


class BulkItem(BaseModel):
    type: MediaType
    id: int


class BulkPayload(BaseModel):
    items: list[BulkItem] = Field(min_length=1, max_length=500)
    language: Language
    #: absent = chaque titre garde sa qualité actuelle
    quality: Quality | None = None
    dub: Dub = "any"
    action: Literal["none", "search"] = "none"


async def _arr_client(media_type: str, *, timeout: int = 30) -> Any:
    """Client /api/v3 du Radarr (film) ou Sonarr (série) actif."""
    from app.database import async_session_factory
    from app.models.service import Service
    from app.services.arr_client import ArrBaseClient
    from app.services.encryption import decrypt_api_key

    target = mv.service_of(media_type)
    async with async_session_factory() as session:
        result = await session.execute(
            select(Service).where(Service.is_enabled == True, Service.type == target)  # noqa: E712
        )
        service = result.scalars().first()
    if service is None:
        name = "Radarr" if target == "radarr" else "Sonarr"
        raise HTTPException(status_code=400, detail=f"Aucun service {name} configuré.")
    client = ArrBaseClient(
        url=service.url, api_key=decrypt_api_key(service.api_key), timeout=timeout
    )
    client.API_PREFIX = "/api/v3"
    return client


async def _trash_cache() -> Any:
    """Données TRaSH, resynchronisées si elles sont périmées (24 h).

    Une panne de GitHub ne bloque pas tant qu'on a déjà des données en cache.
    """
    cache = get_trash_cache()
    if cache.is_stale:
        try:
            await cache.sync()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Synchronisation TRaSH impossible : %s", exc)
    return cache


def _fail(exc: Exception, what: str) -> HTTPException:
    if isinstance(exc, mv.VersionError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code == 404:
            return HTTPException(status_code=404, detail="Titre introuvable dans Radarr / Sonarr.")
        body = (exc.response.text or "").strip()[:300]
        logger.error("%s : HTTP %s %s", what, exc.response.status_code, body)
        return HTTPException(
            status_code=502,
            detail=f"Radarr / Sonarr a refusé l'opération (erreur {exc.response.status_code}).",
        )
    if isinstance(exc, httpx.HTTPError):
        return HTTPException(status_code=502, detail="Radarr / Sonarr est injoignable.")
    logger.error("%s : %s", what, exc, exc_info=True)
    return HTTPException(status_code=500, detail=f"{what} : {exc}")


@router.get("/{type}/{id}")
async def get_version(type: MediaType, id: int):
    """Version voulue (lue depuis le profil), versions proposables, état du fichier."""
    cache = await _trash_cache()
    client = await _arr_client(type)
    try:
        return await mv.get_state(client, cache, type, id)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc, "Lecture de la version impossible") from exc
    finally:
        await client.close()


@router.put("/{type}/{id}", dependencies=[Depends(require_admin)])
async def set_version(type: MediaType, id: int, payload: VersionPayload):
    """Change la version d'un titre ; crée le profil dans Radarr/Sonarr si besoin."""
    from app.services.activity_log import log_event

    cache = await _trash_cache()
    client = await _arr_client(type, timeout=60)
    try:
        version = mv.Version(payload.language, payload.quality, payload.dub)
        result = await mv.set_version(client, cache, type, id, version, payload.action)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc, "Changement de version impossible") from exc
    finally:
        await client.close()

    app_cache.invalidate("media:all")
    await log_event(
        category="library",
        action="version",
        media_type=type,
        media_id=id,
        subtitle=version_label(result["version"]),
        detail={"none": None, "search": "Recherche lancée", "replace": "Fichier remplacé"}[
            result["action"]
        ],
    )
    return result


@router.post("/bulk", dependencies=[Depends(require_admin)])
async def set_versions_bulk(payload: BulkPayload):
    """Même version pour une sélection de la médiathèque (films et séries mélangés)."""
    from app.services.activity_log import log_event

    cache = await _trash_cache()
    results: dict[str, Any] = {}
    for media_type in ("movie", "series"):
        ids = sorted({item.id for item in payload.items if item.type == media_type})
        if not ids:
            continue
        client = await _arr_client(media_type, timeout=60)
        try:
            results[media_type] = await mv.set_versions_bulk(
                client,
                cache,
                media_type,
                ids,
                payload.language,
                payload.quality,
                payload.dub,
                payload.action,
            )
        except Exception as exc:  # noqa: BLE001
            raise _fail(exc, "Changement de version impossible") from exc
        finally:
            await client.close()

    app_cache.invalidate("media:all")
    total = sum(r["total"] for r in results.values())
    changed = sum(r["changed"] for r in results.values())
    await log_event(
        category="library",
        action="version",
        title=f"{total} titre{'s' if total > 1 else ''}",
        subtitle=LANGUAGE_LABELS[payload.language]
        + (f" ({DUB_LABELS[payload.dub]})" if payload.dub in DUB_LABELS else ""),
        detail=f"{changed} modifié{'s' if changed > 1 else ''}",
    )
    return {
        "status": "ok",
        "total": total,
        "changed": changed,
        "searched": sum(r["searched"] for r in results.values()),
        "created_profiles": [
            p["profile_name"] for r in results.values() for p in r["profiles"] if p["created"]
        ],
        "warnings": sorted({w for r in results.values() for w in r["warnings"]}),
        "by_type": results,
    }

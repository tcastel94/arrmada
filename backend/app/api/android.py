"""Mises à jour de l'appli Android (ADR-009) : version proposée et APK.

Appareils (jeton d'appareil, réseau local ou VPN) : ``GET /update``,
``POST /update/check`` (bouton « Rechercher une mise à jour »), ``GET
/apk/{fichier}``. Web app : état du miroir et vérification immédiate.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import get_current_user, require_admin
from app.services import android_update

router = APIRouter(
    prefix="/api/android", tags=["android"], dependencies=[Depends(get_current_user)]
)


@router.get("/update")
async def update(
    version_code: int = Query(..., ge=0),
    build_type: str = Query("release", pattern="^(release|debug)$"),
) -> dict:
    """Y a-t-il plus récent que la version installée ([version_code]) pour ce type d'APK ?"""
    apk = android_update.latest(build_type)
    if apk is None or apk.version_code <= version_code:
        return {"available": False}
    return {"available": True, **apk.as_dict()}


@router.post("/update/check")
async def check_update(
    version_code: int = Query(..., ge=0),
    build_type: str = Query("release", pattern="^(release|debug)$"),
) -> dict:
    """Bouton « Rechercher une mise à jour » d'un appareil : le serveur revérifie
    d'abord la release GitHub (au plus toutes les 2 minutes, sans attendre la
    vérification horaire), puis répond comme ``GET /update``."""
    await android_update.refresh_for_device()
    return await update(version_code, build_type)


@router.get("/apk/{name}")
async def download(name: str) -> FileResponse:
    """L'APK elle-même (seules les APK du dossier, par leur nom exact)."""
    apk = android_update.find(name)
    if apk is None:
        raise HTTPException(status_code=404, detail="APK inconnue")
    return FileResponse(
        apk.path, media_type="application/vnd.android.package-archive", filename=apk.path.name
    )


@router.get("/status", dependencies=[Depends(require_admin)])
async def mirror_status() -> dict:
    """APK présentes sur le serveur et dernière vérification GitHub (web app)."""
    return {
        "apks": [apk.as_dict() for apk in android_update.local_apks()],
        "check": android_update.status(),
    }


@router.post("/refresh", dependencies=[Depends(require_admin)])
async def refresh_now() -> dict:
    """Vérifie tout de suite la release GitHub (sinon : toutes les heures)."""
    try:
        message = await android_update.refresh()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Vérification impossible : {exc}") from exc
    return {"message": message}

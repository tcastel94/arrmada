"""Caméras Eufy (via eufy-security-ws) : état, photo d'une détection, test.

  GET  /api/cameras/status          état de l'abonnement (web app)
  GET  /api/cameras/snapshot/{id}   photo d'une détection, en base64 (TV)
  POST /api/cameras/test            fausse détection, pour essayer la pop-up

La photo est servie en JSON (base64), comme les QR codes : l'add-on Kodi
l'écrit dans son cache puis l'affiche, sans que le jeton de la TV passe
dans une adresse d'image (que Kodi garderait dans ses journaux).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_admin
from app.config import settings
from app.services import eufy

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("/status", dependencies=[Depends(require_admin)])
async def camera_status() -> dict:
    bridge = eufy.bridge
    return {
        "configured": bool(settings.EUFY_WS_URL),
        "url": settings.EUFY_WS_URL,
        "connected": bool(bridge and bridge.connected),
        "detections": sorted(bridge.kinds) if bridge else [],
        "cameras": sorted(bridge.names.values()) if bridge else [],
        "last_event": bridge.last_event if bridge else None,
    }


@router.get("/snapshot/{snapshot_id}")
async def camera_snapshot(snapshot_id: int, _user: dict = Depends(get_current_user)) -> dict:
    found = eufy.bridge.snapshots.as_json(snapshot_id) if eufy.bridge else None
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo inconnue ou expirée")
    return found


@router.post("/test", dependencies=[Depends(require_admin)])
async def camera_test() -> dict:
    """Publie une fausse détection : la TV en lecture affiche la pop-up."""
    bridge = eufy.bridge or eufy.EufyBridge("", {"person"}, eufy._publish_on_bus)
    bridge.names.setdefault("TEST", "Test ArrMada")  # nom affiché sur la TV
    await bridge.publish("TEST", ("person", "Personne détectée (test)"), None, time.time())
    return {"status": "ok"}

"""Shared FastAPI dependencies."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verify_token
from app.database import get_db as _get_db

# Re-export for convenience
get_db = _get_db

# « Vu pour la dernière fois » n'est réécrit qu'au plus une fois par minute :
# une TV appelle l'API toutes les quelques secondes, inutile d'écrire autant.
_LAST_SEEN_EVERY = timedelta(minutes=1)


async def _authenticate_device(request: Request, db: AsyncSession, token: str) -> dict:
    """Jeton d'appareil (Kodi appairé) : réseau local, périmètre « TV »."""
    from app.models.device import Device
    from app.services import devices as devices_service

    client_host = request.client.host if request.client else None
    if not devices_service.is_lan_request(client_host, request.headers.get("X-Forwarded-For")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jeton d'appareil accepté seulement depuis le réseau local",
        )

    device = (
        await db.execute(
            select(Device).where(Device.token_hash == devices_service.hash_token(token))
        )
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Appareil inconnu ou révoqué : relance l'appairage sur la TV",
        )

    if not devices_service.device_may_call(request.method, request.url.path, device.kind):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action non autorisée depuis une TV (à faire dans la web app)",
        )

    payload = {
        "sub": f"device:{device.id}",
        "role": "device",
        "device_id": device.id,
        "device_name": device.name,
        "room": device.room,
        "avr_service_id": device.avr_service_id,
        "kind": device.kind,
    }
    # Profil famille qui regarde (appli Android) : « Famille » sans en-tête (ADR-008)
    from app.services import family_profiles

    profile_id, profile_name = await family_profiles.resolve(
        db, request.headers.get("X-Profile-Id")
    )
    payload["profile_id"] = profile_id
    payload["profile_name"] = profile_name
    now = datetime.now(UTC).replace(tzinfo=None)
    if device.last_seen_at is None or now - device.last_seen_at > _LAST_SEEN_EVERY:
        device.last_seen_at = now
        device.last_ip = client_host
    # Clôt la transaction tout de suite : sinon elle resterait ouverte pendant
    # toute la requête (des heures pour un flux SSE), et SQLite bloquerait
    # les écritures des autres requêtes pendant ce temps.
    await db.commit()
    return payload


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Verify JWT from Authorization header, cookie, or query param, or API key from header/param.

    Also accepts a paired device token (`X-Device-Token`, ADR-003 § 4), limited
    to the "TV" scope. Returns the decoded token payload.
    """
    from app.config import settings

    # 0a. Jeton d'appareil (Kodi appairé)
    device_token = request.headers.get("X-Device-Token")
    if device_token:
        return await _authenticate_device(request, db, device_token)

    # 0b. Try X-Api-Key header or apikey query param (add-on Kodi, scripts).
    # compare_digest : comparaison à temps constant, pour ne pas laisser
    # deviner le secret caractère par caractère via le temps de réponse.
    api_key = request.headers.get("X-Api-Key") or request.query_params.get("apikey")
    if api_key and hmac.compare_digest(api_key.encode(), settings.ARRMADA_AUTH_SECRET.encode()):
        return {"sub": "api_client", "role": "admin"}

    token: str | None = None

    # 1. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Try cookie
    if not token:
        token = request.cookies.get("arrmada_token")

    # 3. Try query param (needed for SSE EventSource which can't set headers)
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(token)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Réservé à la web app (et aux scripts à clé API) : refusé aux TV."""
    if user.get("role") == "device":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action non autorisée depuis une TV (à faire dans la web app)",
        )
    return user

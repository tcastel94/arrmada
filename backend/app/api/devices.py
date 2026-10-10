"""Appareils appairés (ADR-003 § 4 et § 6) : appairage, liste, révocation.

Routes publiques (réseau local seulement), appelées par Kodi avant d'avoir
un jeton :
  POST /api/devices/pair/start    demande un code court + un code secret
  POST /api/devices/pair/poll     « est-ce validé ? » → jeton, une seule fois
  GET  /api/devices/pair/qr/{code}.png   QR code vers la page d'appairage

Routes de la web app (administrateur) :
  POST   /api/devices/pair/confirm  valide un code : nom, pièce, ampli
  GET    /api/devices               liste (dernière activité)
  PATCH  /api/devices/{id}          renomme, change de pièce ou d'ampli
  DELETE /api/devices/{id}          révoque (le jeton cesse de marcher)

Route de l'appareil lui-même :
  GET /api/devices/me               « qui suis-je ? » (nom, pièce, ampli)
"""

# Pas de `from __future__ import annotations` ici : le décorateur de
# limitation de débit (slowapi) masquerait alors le type du corps de requête
# à FastAPI, qui le prendrait pour un paramètre d'URL (erreur 422).
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.config import settings
from app.main import limiter
from app.models.device import ROOMS, Device
from app.models.service import Service
from app.services import devices as devices_service
from app.services.devices import pairings

public_router = APIRouter(prefix="/api/devices", tags=["devices"])
router = APIRouter(prefix="/api/devices", tags=["devices"])


# ── Schémas ───────────────────────────────────────────────────


class PairStartRequest(BaseModel):
    platform: str = Field(default="", max_length=100)  # ex. « Kodi 21.1 · Android »
    # « screen » : écran d'appoint (tablette), jeton en lecture seule
    kind: str = Field(default="tv", pattern="^(tv|screen)$")


class PairPollRequest(BaseModel):
    device_code: str = Field(min_length=10, max_length=100)


class PairConfirmRequest(BaseModel):
    user_code: str = Field(min_length=4, max_length=12)
    name: str = Field(min_length=1, max_length=100)
    room: str = "salon"
    avr_service_id: int | None = None


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    room: str | None = None
    avr_service_id: int | None = None
    clear_avr: bool = False  # « aucun ampli choisi » (= le premier ampli actif)


# ── Outils ────────────────────────────────────────────────────


def _require_lan(request: Request) -> str:
    host = request.client.host if request.client else ""
    if not devices_service.is_lan_request(host, request.headers.get("X-Forwarded-For")):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Appairage possible seulement en réseau local"
        )
    return host


def web_base_url(request: Request) -> str:
    """Adresse de la web app pour les QR codes.

    `PUBLIC_WEB_URL` si elle est réglée, sinon l'adresse par laquelle Kodi
    a joint le backend, avec le port de l'interface (8420 → 3420).
    """
    if settings.PUBLIC_WEB_URL:
        return settings.PUBLIC_WEB_URL.rstrip("/")
    parts = urlsplit(str(request.base_url))
    host = parts.hostname or "localhost"
    if ":" in host:  # IPv6 littérale
        host = f"[{host}]"
    port = parts.port
    netloc = f"{host}:3420" if port in (None, 8420) else f"{host}:{port}"
    return urlunsplit((parts.scheme, netloc, "", "", "")).rstrip("/")


def _verification_url(request: Request, user_code: str) -> str:
    return f"{web_base_url(request)}/settings/kodi?pair={user_code}"


def _check_room(room: str) -> str:
    room = (room or "").strip().lower()
    if room not in ROOMS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Pièce inconnue : {room}")
    return room


async def _check_avr(db: AsyncSession, avr_service_id: int | None) -> Service | None:
    if avr_service_id is None:
        return None
    svc = await db.get(Service, avr_service_id)
    if svc is None or svc.type != "yamaha":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ampli Yamaha inconnu")
    return svc


async def _serialize(db: AsyncSession, device: Device) -> dict:
    avr = await db.get(Service, device.avr_service_id) if device.avr_service_id else None
    return {
        "id": device.id,
        "name": device.name,
        "room": device.room,
        "avr_service_id": device.avr_service_id,
        "avr_name": avr.name if avr else None,
        "kind": device.kind or "tv",
        "platform": device.platform,
        "last_ip": device.last_ip,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
    }


# ── Routes publiques (Kodi, avant appairage) ──────────────────


@public_router.post("/pair/start")
@limiter.limit("10/minute")
async def pair_start(request: Request, body: PairStartRequest) -> dict:
    """Kodi demande un appairage : code court à afficher, code secret à garder."""
    host = _require_lan(request)
    try:
        pending = pairings.start(body.platform, host, body.kind)
    except OverflowError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    return {
        "device_code": pending.device_code,
        "user_code": pending.user_code,
        "verification_url": _verification_url(request, pending.user_code),
        "qr_url": f"/api/devices/pair/qr/{pending.user_code}.png",
        "expires_in": devices_service.PAIRING_TTL_SECONDS,
        "interval": devices_service.POLL_INTERVAL_SECONDS,
    }


@public_router.post("/pair/poll")
async def pair_poll(request: Request, body: PairPollRequest) -> dict:
    """« Est-ce validé ? » Le jeton n'est remis qu'une fois, puis oublié."""
    _require_lan(request)
    pending = pairings.by_device_code(body.device_code)
    if pending is None:
        raise HTTPException(status.HTTP_410_GONE, "Code expiré : relance l'appairage")
    if pending.token is None:
        return {"status": "pending", "interval": devices_service.POLL_INTERVAL_SECONDS}
    token, device = pending.token, pending.device
    pairings.consume(body.device_code)
    return {"status": "ok", "token": token, "device": device}


# GET + HEAD, et une adresse qui finit par « .png » : Kodi interroge l'image
# en HEAD et se fie à l'extension pour reconnaître son format (sans quoi le
# QR code reste blanc sur la TV).
@public_router.api_route("/pair/qr/{code}.png", methods=["GET", "HEAD"])
async def pair_qr(request: Request, code: str) -> Response:
    """QR code de la page d'appairage, pour un code court encore valide."""
    _require_lan(request)
    pending = pairings.by_user_code(code)
    if pending is None or pending.token is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Code inconnu ou expiré")
    png = devices_service.qr_png(_verification_url(request, pending.user_code))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


# ── Web app (administrateur) ──────────────────────────────────


@router.post("/pair/confirm", dependencies=[Depends(require_admin)])
async def pair_confirm(body: PairConfirmRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Valide le code affiché par la TV : crée l'appareil et prépare son jeton."""
    pending = pairings.by_user_code(body.user_code)
    if pending is None or pending.token is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Code inconnu ou expiré : vérifie le code affiché sur la TV",
        )
    room = _check_room(body.room)
    await _check_avr(db, body.avr_service_id)

    token = devices_service.new_token()
    device = Device(
        name=body.name.strip(),
        room=room,
        avr_service_id=body.avr_service_id,
        token_hash=devices_service.hash_token(token),
        platform=pending.platform or None,
        last_ip=pending.ip or None,
        kind=pending.kind,
    )
    db.add(device)
    await db.flush()
    serialized = await _serialize(db, device)
    pending.device = serialized
    pending.token = token  # remis à Kodi à son prochain « poll »
    return {"status": "ok", "device": serialized}


@router.get("", dependencies=[Depends(require_admin)])
async def list_devices(db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (await db.execute(select(Device).order_by(Device.name))).scalars().all()
    return [await _serialize(db, d) for d in rows]


@router.get("/me")
async def me(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """L'appareil appelant (jeton d'appareil). Autre authentification : non appairé."""
    if user.get("role") != "device":
        return {"paired": False}
    device = await db.get(Device, user["device_id"])
    if device is None:  # supprimé entre-temps
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Appareil révoqué")
    return {"paired": True, **(await _serialize(db, device))}


@router.patch("/{device_id}", dependencies=[Depends(require_admin)])
async def update_device(
    device_id: int, body: DeviceUpdate, db: AsyncSession = Depends(get_db)
) -> dict:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appareil inconnu")
    if body.name is not None:
        device.name = body.name.strip()
    if body.room is not None:
        device.room = _check_room(body.room)
    if body.clear_avr:
        device.avr_service_id = None
    elif body.avr_service_id is not None:
        await _check_avr(db, body.avr_service_id)
        device.avr_service_id = body.avr_service_id
    await db.flush()
    return await _serialize(db, device)


@router.delete("/{device_id}", dependencies=[Depends(require_admin)])
async def revoke_device(device_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Révoque l'appareil : son jeton est refusé dès la requête suivante."""
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appareil inconnu")
    await db.delete(device)
    return {"status": "ok"}

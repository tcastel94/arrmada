"""Google Cast control via pychromecast.

mDNS discovery does not work from inside the bridged backend container, so we
discover by TCP-probing port 8009 across the LAN and connecting by host (which
does work). Casting hands the device a Jellyfin-transcoded HLS URL.
"""

from __future__ import annotations

import asyncio
import ipaddress
import uuid as uuidlib
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cast import CastDevice
from app.models.service import Service
from app.utils.logger import get_logger

logger = get_logger(__name__)

CAST_PORT = 8009


# ── Discovery (subnet TCP-scan + connect) ──────────────────────

async def _subnets(db: AsyncSession) -> set[str]:
    res = await db.execute(select(Service.url))
    nets: set[str] = set()
    for (url,) in res.all():
        host = urlsplit((url or "").strip() if (url or "").startswith("http") else f"http://{url}").hostname
        if not host:
            continue
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            continue
        if isinstance(ip, ipaddress.IPv4Address) and not ip.is_loopback:
            nets.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
    return nets


async def _port_open(ip: str, port: int, timeout: float = 0.6) -> bool:
    try:
        fut = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


# Devices whose name/model hint at audio-only playback (no video).
_AUDIO_HINTS = ("mini", "nest audio", "speaker", "jbl", "authentics", "sonos", "group", "soundbar")


def _is_video(name: str, model: str | None) -> bool:
    s = f"{name} {model or ''}".lower()
    return not any(h in s for h in _AUDIO_HINTS)


def _probe_uuid_sync(ip: str) -> Optional[str]:
    """Fallback: connect via pychromecast just to read the device UUID."""
    import pychromecast

    try:
        cc = pychromecast.get_chromecast_from_host(
            (ip, CAST_PORT, uuidlib.uuid4(), None, None), timeout=6
        )
        cc.wait(timeout=6)
        u = str(cc.cast_info.uuid)
        try:
            cc.disconnect()
        except Exception:
            pass
        return u
    except Exception:
        return None


async def _identify(ip: str) -> Optional[dict[str, Any]]:
    """Read a Cast device's name + uuid from its eureka_info HTTP endpoint (8008)."""
    name = ip
    model = None
    dev_uuid: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=3.5) as client:
            r = await client.get(f"http://{ip}:8008/setup/eureka_info?options=detail")
            if r.status_code == 200:
                d = r.json()
                name = d.get("name") or ip
                model = (d.get("device_info") or {}).get("model_name")
                udn = (d.get("ssdp_udn") or "").replace("uuid:", "").strip()
                if udn:
                    dev_uuid = udn
    except Exception:
        pass

    if not dev_uuid:
        dev_uuid = await asyncio.to_thread(_probe_uuid_sync, ip)
    if not dev_uuid:
        return None
    try:
        uuidlib.UUID(dev_uuid)
    except (ValueError, AttributeError):
        return None
    return {
        "uuid": dev_uuid,
        "name": name,
        "ip": ip,
        "port": CAST_PORT,
        "model": model,
        "video_capable": _is_video(name, model),
    }


async def discover(db: AsyncSession) -> list[dict[str, Any]]:
    """Scan the LAN for Cast devices and upsert them into the DB."""
    candidates: list[str] = []
    for net in await _subnets(db):
        hosts = [str(h) for h in ipaddress.ip_network(net).hosts()]
        sem = asyncio.Semaphore(64)

        async def _check(ip: str):
            async with sem:
                if await _port_open(ip, CAST_PORT):
                    candidates.append(ip)

        await asyncio.gather(*(_check(h) for h in hosts))

    # Read each open :8009 device's identity (bounded concurrency).
    results: list[dict[str, Any]] = []
    sem2 = asyncio.Semaphore(12)

    async def _resolve(ip: str):
        async with sem2:
            info = await _identify(ip)
            if info:
                results.append(info)

    await asyncio.gather(*(_resolve(ip) for ip in candidates))

    # Upsert
    for info in results:
        existing = (
            await db.execute(select(CastDevice).where(CastDevice.uuid == info["uuid"]))
        ).scalars().first()
        if existing:
            existing.name = info["name"]
            existing.ip = info["ip"]
            existing.port = info["port"]
            existing.model = info["model"]
            existing.video_capable = info["video_capable"]
            existing.last_seen = datetime.now(timezone.utc)
        else:
            db.add(
                CastDevice(
                    uuid=info["uuid"],
                    name=info["name"],
                    ip=info["ip"],
                    port=info["port"],
                    model=info["model"],
                    video_capable=info["video_capable"],
                )
            )
    await db.commit()
    return await list_devices(db)


async def list_devices(db: AsyncSession) -> list[dict[str, Any]]:
    res = await db.execute(
        select(CastDevice).where(CastDevice.is_enabled == True).order_by(CastDevice.name)  # noqa: E712
    )
    return [
        {
            "id": d.id,
            "uuid": d.uuid,
            "name": d.name,
            "ip": d.ip,
            "port": d.port,
            "model": d.model,
            "video_capable": d.video_capable,
        }
        for d in res.scalars().all()
    ]


async def _get(db: AsyncSession, device_id: int) -> Optional[CastDevice]:
    return await db.get(CastDevice, device_id)


# ── Cast + control ─────────────────────────────────────────────

def _host_tuple(d: CastDevice):
    return (d.ip, d.port, uuidlib.UUID(d.uuid), d.model, d.name)


def _cast_sync(host: tuple, url: str, content_type: str, title: str | None) -> dict[str, Any]:
    import time

    import pychromecast
    from pychromecast.config import APP_MEDIA_RECEIVER

    cc = pychromecast.get_chromecast_from_host(host, timeout=10)
    cc.wait(timeout=10)

    # Take over the device: if another app (Deezer, YouTube…) is running, quit it
    # so the Default Media Receiver launches cleanly — otherwise play_media is
    # delivered to the wrong app and silently ignored.
    try:
        current = cc.status.app_id if cc.status else None
        if current and current != APP_MEDIA_RECEIVER:
            cc.quit_app()
            time.sleep(3)
            cc.wait(timeout=6)
    except Exception:
        pass

    mc = cc.media_controller
    mc.play_media(url, content_type, title=title or "", stream_type="BUFFERED")

    state = None
    for _ in range(14):
        time.sleep(1.5)
        try:
            mc.update_status()
        except Exception:
            pass
        state = mc.status.player_state if mc.status else None
        if state in ("PLAYING", "BUFFERING"):
            break

    playing = state in ("PLAYING", "BUFFERING")
    try:
        cc.disconnect()
    except Exception:
        pass
    return {
        "status": "casting" if playing else "error",
        "player_state": state,
        "detail": None if playing else "La lecture n'a pas démarré sur l'appareil.",
    }


def _control_sync(host: tuple, action: str, value: Any) -> dict[str, Any]:
    import pychromecast

    cc = pychromecast.get_chromecast_from_host(host, timeout=8)
    cc.wait(timeout=8)
    mc = cc.media_controller
    if action in ("pause", "play", "stop"):
        # A fresh connection has no media session yet — sync it first, else the
        # media command is rejected (RequestFailed).
        try:
            mc.block_until_active(timeout=6)
        except Exception:
            pass
    if action == "pause":
        mc.pause()
    elif action == "play":
        mc.play()
    elif action == "stop":
        mc.stop()
    elif action == "quit":
        cc.quit_app()
    elif action == "volume":
        cc.set_volume(max(0.0, min(1.0, float(value))))
    elif action == "mute":
        cc.set_volume_muted(bool(value))
    else:
        try:
            cc.disconnect()
        except Exception:
            pass
        return {"status": "error", "detail": f"action inconnue: {action}"}
    try:
        cc.disconnect()
    except Exception:
        pass
    return {"status": "ok", "action": action}


def _status_sync(host: tuple) -> dict[str, Any]:
    import pychromecast

    cc = pychromecast.get_chromecast_from_host(host, timeout=8)
    cc.wait(timeout=8)
    mc = cc.media_controller
    st = mc.status
    cast_st = cc.status
    out = {
        "app": cast_st.display_name if cast_st else None,
        "player_state": st.player_state if st else None,
        "title": st.title if st else None,
        "current_time": st.current_time if st else None,
        "duration": st.duration if st else None,
        "volume_level": cast_st.volume_level if cast_st else None,
        "volume_muted": cast_st.volume_muted if cast_st else None,
    }
    try:
        cc.disconnect()
    except Exception:
        pass
    return out


async def cast_stream(db: AsyncSession, device_id: int, url: str, content_type: str, title: str | None) -> dict[str, Any]:
    d = await _get(db, device_id)
    if not d:
        return {"status": "error", "detail": "Appareil introuvable"}
    try:
        return await asyncio.to_thread(_cast_sync, _host_tuple(d), url, content_type, title)
    except Exception as exc:
        logger.error("cast to %s failed: %s", d.name, exc)
        return {"status": "error", "detail": type(exc).__name__}


async def control(db: AsyncSession, device_id: int, action: str, value: Any = None) -> dict[str, Any]:
    d = await _get(db, device_id)
    if not d:
        return {"status": "error", "detail": "Appareil introuvable"}
    try:
        return await asyncio.to_thread(_control_sync, _host_tuple(d), action, value)
    except Exception as exc:
        logger.error("cast control %s on %s failed: %s", action, d.name, exc)
        return {"status": "error", "detail": type(exc).__name__}


async def status(db: AsyncSession, device_id: int) -> dict[str, Any]:
    d = await _get(db, device_id)
    if not d:
        return {"status": "error", "detail": "Appareil introuvable"}
    try:
        return await asyncio.to_thread(_status_sync, _host_tuple(d))
    except Exception as exc:
        return {"status": "error", "detail": type(exc).__name__}


async def delete_device(db: AsyncSession, device_id: int) -> dict[str, Any]:
    d = await _get(db, device_id)
    if d:
        await db.delete(d)
        await db.commit()
    return {"status": "deleted"}

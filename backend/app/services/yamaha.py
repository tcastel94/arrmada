"""Yamaha AV receiver control via the YamahaExtendedControl (YXC) REST API.

Yamaha network AVRs (RX-A/RX-V…, MusicCast) expose a local HTTP API at
``http://<ip>/YamahaExtendedControl/v1/…`` — no auth. We drive the *main* zone
by default: power, volume (0..max_volume), mute and input.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.utils.logger import get_logger

logger = get_logger(__name__)

YXC = "/YamahaExtendedControl/v1"


def _base(url: str) -> str:
    """Normalise a stored URL to a scheme+host base (drop trailing slash/path)."""
    u = (url or "").strip().rstrip("/")
    if not u:
        return u
    if not u.startswith("http"):
        u = f"http://{u}"
    # Keep only scheme://host[:port]
    from urllib.parse import urlsplit

    p = urlsplit(u)
    return f"{p.scheme}://{p.netloc}"


async def _get(base: str, path: str, *, timeout: float = 4.0) -> dict[str, Any]:
    """GET a YXC endpoint and return the parsed JSON (raises on transport error)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{base}{YXC}{path}")
        r.raise_for_status()
        return r.json()


async def probe(ip_or_base: str, *, timeout: float = 1.5) -> dict[str, Any] | None:
    """Return device info if a Yamaha YXC device answers, else None."""
    base = _base(ip_or_base)
    try:
        info = await _get(base, "/system/getDeviceInfo", timeout=timeout)
        if info.get("response_code") == 0 and info.get("model_name"):
            return {"url": base, "model_name": info["model_name"], "device_id": info.get("device_id")}
    except Exception:
        return None
    return None


# ── Discovery ──────────────────────────────────────────────────

def _ssdp_search(timeout: float = 3.0) -> set[str]:
    """SSDP M-SEARCH → set of candidate host IPs (best-effort; may be empty)."""
    hosts: set[str] = set()
    msg = "\r\n".join(
        [
            "M-SEARCH * HTTP/1.1",
            "HOST:239.255.255.250:1900",
            'MAN:"ssdp:discover"',
            "MX:2",
            "ST:ssdp:all",
            "",
        ]
    ) + "\r\n"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(timeout)
        s.sendto(msg.encode(), ("239.255.255.250", 1900))
        import time

        start = time.monotonic()
        while time.monotonic() - start < timeout + 1:
            try:
                data, addr = s.recvfrom(2048)
            except socket.timeout:
                break
            low = data.decode(errors="ignore").lower()
            if "yamaha" in low or "mediarenderer" in low or "av_receiver" in low:
                hosts.add(addr[0])
        s.close()
    except Exception as exc:  # multicast often blocked in containers — non-fatal
        logger.info("Yamaha SSDP search unavailable: %s", exc)
    return hosts


async def _subnets_from_services(db: AsyncSession) -> set[str]:
    """Derive candidate /24 networks from the hosts of configured services."""
    from urllib.parse import urlsplit

    res = await db.execute(select(Service.url))
    nets: set[str] = set()
    for (url,) in res.all():
        host = urlsplit(_base(url or "")).hostname
        if not host:
            continue
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            continue
        if isinstance(ip, ipaddress.IPv4Address) and not ip.is_loopback:
            nets.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
    return nets


async def discover(db: AsyncSession) -> list[dict[str, Any]]:
    """Find Yamaha AVRs: SSDP first, then a bounded YXC probe of known subnets."""
    candidates: set[str] = set()

    # 1. SSDP (fast, best-effort)
    for ip in await asyncio.to_thread(_ssdp_search):
        candidates.add(ip)

    # 2. Probe the /24 of every configured service (robust, unicast HTTP)
    for net in await _subnets_from_services(db):
        for host in ipaddress.ip_network(net).hosts():
            candidates.add(str(host))

    if not candidates:
        return []

    sem = asyncio.Semaphore(48)

    async def _probe(ip: str) -> dict[str, Any] | None:
        async with sem:
            return await probe(ip, timeout=1.2)

    results = await asyncio.gather(*(_probe(ip) for ip in candidates))
    found = [r for r in results if r]
    # De-dup by URL, stable order.
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for r in sorted(found, key=lambda x: x["url"]):
        if r["url"] not in seen:
            seen.add(r["url"])
            uniq.append(r)
    return uniq


# ── Instances ──────────────────────────────────────────────────

async def _enabled(db: AsyncSession) -> list[Service]:
    res = await db.execute(
        select(Service).where(Service.type == "yamaha", Service.is_enabled == True)  # noqa: E712
    )
    # De-dup by normalised URL.
    seen: set[str] = set()
    out: list[Service] = []
    for s in res.scalars().all():
        b = _base(s.url)
        if b not in seen:
            seen.add(b)
            out.append(s)
    return out


def _pct(volume: int, max_volume: int) -> int:
    return round((volume / max_volume) * 100) if max_volume else 0


async def _zone_status(base: str, zone: str = "main") -> dict[str, Any]:
    st = await _get(base, f"/{zone}/getStatus")
    max_vol = st.get("max_volume") or 161
    vol = st.get("volume") or 0
    return {
        "power": st.get("power"),
        "volume": vol,
        "max_volume": max_vol,
        "volume_pct": _pct(vol, max_vol),
        "mute": bool(st.get("mute")),
        "input": st.get("input"),
        "actual_db": (st.get("actual_volume") or {}).get("value"),
        "sound_program": st.get("sound_program"),
    }


async def get_state(db: AsyncSession, service_id: int | None = None) -> dict[str, Any]:
    """Live state of the configured AVR(s). Returns {devices:[…]}."""
    instances = await _enabled(db)
    if service_id is not None:
        instances = [s for s in instances if s.id == service_id]

    devices: list[dict[str, Any]] = []
    for svc in instances:
        base = _base(svc.url)
        entry: dict[str, Any] = {"id": svc.id, "name": svc.name, "url": base, "online": False}
        try:
            entry.update(await _zone_status(base))
            entry["online"] = True
        except Exception as exc:
            entry["error"] = type(exc).__name__
        devices.append(entry)
    return {"devices": devices}


async def _pick(db: AsyncSession, service_id: int | None) -> Service | None:
    instances = await _enabled(db)
    if service_id is not None:
        return next((s for s in instances if s.id == service_id), None)
    return instances[0] if instances else None


async def control(
    db: AsyncSession,
    action: str,
    value: Any = None,
    service_id: int | None = None,
    zone: str = "main",
) -> dict[str, Any]:
    """Send a command to the AVR: volume | mute | power | input.

    ``volume`` accepts an absolute value (0..max_volume). ``power`` accepts
    on|standby|toggle. ``mute`` accepts a truthy/falsey value. ``input`` accepts
    an input id string.
    """
    svc = await _pick(db, service_id)
    if not svc:
        return {"status": "error", "detail": "Aucun ampli Yamaha configuré"}
    base = _base(svc.url)
    zone = zone if zone in ("main", "zone2", "zone3", "zone4") else "main"

    try:
        if action == "volume":
            vol = max(0, int(value))
            await _get(base, f"/{zone}/setVolume?volume={vol}")
        elif action == "volume_step":
            # value = +N / -N relative step
            step = int(value)
            await _get(base, f"/{zone}/setVolume?volume={'up' if step > 0 else 'down'}&step={abs(step)}")
        elif action == "mute":
            enable = "true" if value else "false"
            await _get(base, f"/{zone}/setMute?enable={enable}")
        elif action == "power":
            p = str(value or "toggle")
            if p not in ("on", "standby", "toggle"):
                p = "toggle"
            await _get(base, f"/{zone}/setPower?power={p}")
        elif action == "input":
            await _get(base, f"/{zone}/setInput?input={value}")
        else:
            return {"status": "error", "detail": f"Action inconnue: {action}"}
    except Exception as exc:
        logger.error("Yamaha control %s failed on %s: %s", action, base, exc)
        return {"status": "error", "detail": f"{type(exc).__name__}"}

    return {"status": "ok", "action": action}


async def test_connection(db: AsyncSession, service_id: int) -> dict[str, Any]:
    """Ping an AVR and read its model / status."""
    svc = await db.get(Service, service_id)
    if not svc or svc.type != "yamaha":
        return {"ok": False, "detail": "Instance introuvable"}
    base = _base(svc.url)
    try:
        info = await _get(base, "/system/getDeviceInfo")
        st = await _zone_status(base)
        return {
            "ok": True,
            "model": info.get("model_name"),
            "api_version": info.get("api_version"),
            "power": st.get("power"),
            "volume_pct": st.get("volume_pct"),
        }
    except Exception as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}"}


async def list_inputs(db: AsyncSession, service_id: int | None = None) -> list[str]:
    """Available input ids for the main zone (from getFeatures)."""
    svc = await _pick(db, service_id)
    if not svc:
        return []
    try:
        feats = await _get(_base(svc.url), "/system/getFeatures", timeout=6.0)
        main = next((z for z in feats.get("zone", []) if z.get("id") == "main"), None)
        return list(main.get("input_list", [])) if main else []
    except Exception:
        return []

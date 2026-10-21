"""Yamaha AV receiver control via the YamahaExtendedControl (YXC) REST API.

Yamaha network AVRs (RX-A/RX-V…, MusicCast) expose a local HTTP API at
``http://<ip>/YamahaExtendedControl/v1/…`` — no auth. We drive the *main* zone
by default: power, volume (0..max_volume), mute and input.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from pathlib import Path
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


# Codes d'erreur YXC : l'ampli répond HTTP 200 même quand il REFUSE une
# commande ; seul `response_code` (≠ 0) le signale.
_YXC_ERRORS = {
    1: "initialisation en cours",
    2: "erreur interne",
    3: "commande non prise en charge",
    4: "paramètre invalide",
    5: "impossible dans l'état actuel",
    6: "délai dépassé",
    99: "mise à jour du firmware en cours",
}


class YamahaError(RuntimeError):
    """L'ampli a répondu mais a refusé la commande (response_code ≠ 0)."""


# Ancien identifiant (profils déjà enregistrés) → identifiant YXC réel.
_PROGRAM_ALIASES = {"surround_decoder": "surr_decoder"}


def _program_id(program: str) -> str:
    return _PROGRAM_ALIASES.get(program, program)


async def _get(base: str, path: str, *, timeout: float = 4.0) -> dict[str, Any]:
    """GET a YXC endpoint and return the parsed JSON.

    Raises on transport errors AND when the AVR rejects the command
    (``response_code`` ≠ 0) : sans ça, une commande refusée (programme sonore
    inconnu, paramètre hors plage…) était affichée comme appliquée.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{base}{YXC}{path}")
        r.raise_for_status()
        data = r.json()
    code = data.get("response_code", 0) if isinstance(data, dict) else 0
    if code:
        reason = _YXC_ERRORS.get(code, f"code {code}")
        raise YamahaError(f"{path.split('?')[0]} : {reason}")
    return data


async def probe(ip_or_base: str, *, timeout: float = 1.5) -> dict[str, Any] | None:
    """Return device info if a Yamaha YXC device answers, else None."""
    base = _base(ip_or_base)
    try:
        info = await _get(base, "/system/getDeviceInfo", timeout=timeout)
        if info.get("response_code") == 0 and info.get("model_name"):
            return {
                "url": base,
                "model_name": info["model_name"],
                "device_id": info.get("device_id"),
            }
    except Exception:
        return None
    return None


# ── Discovery ──────────────────────────────────────────────────


def _ssdp_search(timeout: float = 3.0) -> set[str]:
    """SSDP M-SEARCH → set of candidate host IPs (best-effort; may be empty)."""
    hosts: set[str] = set()
    msg = (
        "\r\n".join(
            [
                "M-SEARCH * HTTP/1.1",
                "HOST:239.255.255.250:1900",
                'MAN:"ssdp:discover"',
                "MX:2",
                "ST:ssdp:all",
                "",
            ]
        )
        + "\r\n"
    )
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
            except TimeoutError:
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


def zone_status(st: dict[str, Any]) -> dict[str, Any]:
    """Réponse YXC `getStatus` → état exposé (web app, TV).

    Réglages « voix » et « mode nuit » (dialog_lift, dialog_level,
    adaptive_drc) : None quand l'ampli ne les a pas (la TV masque alors le
    réglage dans son menu pause).
    """
    max_vol = st.get("max_volume") or 161
    vol = st.get("volume") or 0

    def flag(key: str) -> bool | None:
        return bool(st[key]) if key in st else None

    return {
        "power": st.get("power"),
        "volume": vol,
        "max_volume": max_vol,
        "volume_pct": _pct(vol, max_vol),
        "mute": bool(st.get("mute")),
        "input": st.get("input"),
        "actual_db": (st.get("actual_volume") or {}).get("value"),
        "sound_program": st.get("sound_program"),
        "dialog_lift": st.get("dialogue_lift"),
        "dialog_level": st.get("dialogue_level"),
        "adaptive_drc": flag("adaptive_drc"),
        "enhancer": flag("enhancer"),
        "extra_bass": flag("extra_bass"),
        "subwoofer_volume": st.get("subwoofer_volume"),  # niveau du caisson (−12 à +12)
    }


async def _zone_status(base: str, zone: str = "main") -> dict[str, Any]:
    return zone_status(await _get(base, f"/{zone}/getStatus"))


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
            await _get(
                base, f"/{zone}/setVolume?volume={'up' if step > 0 else 'down'}&step={abs(step)}"
            )
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
        elif action == "sound_program":
            await _get(base, f"/{zone}/setSoundProgram?program={_program_id(str(value))}")
        elif action == "dialog_lift":
            val = max(0, min(5, int(value)))
            await _get(base, f"/{zone}/setDialogueLift?value={val}")
        elif action == "dialog_level":
            val = max(0, min(3, int(value)))
            await _get(base, f"/{zone}/setDialogueLevel?value={val}")
        elif action == "enhancer":
            enable = "true" if value else "false"
            await _get(base, f"/{zone}/setEnhancer?enable={enable}")
        elif action == "extra_bass":
            enable = "true" if value else "false"
            await _get(base, f"/{zone}/setExtraBass?enable={enable}")
        elif action == "adaptive_drc":
            enable = "true" if value else "false"
            await _get(base, f"/{zone}/setAdaptiveDrc?enable={enable}")
        elif action == "subwoofer_volume":
            val = max(-12, min(12, int(value)))
            await _get(base, f"/{zone}/setSubwooferVolume?volume={val}")
        else:
            return {"status": "error", "detail": f"Action inconnue: {action}"}
    except Exception as exc:
        logger.error("Yamaha control %s failed on %s: %s", action, base, exc)
        return {"status": "error", "detail": f"{type(exc).__name__}"}

    return {"status": "ok", "action": action}


# ── Room Audio Profiles & Automation ─────────────────────────

DEFAULT_PROFILES = {
    "salon": {
        "name": "Salon",
        # Disposition des enceintes (principales.caissons.plafond) : la TV en
        # déduit le décodage conseillé selon le son du film
        "speakers": "5.1",
        "volume_pct": 40,
        "volume_raw": 65,  # Typical YXC volume step (0..161)
        "dialog_lift": 2,
        "dialog_level": 2,
        "movie_sound_program": "surr_decoder",
        "series_sound_program": "drama",
        "music_sound_program": "2ch_stereo",
        "adaptive_drc": True,
        "enhancer": True,
        "extra_bass": False,
        "input": None,
    },
    "cinema": {
        "name": "Salle de cinéma",
        # Centrale, 2 avant, 2 surround, 2 arrière, 2 caissons, 2 Atmos
        "speakers": "7.2.2",
        "volume_pct": 60,
        "volume_raw": 95,
        "dialog_lift": 1,
        "dialog_level": 1,
        "movie_sound_program": "straight",
        "series_sound_program": "spectacle",
        "music_sound_program": "7ch_stereo",
        "adaptive_drc": False,
        "enhancer": False,
        "extra_bass": True,
        "input": None,
    },
}


# Profils persistés sur disque (volume ./data monté sur /app/data, comme la
# clé de chiffrement) : avant, ils vivaient dans le cache mémoire et
# disparaissaient à chaque redémarrage du conteneur.
_PROFILES_FILE = Path("data") / "yamaha_room_profiles.json"


def _load_profiles() -> dict[str, Any]:
    """Profils enregistrés, complétés par les valeurs par défaut."""
    profiles = {room: dict(values) for room, values in DEFAULT_PROFILES.items()}
    try:
        stored = json.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return profiles
    except (OSError, ValueError) as exc:
        logger.warning("Profils Yamaha illisibles (%s) : valeurs par défaut", exc)
        return profiles
    for room, values in (stored or {}).items():
        if isinstance(values, dict):
            profiles[room] = {**profiles.get(room, {}), **values}
    return profiles


def _write_profiles(profiles: dict[str, Any]) -> None:
    """Écriture atomique : fichier temporaire puis renommage (jamais de JSON tronqué)."""
    _PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PROFILES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_PROFILES_FILE)


async def get_room_profiles(db: AsyncSession) -> dict[str, Any]:
    """Retrieve configured room sound profiles (Salon & Salle de Cinéma)."""
    return _load_profiles()


async def save_room_profile(
    db: AsyncSession, room: str, profile_data: dict[str, Any]
) -> dict[str, Any]:
    """Save or update audio settings for a room profile."""
    profiles = _load_profiles()
    current = {**profiles.get(room, DEFAULT_PROFILES.get(room, {})), **profile_data}
    profiles[room] = current
    _write_profiles(profiles)
    return {"status": "ok", "room": room, "profile": current}


async def apply_preset(
    db: AsyncSession,
    room: str = "salon",
    media_type: str = "movie",
    audio_codec: str | None = None,
    audio_channels: int | None = None,
    service_id: int | None = None,
) -> dict[str, Any]:
    """Apply optimal sound parameters on the AVR for the specified room & media context."""
    svc = await _pick(db, service_id)
    if not svc:
        return {"status": "error", "detail": "Aucun ampli Yamaha configuré"}
    base = _base(svc.url)

    profiles = await get_room_profiles(db)
    room_key = "cinema" if "cinema" in room.lower() or "cinéma" in room.lower() else "salon"
    profile = profiles.get(room_key, DEFAULT_PROFILES["salon"])

    applied: dict[str, Any] = {"room": profile.get("name", room_key)}

    try:
        # 1. Power ON if standby
        st = await _zone_status(base)
        if st.get("power") != "on":
            await _get(base, "/main/setPower?power=on")
            applied["power"] = "on"
            await asyncio.sleep(0.5)

        # 2. Input switch if configured
        target_input = profile.get("input")
        if target_input:
            await _get(base, f"/main/setInput?input={target_input}")
            applied["input"] = target_input

        # 3. Choose Sound Program based on media type & channels
        program = profile.get("movie_sound_program", "straight")
        if media_type in ("tv", "series", "episode"):
            program = profile.get("series_sound_program", "drama")
        elif media_type in ("music", "audio", "track"):
            program = profile.get("music_sound_program", "2ch_stereo")
        elif audio_channels and audio_channels <= 2 and room_key == "salon":
            program = "surr_decoder"

        # Apply Sound Program (try, gracefully fallback if not supported)
        try:
            program = _program_id(program)
            await _get(base, f"/main/setSoundProgram?program={program}")
            applied["sound_program"] = program
        except Exception:
            logger.debug("Sound program %s not supported on %s", program, base)

        # 4. Set Volume
        vol_raw = profile.get("volume_raw")
        if vol_raw is not None:
            vol_target = max(0, min(140, int(vol_raw)))  # cap at safe volume
            await _get(base, f"/main/setVolume?volume={vol_target}")
            applied["volume"] = vol_target

        # 5. Dialogue Lift & Dialogue Level
        dialog_lift = profile.get("dialog_lift")
        if dialog_lift is not None:
            try:
                await _get(base, f"/main/setDialogueLift?value={dialog_lift}")
                applied["dialog_lift"] = dialog_lift
            except Exception:
                pass

        dialog_level = profile.get("dialog_level")
        if dialog_level is not None:
            try:
                await _get(base, f"/main/setDialogueLevel?value={dialog_level}")
                applied["dialog_level"] = dialog_level
            except Exception:
                pass

        # 6. Enhancer & Extra Bass
        if "enhancer" in profile:
            try:
                e_val = "true" if profile["enhancer"] else "false"
                await _get(base, f"/main/setEnhancer?enable={e_val}")
                applied["enhancer"] = profile["enhancer"]
            except Exception:
                pass

        if "extra_bass" in profile:
            try:
                b_val = "true" if profile["extra_bass"] else "false"
                await _get(base, f"/main/setExtraBass?enable={b_val}")
                applied["extra_bass"] = profile["extra_bass"]
            except Exception:
                pass

        # 7. Adaptive DRC (Night Mode)
        if "adaptive_drc" in profile:
            try:
                drc_val = "true" if profile["adaptive_drc"] else "false"
                await _get(base, f"/main/setAdaptiveDrc?enable={drc_val}")
                applied["adaptive_drc"] = profile["adaptive_drc"]
            except Exception:
                pass

        # Log event in activity history
        from app.services.activity_log import log_event

        await log_event(
            category="yamaha",
            action="apply_preset",
            status="ok",
            source="arrmada",
            device=svc.name,
            detail=f"Preset {profile.get('name')} appliqué ({applied.get('sound_program', '')})",
            meta=applied,
        )

        return {"status": "ok", "device": svc.name, "applied": applied}

    except Exception as exc:
        logger.error("Failed to apply Yamaha sound preset %s on %s: %s", room_key, base, exc)
        return {
            "status": "error",
            "detail": f"Échec de l'application du préréglage : {type(exc).__name__}",
        }


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

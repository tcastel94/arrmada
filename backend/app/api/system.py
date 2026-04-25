"""System Monitor API — disk space, system resources, and Kodi sessions."""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.cache import cache
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/system",
    tags=["system"],
    dependencies=[Depends(get_current_user)],
)


async def _fetch_disk_space(db: AsyncSession) -> list[dict[str, Any]]:
    """Fetch disk space from Sonarr/Radarr root folders."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type.in_(["sonarr", "radarr"]),
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    disks: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        try:
            if svc.type == "radarr":
                client = RadarrClient(url=svc.url, api_key=api_key)
            else:
                client = SonarrClient(url=svc.url, api_key=api_key)

            try:
                raw_disks = await client.get("/diskspace")
                for d in raw_disks:
                    path = d.get("path", "")
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)

                    total = d.get("totalSpace", 0)
                    free = d.get("freeSpace", 0)
                    used = total - free

                    disks.append({
                        "path": path,
                        "label": d.get("label", path.split("/")[-1] or path),
                        "total_bytes": total,
                        "free_bytes": free,
                        "used_bytes": used,
                        "total_human": format_bytes(total),
                        "free_human": format_bytes(free),
                        "used_human": format_bytes(used),
                        "usage_percent": round((used / total * 100), 1) if total > 0 else 0,
                        "source_service": svc.name,
                    })
            finally:
                await client.close()

        except Exception as exc:
            logger.error("Disk space fetch failed for %s: %s", svc.name, exc)

    disks.sort(key=lambda d: d["usage_percent"], reverse=True)
    return disks


def _get_host_resources() -> dict[str, Any]:
    """Get host CPU and memory stats from /proc (Linux only)."""
    resources: dict[str, Any] = {"available": False}

    try:
        # Memory from /proc/meminfo
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]  # value in kB
                    meminfo[key] = int(val) * 1024  # Convert to bytes

        total_mem = meminfo.get("MemTotal", 0)
        free_mem = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        used_mem = total_mem - free_mem

        resources["memory"] = {
            "total_bytes": total_mem,
            "used_bytes": used_mem,
            "free_bytes": free_mem,
            "total_human": format_bytes(total_mem),
            "used_human": format_bytes(used_mem),
            "free_human": format_bytes(free_mem),
            "usage_percent": round((used_mem / total_mem * 100), 1) if total_mem > 0 else 0,
        }

        # CPU from /proc/stat (instantaneous snapshot)
        with open("/proc/stat") as f:
            cpu_line = f.readline()  # First line = aggregate CPU
            cpu_parts = cpu_line.split()[1:]  # Skip "cpu" label
            cpu_values = [int(x) for x in cpu_parts]
            idle = cpu_values[3] if len(cpu_values) > 3 else 0
            total_cpu = sum(cpu_values)

            resources["cpu"] = {
                "idle_ticks": idle,
                "total_ticks": total_cpu,
                "cores": os.cpu_count() or 1,
            }

        # Uptime
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.readline().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            resources["uptime"] = {
                "seconds": uptime_seconds,
                "human": f"{days}d {hours}h {minutes}m",
            }

        # Load average
        with open("/proc/loadavg") as f:
            load_parts = f.readline().split()
            resources["load_average"] = {
                "1min": float(load_parts[0]),
                "5min": float(load_parts[1]),
                "15min": float(load_parts[2]),
            }

        resources["available"] = True

    except Exception as exc:
        logger.debug("Host resources not available: %s", exc)

    return resources


async def _fetch_kodi_sessions(db: AsyncSession) -> list[dict[str, Any]]:
    """Get active Kodi player sessions via JSON-RPC."""
    import httpx

    stmt = select(Service).where(Service.type == "kodi", Service.is_enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    kodis = result.scalars().all()

    sessions: list[dict[str, Any]] = []

    for kodi in kodis:
        url = f"{kodi.url}/jsonrpc"
        auth = None
        if kodi.api_key:
            creds = decrypt_api_key(kodi.api_key)
            if ":" in creds:
                auth = tuple(creds.split(":", 1))

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Get active players
                payload = {
                    "jsonrpc": "2.0",
                    "method": "Player.GetActivePlayers",
                    "id": 1,
                }
                resp = await client.post(url, json=payload, auth=auth)
                resp.raise_for_status()
                players = resp.json().get("result", [])

                for player in players:
                    player_id = player.get("playerid")
                    player_type = player.get("type", "unknown")

                    # Get current item details
                    item_payload = {
                        "jsonrpc": "2.0",
                        "method": "Player.GetItem",
                        "params": {
                            "playerid": player_id,
                            "properties": ["title", "showtitle", "season", "episode",
                                           "runtime", "thumbnail", "year", "file"],
                        },
                        "id": 2,
                    }
                    item_resp = await client.post(url, json=item_payload, auth=auth)
                    item_data = item_resp.json().get("result", {}).get("item", {})

                    # Get playback progress
                    props_payload = {
                        "jsonrpc": "2.0",
                        "method": "Player.GetProperties",
                        "params": {
                            "playerid": player_id,
                            "properties": ["time", "totaltime", "percentage", "speed"],
                        },
                        "id": 3,
                    }
                    props_resp = await client.post(url, json=props_payload, auth=auth)
                    props_data = props_resp.json().get("result", {})

                    title = item_data.get("title", "Unknown")
                    show_title = item_data.get("showtitle", "")
                    if show_title:
                        season = item_data.get("season", 0)
                        episode = item_data.get("episode", 0)
                        display_title = f"{show_title} S{season:02d}E{episode:02d} — {title}"
                    else:
                        display_title = title

                    # Format time
                    total_time = props_data.get("totaltime", {})
                    total_seconds = total_time.get("hours", 0) * 3600 + total_time.get("minutes", 0) * 60 + total_time.get("seconds", 0)
                    current_time = props_data.get("time", {})
                    current_seconds = current_time.get("hours", 0) * 3600 + current_time.get("minutes", 0) * 60 + current_time.get("seconds", 0)

                    sessions.append({
                        "instance": kodi.name,
                        "title": display_title,
                        "type": player_type,
                        "year": item_data.get("year"),
                        "progress_percent": round(props_data.get("percentage", 0), 1),
                        "is_paused": props_data.get("speed", 1) == 0,
                        "elapsed_seconds": current_seconds,
                        "total_seconds": total_seconds,
                        "thumbnail": item_data.get("thumbnail", ""),
                    })

        except Exception as exc:
            logger.debug("Kodi session fetch failed for %s: %s", kodi.name, exc)

    return sessions


@router.get("/disk")
async def get_disk_space(db: AsyncSession = Depends(get_db)):
    """Fetch disk space from all Sonarr/Radarr root folders."""
    async def _fetch():
        return await _fetch_disk_space(db)

    data = await cache.get_or_set("system:disk", _fetch, ttl_seconds=120)
    return {
        "disks": data,
        "total_used": sum(d["used_bytes"] for d in data),
        "total_free": sum(d["free_bytes"] for d in data),
        "total_capacity": sum(d["total_bytes"] for d in data),
    }


@router.get("/resources")
async def get_system_resources():
    """Fetch host CPU, memory, uptime, and load average."""
    return _get_host_resources()


@router.get("/kodi/sessions")
async def get_kodi_sessions(db: AsyncSession = Depends(get_db)):
    """Fetch active Kodi player sessions (what's playing now)."""
    sessions = await _fetch_kodi_sessions(db)
    return {"sessions": sessions, "active": len(sessions)}


@router.get("/overview")
async def system_overview(db: AsyncSession = Depends(get_db)):
    """Combined system overview: disks + resources + Kodi sessions."""
    async def _fetch_disks():
        return await _fetch_disk_space(db)

    disks = await cache.get_or_set("system:disk", _fetch_disks, ttl_seconds=120)
    resources = _get_host_resources()
    kodi_sessions = await _fetch_kodi_sessions(db)

    return {
        "disks": disks,
        "resources": resources,
        "kodi_sessions": kodi_sessions,
        "kodi_active": len(kodi_sessions),
    }

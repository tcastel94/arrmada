"""Outils du copilote (lecture) : file de téléchargement, indexeurs, journaux Docker, espace disque."""

from __future__ import annotations

import re
from typing import Any

from app.models.service import Service
from app.services import media_aggregator
from app.services.copilot.tools.args import DockerLogsArgs, NoArgs
from app.services.copilot.tools.common import (
    _capped,
    _client,
    _error,
    _fold,
    _matches,
    _per_service,
    _services,
    _words,
    session_factory,
)
from app.utils.helpers import format_bytes

_QUEUE_KEYS = (
    "title",
    "download_id",
    "service_type",
    "status",
    "tracked_state",
    "progress",
    "time_left",
    "source_service",
    "download_client",
    "protocol",
    "indexer",
    "quality",
    "error",
    "detail",
    "episode_count",
    "season_number",
    "movie_id",
    "series_id",
)


async def get_download_queue(_: NoArgs) -> dict[str, Any]:
    async with session_factory() as db:
        items = await media_aggregator.get_queue_items(db)
    queue = [
        {
            **{key: item.get(key) for key in _QUEUE_KEYS if item.get(key) not in (None, "")},
            "size": format_bytes(item.get("size_bytes")),
        }
        for item in items
    ]
    result: dict[str, Any] = {"arr_queue": _capped(queue, 60)}

    music = []
    for svc in await _services("lidarr"):
        try:
            async with _client(svc) as client:
                records = (await client.get_queue()).get("records") or []
        except Exception as exc:  # noqa: BLE001
            music.append({"service": svc.name, "error": _error(exc)})
            continue
        seen: set[str] = set()
        for record in records:
            # Une ligne par album : Lidarr peut en renvoyer une par piste
            download_id = str(record.get("downloadId") or record.get("id"))
            if download_id in seen:
                continue
            seen.add(download_id)
            size = float(record.get("size") or 0)
            left = float(record.get("sizeleft") or 0)
            item = {
                "title": record.get("title"),
                "download_id": record.get("downloadId"),
                "service_type": "lidarr",
                "artist": (record.get("artist") or {}).get("artistName"),
                "album": (record.get("album") or {}).get("title"),
                "status": record.get("status"),
                "tracked_state": record.get("trackedDownloadState"),
                "progress": round(100 * (size - left) / size) if size else None,
                "time_left": record.get("timeleft"),
                "download_client": record.get("downloadClient"),
                "error": record.get("errorMessage"),
                "detail": next(
                    (
                        msg
                        for m in record.get("statusMessages") or []
                        for msg in m.get("messages") or []
                        if msg
                    ),
                    None,
                ),
            }
            music.append({k: v for k, v in item.items() if v not in (None, "")})
    if music:
        result["lidarr_queue"] = _capped(music, 40)

    clients = []
    for svc in await _services("sabnzbd"):
        try:
            async with _client(svc) as client:
                sab_queue = await client.get_queue()
                history = await client.get_history(limit=40)
        except Exception as exc:  # noqa: BLE001
            clients.append({"service": svc.name, "error": _error(exc)})
            continue
        failed = [
            {
                "nzo_id": slot.get("nzo_id"),
                "name": slot.get("name"),
                "category": slot.get("category"),
                "fail_message": slot.get("fail_message"),
            }
            for slot in history.get("slots") or []
            if str(slot.get("status", "")).lower() == "failed"
        ]
        clients.append(
            {
                "service": svc.name,
                "paused": sab_queue.get("paused"),
                "speed": sab_queue.get("speed"),
                "size_left": sab_queue.get("sizeleft"),
                "time_left": sab_queue.get("timeleft"),
                "free_space_download_gb": sab_queue.get("diskspace1"),
                "free_space_complete_gb": sab_queue.get("diskspace2"),
                "slots": [
                    {
                        key: slot.get(key)
                        for key in (
                            "nzo_id",
                            "filename",
                            "status",
                            "percentage",
                            "priority",
                            "cat",
                            "timeleft",
                        )
                    }
                    for slot in (sab_queue.get("slots") or [])[:40]
                ],
                "recent_failures": failed[:15],
            }
        )
    if clients:
        result["sabnzbd"] = clients
    return result


async def get_indexers(_: NoArgs) -> dict[str, Any]:
    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        indexers = await client.get_indexers()
        stats = {
            row.get("indexerId"): row
            for row in (await client.get_indexer_stats()).get("indexers") or []
        }
        rows = []
        for indexer in indexers:
            row = stats.get(indexer.get("id"), {})
            queries = row.get("numberOfQueries", 0)
            failed = row.get("numberOfFailedQueries", 0)
            rows.append(
                {
                    "name": indexer.get("name"),
                    "protocol": indexer.get("protocol"),
                    "privacy": indexer.get("privacy"),
                    "enabled": indexer.get("enable"),
                    "priority": indexer.get("priority"),
                    "status_messages": [
                        m.get("message") for m in indexer.get("statusMessages") or []
                    ],
                    "queries": queries,
                    "failed_queries": failed,
                    # Pas de taux pour un indexeur jamais interrogé (0 % serait faux)
                    "query_success_percent": round((queries - failed) / queries * 100, 1)
                    if queries
                    else None,
                    "grabs": row.get("numberOfGrabs", 0),
                    "failed_grabs": row.get("numberOfFailedGrabs", 0),
                    "average_response_ms": row.get("averageResponseTime"),
                }
            )
        return {"indexers": rows}

    return await _per_service(("prowlarr",), fetch)


_DIGITS_RE = re.compile(r"\d+")


async def get_docker_logs(args: DockerLogsArgs) -> dict[str, Any]:
    from app.services import docker_logs

    async with session_factory() as db:
        entries = await docker_logs.get_aggregated_logs(db, tail=400, limit=4000)
    if not entries:
        return {
            "error": "Aucun journal lisible : le socket Docker n'est pas monté dans le conteneur "
            "ArrMada (/var/run/docker.sock), ou aucun conteneur ne correspond aux services "
            "enregistrés."
        }

    wanted_service = _fold(args.service)
    words = _words(args.search)
    levels = {"problems": {"error", "warning"}, "error": {"error"}, "warning": {"warning"}}.get(
        args.level
    )
    # Mêmes messages répétés (aux chiffres près) : une ligne, avec le compte.
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:  # du plus récent au plus ancien
        if levels and entry["level"] not in levels:
            continue
        if wanted_service and wanted_service not in _fold(
            f"{entry['service']} {entry['container']}"
        ):
            continue
        if words and not _matches(entry["message"], words):
            continue
        key = (entry["service"], entry["level"], _DIGITS_RE.sub("#", entry["message"])[:200])
        if key in grouped:
            grouped[key]["count"] += 1
            grouped[key]["first_seen"] = entry["ts"]
        else:
            grouped[key] = {
                "last_seen": entry["ts"],
                "first_seen": entry["ts"],
                "service": entry["service"],
                "level": entry["level"],
                "count": 1,
                "message": entry["message"][:600],
            }
    messages = list(grouped.values())
    return {
        "containers": sorted({entry["service"] for entry in entries}),
        "distinct_messages": len(messages),
        "messages": messages[: args.limit],
    }


async def get_disk_space(_: NoArgs) -> dict[str, Any]:
    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        disks = []
        for disk in await client.get("/diskspace"):
            total, free = disk.get("totalSpace") or 0, disk.get("freeSpace") or 0
            disks.append(
                {
                    "path": disk.get("path"),
                    "label": disk.get("label") or None,
                    "total": format_bytes(total),
                    "free": format_bytes(free),
                    "used_percent": round((total - free) / total * 100, 1) if total else None,
                }
            )
        return {"disks": disks}

    return await _per_service(("radarr", "sonarr"), fetch)

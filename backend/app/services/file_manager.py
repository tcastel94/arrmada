"""File management service — move downloads to media folders via Unraid API."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.sabnzbd import SabnzbdClient
from app.services.unraid import UnraidClient
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_sabnzbd_history(db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch SABnzbd download history with file paths and import status."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == "sabnzbd",
    )
    result = await db.execute(stmt)
    sab_service = result.scalars().first()

    if not sab_service:
        return []

    api_key = decrypt_api_key(sab_service.api_key)
    client = SabnzbdClient(url=sab_service.url, api_key=api_key)

    try:
        history = await client.get_history(limit=limit)
        slots = history.get("slots", [])

        items = []
        for slot in slots:
            status = slot.get("status", "Unknown")
            storage = slot.get("storage", "")
            path = slot.get("path", "")
            final_path = storage or path

            items.append({
                "nzo_id": slot.get("nzo_id", ""),
                "name": slot.get("name", "Unknown"),
                "status": status,
                "category": slot.get("category", "*"),
                "size_bytes": slot.get("bytes", 0),
                "size_human": slot.get("size", "0 B"),
                "completed_at": slot.get("completed"),
                "storage_path": final_path,
                "download_path": slot.get("path", ""),
                "stage_log": _parse_stage_log(slot.get("stage_log", [])),
                "fail_message": slot.get("fail_message", ""),
                "script_log": slot.get("script_log", ""),
                "has_been_moved": bool(storage and storage != path),
                "is_stuck": status == "Completed" and not storage,
            })
        return items
    finally:
        await client.close()


def _parse_stage_log(stage_log: list[dict]) -> list[dict[str, Any]]:
    """Parse SABnzbd stage_log into readable actions."""
    parsed = []
    for stage in stage_log:
        name = stage.get("name", "")
        actions = stage.get("actions", [])
        parsed.append({
            "stage": name,
            "actions": actions[:3] if actions else [],  # Limit to 3 actions per stage
        })
    return parsed


def _get_unraid_client() -> UnraidClient:
    """Build an UnraidClient from settings."""
    return UnraidClient(
        url=settings.UNRAID_URL,
        api_key=settings.UNRAID_API_KEY,
        username=settings.UNRAID_USERNAME,
        password=settings.UNRAID_PASSWORD,
    )


async def get_docker_containers(db: AsyncSession) -> list[dict[str, Any]]:
    """Get Docker containers filtered to only registered services."""
    # Fetch all registered services from DB
    stmt = select(Service).where(Service.is_enabled == True)  # noqa: E712
    result = await db.execute(stmt)
    services = list(result.scalars().all())

    if not services:
        return []

    # Build a lookup: service_type -> service record
    service_types = {svc.type.lower(): svc for svc in services}

    client = _get_unraid_client()
    try:
        all_containers = await client.get_docker_containers()
    finally:
        await client.close()

    # Filter: keep only containers whose name contains a registered service type
    matched = []
    for container in all_containers:
        container_name = container.get("name", "").lower()
        for svc_type, svc in service_types.items():
            if svc_type in container_name:
                container["service_name"] = svc.name
                container["service_type"] = svc.type
                container["service_url"] = svc.url
                matched.append(container)
                break  # Only match once per container

    return matched


async def docker_action(container_id: str, action: str) -> str:
    """Perform a Docker action (start/stop/restart) on Unraid."""
    client = _get_unraid_client()
    try:
        return await client.docker_action(container_id, action)
    finally:
        await client.close()

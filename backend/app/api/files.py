"""File Manager API — SABnzbd history, download paths, Docker, and media mover."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.file_manager import (
    get_sabnzbd_history,
    get_docker_containers,
    docker_action,
)
from app.services.media_mover import (
    get_path_mappings,
    get_stuck_downloads,
    trigger_manual_import,
)
from app.database import async_session_factory

router = APIRouter(
    prefix="/api/files",
    tags=["files"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/history")
async def sabnzbd_history(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Fetch SABnzbd download history with file paths."""
    items = await get_sabnzbd_history(db, limit=limit)
    stuck = [i for i in items if i.get("is_stuck")]
    return {
        "items": items,
        "total": len(items),
        "stuck_count": len(stuck),
    }


@router.get("/docker")
async def list_docker(db: AsyncSession = Depends(get_db)):
    """List Docker containers matching registered services."""
    containers = await get_docker_containers(db)
    return {
        "containers": containers,
        "total": len(containers),
        "running": sum(1 for c in containers if c.get("status") == "running"),
    }


class DockerActionPayload(BaseModel):
    container_id: str
    action: str  # start, stop, restart


@router.post("/docker/action")
async def run_docker_action(payload: DockerActionPayload):
    """Start/stop/restart a Docker container on Unraid."""
    result = await docker_action(payload.container_id, payload.action)
    return {"result": result, "container_id": payload.container_id, "action": payload.action}


# ── Media Mover ───────────────────────────────────────────────

@router.get("/paths")
async def nas_paths():
    """Get NAS path mappings derived from Docker volume mounts."""
    return await get_path_mappings()


@router.get("/stuck")
async def stuck_downloads(db: AsyncSession = Depends(get_db)):
    """Get completed downloads that haven't been imported yet."""
    stuck = await get_stuck_downloads(db)
    return {
        "items": stuck,
        "total": len(stuck),
    }


class ImportPayload(BaseModel):
    download_path: str
    media_type: str  # movie or series


@router.post("/import")
async def manual_import(payload: ImportPayload, db: AsyncSession = Depends(get_db)):
    """Trigger a manual import in Radarr/Sonarr for a stuck download.

    This will move the files to the proper media folder, rename them,
    and trigger Bazarr for subtitles + Jellyfin library update.
    """
    return await trigger_manual_import(db, payload.download_path, payload.media_type)


class BulkImportPayload(BaseModel):
    items: list[ImportPayload]


@router.post("/import/bulk")
async def bulk_import(
    payload: BulkImportPayload,
    background_tasks: BackgroundTasks,
):
    """Trigger manual import for multiple files in the background."""
    async def run_imports():
        import logging
        logger = logging.getLogger("app.api.files")
        
        for idx, item in enumerate(payload.items):
            try:
                logger.info("Background bulk import [%d/%d]: %s (%s)", idx + 1, len(payload.items), item.download_path, item.media_type)
                async with async_session_factory() as db:
                    await trigger_manual_import(db, item.download_path, item.media_type)
            except Exception as exc:
                logger.error("Failed background bulk import for %s: %s", item.download_path, exc)

    background_tasks.add_task(run_imports)
    return {"success": True, "message": f"Importation en arrière-plan démarrée pour {len(payload.items)} fichiers !"}


@router.get("/auto-import/reports")
async def get_auto_import_reports():
    """Get the 10 most recent auto-import execution reports."""
    from app.services.auto_import_reports import get_reports
    return get_reports()

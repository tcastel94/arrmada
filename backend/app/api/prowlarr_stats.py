"""Prowlarr Stats API — indexer performance analytics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.prowlarr import ProwlarrClient
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/prowlarr",
    tags=["prowlarr"],
    dependencies=[Depends(get_current_user)],
)


async def _fetch_prowlarr_stats(db: AsyncSession) -> dict[str, Any]:
    """Fetch indexer stats from all Prowlarr instances."""
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == "prowlarr",
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    all_indexers: list[dict[str, Any]] = []
    all_stats: list[dict[str, Any]] = []

    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        client = ProwlarrClient(url=svc.url, api_key=api_key)
        try:
            # Fetch indexer list
            indexers = await client.get_indexers()
            for idx in indexers:
                all_indexers.append({
                    "id": idx.get("id"),
                    "name": idx.get("name", "Unknown"),
                    "protocol": idx.get("protocol", "unknown"),
                    "privacy": idx.get("privacy", "unknown"),
                    "enable": idx.get("enable", False),
                    "status_messages": idx.get("statusMessages", []),
                    "priority": idx.get("priority", 25),
                    "tags": idx.get("tags", []),
                    "source": svc.name,
                })

            # Fetch stats
            stats = await client.get_indexer_stats()
            indexer_stats = stats.get("indexers", [])

            for s in indexer_stats:
                total_queries = s.get("numberOfQueries", 0)
                total_grabs = s.get("numberOfGrabs", 0)
                failed_queries = s.get("numberOfFailedQueries", 0)
                failed_grabs = s.get("numberOfFailedGrabs", 0)

                success_rate = 0
                if total_queries > 0:
                    success_rate = round(((total_queries - failed_queries) / total_queries) * 100, 1)

                grab_rate = 0
                if total_grabs > 0:
                    grab_rate = round(((total_grabs - failed_grabs) / total_grabs) * 100, 1)

                # Find matching indexer name
                indexer_name = s.get("indexerName", "Unknown")

                all_stats.append({
                    "indexer_id": s.get("indexerId"),
                    "indexer_name": indexer_name,
                    "queries": total_queries,
                    "grabs": total_grabs,
                    "failed_queries": failed_queries,
                    "failed_grabs": failed_grabs,
                    "success_rate": success_rate,
                    "grab_rate": grab_rate,
                    "avg_response_time": s.get("averageResponseTime", 0),
                    "source": svc.name,
                })

        except Exception as exc:
            logger.error("Prowlarr stats fetch failed for %s: %s", svc.name, exc)
        finally:
            await client.close()

    # Sort by success rate (worst first = needs attention)
    all_stats.sort(key=lambda s: s["success_rate"])

    # Compute aggregates
    total_queries = sum(s["queries"] for s in all_stats)
    total_grabs = sum(s["grabs"] for s in all_stats)
    total_failed = sum(s["failed_queries"] for s in all_stats)
    avg_success = round(
        ((total_queries - total_failed) / total_queries * 100) if total_queries > 0 else 0,
        1,
    )

    return {
        "indexers": all_indexers,
        "stats": all_stats,
        "summary": {
            "total_indexers": len(all_indexers),
            "enabled_indexers": len([i for i in all_indexers if i.get("enable")]),
            "total_queries": total_queries,
            "total_grabs": total_grabs,
            "total_failed_queries": total_failed,
            "average_success_rate": avg_success,
            "problematic": [s for s in all_stats if s["success_rate"] < 80],
        },
    }


@router.get("/stats")
async def get_prowlarr_stats(db: AsyncSession = Depends(get_db)):
    """Fetch indexer statistics from Prowlarr."""
    async def _fetch():
        return await _fetch_prowlarr_stats(db)

    return await cache.get_or_set("prowlarr:stats", _fetch, ttl_seconds=600)


@router.get("/indexers")
async def get_prowlarr_indexers(db: AsyncSession = Depends(get_db)):
    """Fetch all configured indexers from Prowlarr."""
    data = await get_prowlarr_stats(db)
    return {"indexers": data.get("indexers", [])}


# ── Indexer management (test / enable-disable / delete) ───────

async def _get_prowlarr_client_for_indexer(db: AsyncSession, indexer_id: int) -> ProwlarrClient:
    """Resolve the enabled Prowlarr client that owns the given indexer.

    Iterates enabled Prowlarr instances and returns the first one that
    actually has an indexer with this ID (supports multi-instance setups).
    """
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == "prowlarr",
    )
    result = await db.execute(stmt)
    services = result.scalars().all()

    if not services:
        raise HTTPException(status_code=400, detail="No Prowlarr service configured")

    fallback: ProwlarrClient | None = None
    for svc in services:
        api_key = decrypt_api_key(svc.api_key)
        client = ProwlarrClient(url=svc.url, api_key=api_key, timeout=60)
        try:
            await client.get_indexer(indexer_id)
            return client
        except Exception:
            if fallback is None:
                fallback = client
            else:
                await client.close()

    if fallback is not None:
        return fallback
    raise HTTPException(status_code=404, detail=f"Indexer {indexer_id} not found")


class IndexerTogglePayload(BaseModel):
    enable: bool


@router.post("/indexers/{indexer_id}/test")
async def test_prowlarr_indexer(indexer_id: int, db: AsyncSession = Depends(get_db)):
    """Test connectivity/credentials of an existing indexer."""
    client = await _get_prowlarr_client_for_indexer(db, indexer_id)
    try:
        return await client.test_indexer(indexer_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to test indexer %d: %s", indexer_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


@router.patch("/indexers/{indexer_id}")
async def toggle_prowlarr_indexer(
    indexer_id: int,
    payload: IndexerTogglePayload,
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an indexer."""
    client = await _get_prowlarr_client_for_indexer(db, indexer_id)
    try:
        updated = await client.toggle_indexer(indexer_id, payload.enable)
        cache.invalidate("prowlarr:stats")
        return {"status": "updated", "id": indexer_id, "enable": updated.get("enable", payload.enable)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to toggle indexer %d: %s", indexer_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()


@router.delete("/indexers/{indexer_id}")
async def delete_prowlarr_indexer(indexer_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an indexer from Prowlarr."""
    client = await _get_prowlarr_client_for_indexer(db, indexer_id)
    try:
        await client.delete_indexer(indexer_id)
        cache.invalidate("prowlarr:stats")
        return {"status": "deleted", "id": indexer_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete indexer %d: %s", indexer_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await client.close()

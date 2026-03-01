"""Search API — unified search across Prowlarr indexers and local library."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.media_aggregator import search_media
from app.services.prowlarr import ProwlarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/search",
    tags=["search"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def unified_search(
    q: str = Query(..., min_length=2, description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """Search across local library and Prowlarr indexers."""
    # 1. Local library search
    local_results = await search_media(q, db)

    # 2. Prowlarr indexer search
    indexer_results: list[dict[str, Any]] = []
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == "prowlarr",
    )
    result = await db.execute(stmt)
    prowlarr_services = result.scalars().all()

    for svc in prowlarr_services:
        api_key = decrypt_api_key(svc.api_key)
        client = ProwlarrClient(url=svc.url, api_key=api_key)
        try:
            raw_results = await client.search(q)
            for r in raw_results[:30]:
                indexer_results.append({
                    "title": r.get("title", "Unknown"),
                    "indexer": r.get("indexer", "Unknown"),
                    "size_bytes": r.get("size", 0),
                    "seeders": r.get("seeders", 0),
                    "leechers": r.get("leechers", 0),
                    "age_days": r.get("age", 0),
                    "download_url": r.get("downloadUrl"),
                    "info_url": r.get("infoUrl"),
                    "categories": [c.get("name", "") for c in r.get("categories", [])],
                    "protocol": r.get("protocol", "unknown"),
                })
        except Exception as exc:
            logger.error("Prowlarr search failed for %s: %s", svc.name, exc)
        finally:
            await client.close()

    return {
        "query": q,
        "library": {
            "items": local_results[:20],
            "total": len(local_results),
        },
        "indexers": {
            "items": indexer_results,
            "total": len(indexer_results),
        },
    }

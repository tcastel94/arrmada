"""Activity timeline API — unified, persisted + live audit feed.

Merges:
  • persisted Arrmada events (playback, subtitles, searches, grabs, adds…)
  • the live Radarr/Sonarr history feed (grabs / imports / failures / deletes)

Supports filtering by category/status/source/media and an optional
grouping-by-média view.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import media_aggregator
from app.services.activity_log import log_event, query_events, to_dict
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/activity",
    tags=["activity"],
    dependencies=[Depends(get_current_user)],
)


def _split(v: Optional[str]) -> Optional[list[str]]:
    if not v:
        return None
    return [p.strip() for p in v.split(",") if p.strip()]


def _arr_status(s: str) -> str:
    return {"success": "ok", "error": "ko"}.get(s, "info")


def _arr_to_unified(it: Any) -> dict[str, Any]:
    """Map a dashboard ActivityItem (Radarr/Sonarr history) to a timeline item."""
    category = "download" if it.icon_type in ("grab", "import", "fail") else "library"
    detail_bits = [b for b in (it.indexer, it.download_client, it.languages) if b]
    return {
        "id": f"arr-{it.id}",
        "ts": (it.timestamp or 0) // 1000,  # *arr history is ms → normalise to seconds
        "category": category,
        "action": it.event_type,
        "status": _arr_status(it.status),
        "source": it.source,
        "media_type": None,
        "media_id": None,
        "tmdb_id": None,
        "title": it.title,
        "subtitle": it.subtitle,
        "detail": " · ".join(detail_bits) or None,
        "duration_ms": None,
        "device": None,
        "size_bytes": it.size_bytes,
        "poster_url": it.poster_url,
    }


def _group_key(item: dict[str, Any]) -> str:
    if item.get("tmdb_id"):
        return f"tmdb:{item['tmdb_id']}"
    if item.get("media_type") and item.get("media_id"):
        return f"{item['media_type']}:{item['media_id']}"
    t = (item.get("title") or "").strip().lower()
    return f"title:{t}" if t else "misc"


@router.get("/timeline")
async def timeline(
    categories: str | None = Query(None, description="Comma list: download,subtitle,playback,library,telegram,system"),
    statuses: str | None = Query(None, description="Comma list: ok,ko,info"),
    source: str | None = Query(None),
    media_type: str | None = Query(None),
    media_id: str | None = Query(None),
    tmdb_id: int | None = Query(None),
    search: str | None = Query(None),
    group: str = Query("none", description="none | media"),
    include_arr: bool = Query(True, description="Merge the live *arr history feed"),
    limit: int = Query(150, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Unified activity timeline (persisted events + live *arr history)."""
    cat_list = _split(categories)
    st_list = _split(statuses)

    # 1. Persisted Arrmada events
    events = await query_events(
        db,
        categories=cat_list,
        statuses=st_list,
        media_type=media_type,
        media_id=media_id,
        tmdb_id=tmdb_id,
        search=search,
        limit=limit,
    )
    items: list[dict[str, Any]] = [to_dict(e) for e in events]

    # 2. Live *arr history (grabs / imports / failures / renames / deletes)
    if include_arr and (not cat_list or "download" in cat_list or "library" in cat_list):
        try:
            from app.api.activity import get_activity

            feed = await get_activity(limit=min(limit, 100), db=db)
            for it in feed.items:
                u = _arr_to_unified(it)
                if cat_list and u["category"] not in cat_list:
                    continue
                if st_list and u["status"] not in st_list:
                    continue
                if source and u["source"] != source:
                    continue
                if search and search.lower() not in (u["title"] or "").lower():
                    continue
                items.append(u)
        except Exception as exc:
            logger.warning("timeline: *arr history merge failed: %s", exc)

    # 3. Enrich (title/poster) from the media library
    try:
        media = list(
            await cache.get_or_set(
                "media:all", lambda: media_aggregator.fetch_all_media(db), ttl_seconds=300
            )
        )
        by_key = {(m["type"], str(m["external_id"])): m for m in media}
        by_tmdb = {m["tmdb_id"]: m for m in media if m.get("tmdb_id")}
        for it in items:
            m = None
            if it.get("media_type") and it.get("media_id"):
                m = by_key.get((it["media_type"], str(it["media_id"])))
            if not m and it.get("tmdb_id"):
                m = by_tmdb.get(it["tmdb_id"])
            if m:
                if not it.get("title"):
                    it["title"] = m.get("title")
                if not it.get("poster_url"):
                    it["poster_url"] = m.get("poster_url")
                if not it.get("tmdb_id"):
                    it["tmdb_id"] = m.get("tmdb_id")
    except Exception as exc:
        logger.debug("timeline enrich skipped: %s", exc)

    # 4. Sort + trim
    items.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    items = items[:limit]

    if group != "media":
        return {"items": items, "total": len(items), "grouped": False}

    # 5. Group by média
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for it in items:
        k = _group_key(it)
        g = groups.get(k)
        if not g:
            g = {
                "key": k,
                "title": it.get("title") or "Divers",
                "media_type": it.get("media_type"),
                "media_id": it.get("media_id"),
                "tmdb_id": it.get("tmdb_id"),
                "poster_url": it.get("poster_url"),
                "items": [],
                "last_ts": 0,
            }
            groups[k] = g
            order.append(k)
        g["items"].append(it)
        if not g["poster_url"] and it.get("poster_url"):
            g["poster_url"] = it["poster_url"]
        g["last_ts"] = max(g["last_ts"], it.get("ts") or 0)

    grouped = sorted(groups.values(), key=lambda g: g["last_ts"], reverse=True)
    for g in grouped:
        g["count"] = len(g["items"])
    return {"groups": grouped, "total": len(items), "grouped": True}


@router.post("/ingest")
async def ingest(data: dict, _user=Depends(get_current_user)):
    """Ingest an external event (e.g. the Telegram bot logging an add).

    Body: {category, action, status?, source?, media_type?, media_id?, tmdb_id?,
    title?, subtitle?, detail?, meta?}
    """
    if not data.get("category") or not data.get("action"):
        return {"status": "error", "detail": "category et action requis"}
    await log_event(
        category=data["category"],
        action=data["action"],
        status=data.get("status", "ok"),
        source=data.get("source", "external"),
        media_type=data.get("media_type"),
        media_id=data.get("media_id"),
        tmdb_id=data.get("tmdb_id"),
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        detail=data.get("detail"),
        device=data.get("device"),
        meta=data.get("meta"),
    )
    return {"status": "ok"}

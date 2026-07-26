"""Activity log — persist actions initiated from Arrmada.

``log_event`` is fire-and-forget and MUST NEVER raise into the caller: an audit
write failing should never break the action being audited. It opens its own DB
session so it is independent of the request's transaction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.activity import ActivityEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def log_event(
    *,
    category: str,
    action: str,
    status: str = "ok",
    source: str = "arrmada",
    media_type: Optional[str] = None,
    media_id: Optional[str | int] = None,
    tmdb_id: Optional[int] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    detail: Optional[str] = None,
    duration_ms: Optional[int] = None,
    device: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    """Insert one audit event. Swallows all errors."""
    try:
        async with async_session_factory() as s:
            s.add(
                ActivityEvent(
                    category=category,
                    action=action,
                    status=status,
                    source=source,
                    media_type=media_type,
                    media_id=str(media_id) if media_id is not None else None,
                    tmdb_id=tmdb_id,
                    title=(title or "")[:300] or None,
                    subtitle=(subtitle or "")[:300] or None,
                    detail=detail,
                    duration_ms=duration_ms,
                    device=device,
                    meta=meta,
                )
            )
            await s.commit()
    except Exception as exc:  # never propagate
        logger.warning("activity log failed (%s/%s): %s", category, action, exc)


def to_dict(e: ActivityEvent) -> dict[str, Any]:
    """Serialise a persisted event to the timeline item shape."""
    ts = e.ts
    if ts and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return {
        "id": f"ev-{e.id}",
        "ts": int(ts.timestamp()) if ts else 0,
        "category": e.category,
        "action": e.action,
        "status": e.status,
        "source": e.source,
        "media_type": e.media_type,
        "media_id": e.media_id,
        "tmdb_id": e.tmdb_id,
        "title": e.title,
        "subtitle": e.subtitle,
        "detail": e.detail,
        "duration_ms": e.duration_ms,
        "device": e.device,
        "meta": e.meta,
    }


async def query_events(
    db: AsyncSession,
    *,
    categories: Optional[list[str]] = None,
    statuses: Optional[list[str]] = None,
    media_type: Optional[str] = None,
    media_id: Optional[str] = None,
    tmdb_id: Optional[int] = None,
    search: Optional[str] = None,
    since_ts: Optional[int] = None,
    limit: int = 200,
) -> list[ActivityEvent]:
    """Fetch persisted events matching the given filters (newest first)."""
    stmt = select(ActivityEvent)
    if categories:
        stmt = stmt.where(ActivityEvent.category.in_(categories))
    if statuses:
        stmt = stmt.where(ActivityEvent.status.in_(statuses))
    if media_type:
        stmt = stmt.where(ActivityEvent.media_type == media_type)
    if media_id:
        stmt = stmt.where(ActivityEvent.media_id == str(media_id))
    if tmdb_id:
        stmt = stmt.where(ActivityEvent.tmdb_id == tmdb_id)
    if search:
        stmt = stmt.where(ActivityEvent.title.ilike(f"%{search}%"))
    if since_ts:
        stmt = stmt.where(ActivityEvent.ts >= datetime.fromtimestamp(since_ts, tz=timezone.utc))
    stmt = stmt.order_by(ActivityEvent.ts.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())

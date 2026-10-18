"""Activity log — persist actions initiated from Arrmada.

``log_event`` is fire-and-forget and MUST NEVER raise into the caller: an audit
write failing should never break the action being audited. It opens its own DB
session so it is independent of the request's transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
    media_type: str | None = None,
    media_id: str | int | None = None,
    tmdb_id: int | None = None,
    title: str | None = None,
    subtitle: str | None = None,
    detail: str | None = None,
    duration_ms: int | None = None,
    device: str | None = None,
    meta: dict[str, Any] | None = None,
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
        ts = ts.replace(tzinfo=UTC)
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
    categories: list[str] | None = None,
    statuses: list[str] | None = None,
    media_type: str | None = None,
    media_id: str | None = None,
    tmdb_id: int | None = None,
    search: str | None = None,
    since_ts: int | None = None,
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
        stmt = stmt.where(ActivityEvent.ts >= datetime.fromtimestamp(since_ts, tz=UTC))
    stmt = stmt.order_by(ActivityEvent.ts.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())

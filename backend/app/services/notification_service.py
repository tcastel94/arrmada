"""Notification service — create and query in-app notifications."""

from __future__ import annotations

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    type: str,
    title: str,
    message: str = "",
    severity: str = "info",
    service_name: str | None = None,
) -> Notification:
    """Create and persist a new notification."""
    notif = Notification(
        type=type,
        title=title,
        message=message,
        severity=severity,
        service_name=service_name,
    )
    db.add(notif)
    await db.flush()
    logger.debug("Notification created: [%s] %s", severity, title)
    return notif


async def create_notification_standalone(
    *,
    type: str,
    title: str,
    message: str = "",
    severity: str = "info",
    service_name: str | None = None,
) -> None:
    """Create a notification using a standalone session (for background tasks)."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        notif = Notification(
            type=type,
            title=title,
            message=message,
            severity=severity,
            service_name=service_name,
        )
        session.add(notif)
        await session.commit()


async def get_notifications(
    db: AsyncSession,
    *,
    limit: int = 50,
    unread_only: bool = False,
) -> list[Notification]:
    """Get recent notifications, newest first."""
    stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_unread_count(db: AsyncSession) -> int:
    """Count unread notifications."""
    stmt = select(func.count(Notification.id)).where(
        Notification.is_read == False  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def mark_as_read(db: AsyncSession, notification_id: int) -> bool:
    """Mark a single notification as read."""
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id)
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def mark_all_as_read(db: AsyncSession) -> int:
    """Mark all notifications as read. Returns count updated."""
    stmt = (
        update(Notification)
        .where(Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    result = await db.execute(stmt)
    return result.rowcount


async def delete_old_notifications(db: AsyncSession, keep: int = 200) -> int:
    """Delete notifications beyond the most recent `keep`. Returns count deleted."""
    # Get the ID threshold
    subq = (
        select(Notification.id)
        .order_by(Notification.created_at.desc())
        .offset(keep)
        .limit(1)
    )
    result = await db.execute(subq)
    threshold_id = result.scalar()

    if threshold_id is None:
        return 0

    stmt = delete(Notification).where(Notification.id <= threshold_id)
    result = await db.execute(stmt)
    return result.rowcount

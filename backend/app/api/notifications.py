"""Notification API — list, read, and manage in-app notifications."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.notification_service import (
    get_notifications,
    get_unread_count,
    mark_as_read,
    mark_all_as_read,
)

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


class NotificationOut(BaseModel):
    id: int
    type: str
    severity: str
    title: str
    message: str
    is_read: bool
    service_name: str | None
    created_at: str


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    unread_count: int


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List recent notifications",
)
async def list_notifications(
    limit: int = 50,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent notifications, newest first."""
    notifications = await get_notifications(db, limit=limit, unread_only=unread_only)
    unread = await get_unread_count(db)

    return NotificationListResponse(
        items=[
            NotificationOut(
                id=n.id,
                type=n.type,
                severity=n.severity,
                title=n.title,
                message=n.message,
                is_read=n.is_read,
                service_name=n.service_name,
                created_at=n.created_at.isoformat() if n.created_at else "",
            )
            for n in notifications
        ],
        unread_count=unread,
    )


@router.get(
    "/count",
    summary="Get unread notification count",
)
async def notification_count(db: AsyncSession = Depends(get_db)):
    """Quick endpoint for the badge counter."""
    count = await get_unread_count(db)
    return {"unread_count": count}


@router.post(
    "/{notification_id}/read",
    summary="Mark a notification as read",
)
async def read_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    success = await mark_as_read(db, notification_id)
    await db.commit()
    return {"success": success}


@router.post(
    "/read-all",
    summary="Mark all notifications as read",
)
async def read_all_notifications(db: AsyncSession = Depends(get_db)):
    """Mark every unread notification as read."""
    count = await mark_all_as_read(db)
    await db.commit()
    return {"marked_read": count}

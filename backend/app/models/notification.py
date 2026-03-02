"""Notification model — stores in-app alert events."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Notification(Base):
    """An in-app notification."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(50))
    # Types: service_down, service_recovered, trash_sync, trash_apply,
    #        download_complete, system_info, system_warning
    severity: Mapped[str] = mapped_column(String(20), default="info")
    # Severities: info, success, warning, error
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(default=False)
    service_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

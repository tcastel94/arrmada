"""DuplicateGroup model — duplicate media detection."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class DuplicateGroup(Base):
    """A group of duplicate media items detected by the system."""

    __tablename__ = "duplicate_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_type: Mapped[str] = mapped_column(String(20))
    normalized_title: Mapped[str] = mapped_column(String(500))
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    item_count: Mapped[int] = mapped_column(default=2)
    best_quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    potential_savings_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, resolved, ignored
    detected_at: Mapped[datetime] = mapped_column(default=func.now())

    def __repr__(self) -> str:
        return f"<DuplicateGroup {self.normalized_title} ({self.item_count} items)>"

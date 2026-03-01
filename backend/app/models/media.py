"""MediaItem model — unified media representation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MediaItem(Base):
    """A media item synced from one of the *arr services."""

    __tablename__ = "media_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(100))  # ID in the source *arr
    tmdb_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(20))  # movie, series, music, book
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    genres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_service: Mapped[str] = mapped_column(String(50))  # which *arr it comes from
    added_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    synced_at: Mapped[datetime] = mapped_column(default=func.now())
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full metadata cache

    def __repr__(self) -> str:
        return f"<MediaItem {self.title} ({self.type})>"

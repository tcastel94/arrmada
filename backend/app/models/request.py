"""MediaRequest model — Overseerr-like request system."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MediaRequest(Base):
    """A media request submitted by the user."""

    __tablename__ = "media_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tmdb_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(20))  # movie, series, music, book
    year: Mapped[Optional[int]] = mapped_column(nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_profile: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested, searching, downloading, available, failed
    target_service: Mapped[str] = mapped_column(String(50))  # radarr, sonarr, lidarr, readarr
    arr_id: Mapped[Optional[int]] = mapped_column(nullable=True)  # ID in the target *arr once added
    requested_at: Mapped[datetime] = mapped_column(default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<MediaRequest {self.title} — {self.status}>"

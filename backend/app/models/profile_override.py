"""ProfileOverride model — per-series/movie TRaSH profile assignments."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ProfileOverride(Base):
    """Override TRaSH quality profile for a specific series or movie.

    When applying TRaSH recommendations, the system will use the
    override profile instead of the default one for matching media.
    """

    __tablename__ = "profile_overrides"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifies the media in Sonarr/Radarr
    media_type: Mapped[str] = mapped_column(String(20))  # "series" or "movie"
    external_id: Mapped[int] = mapped_column()  # Sonarr series ID or Radarr movie ID
    title: Mapped[str] = mapped_column(String(500))  # Display title
    # TRaSH profile config
    profile_name: Mapped[str] = mapped_column(String(200))  # e.g. "french-multi-vo-bluray-web-2160p"
    service_id: Mapped[int] = mapped_column()  # Which Sonarr/Radarr service
    # Optional note
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

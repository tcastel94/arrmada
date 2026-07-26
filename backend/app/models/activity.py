"""ActivityEvent model — persistent audit log of actions across Arrmada."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class ActivityEvent(Base):
    """One logged action (download, subtitle, playback, library, telegram…).

    Persisted so the Activité timeline can show actions initiated *from Arrmada*
    (Kodi playback, subtitle downloads, searches, bot adds) that no external
    service records. *arr/Bazarr history is merged in on read, not stored here.
    """

    __tablename__ = "activity_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(default=func.now(), index=True)

    # Taxonomy
    category: Mapped[str] = mapped_column(String(32), index=True)  # download|subtitle|playback|library|telegram|system
    action: Mapped[str] = mapped_column(String(48))               # kodi_play|sub_download|sub_sync|search|grab|delete|add|…
    status: Mapped[str] = mapped_column(String(16), default="ok")  # ok|ko|info
    source: Mapped[str] = mapped_column(String(32), default="arrmada")  # arrmada|kodi|radarr|sonarr|bazarr|telegram

    # Media reference (for grouping by média)
    media_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # movie|series
    media_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)     # radarr/sonarr id (external_id)
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)   # episode label / provider / language

    # Details
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)             # KO reason, free text
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)      # Kodi/AVR name
    meta: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_activity_media", "media_type", "media_id"),
        Index("ix_activity_cat_ts", "category", "ts"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ActivityEvent {self.category}/{self.action} {self.title!r} {self.status}>"

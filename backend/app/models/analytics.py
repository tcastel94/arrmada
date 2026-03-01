"""AnalyticsSnapshot model — daily library statistics."""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AnalyticsSnapshot(Base):
    """A daily snapshot of library statistics."""

    __tablename__ = "analytics_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, unique=True)
    total_movies: Mapped[int] = mapped_column(default=0)
    total_series: Mapped[int] = mapped_column(default=0)
    total_albums: Mapped[int] = mapped_column(default=0)
    total_books: Mapped[int] = mapped_column(default=0)
    total_size_gb: Mapped[float] = mapped_column(default=0.0)
    downloads_count: Mapped[int] = mapped_column(default=0)
    quality_breakdown_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    genre_breakdown_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AnalyticsSnapshot {self.date}>"

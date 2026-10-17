"""Recommendation model — AI-generated media suggestions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Recommendation(Base):
    """An AI-generated media recommendation."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    tmdb_id: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    type: Mapped[str] = mapped_column(String(20))  # movie, series, music
    year: Mapped[int | None] = mapped_column(nullable=True)
    genres: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    score: Mapped[float] = mapped_column(default=0.0)  # Recommendation score 0-1
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # "Because you liked X, Y"
    is_dismissed: Mapped[bool] = mapped_column(default=False)
    generated_at: Mapped[datetime] = mapped_column(default=func.now())

    def __repr__(self) -> str:
        return f"<Recommendation {self.title} (score={self.score:.2f})>"

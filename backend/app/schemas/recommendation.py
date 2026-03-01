"""Recommendation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RecommendationResponse(BaseModel):
    """Recommendation response."""
    id: int
    tmdb_id: int | None = None
    title: str
    type: str
    year: int | None = None
    genres: list[str] | None = None
    poster_url: str | None = None
    score: float
    reason: str | None = None
    is_dismissed: bool
    generated_at: datetime

    model_config = {"from_attributes": True}

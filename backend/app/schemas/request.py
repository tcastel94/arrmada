"""Request schemas (Overseerr-like)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaRequestCreate(BaseModel):
    """Create a new media request."""
    tmdb_id: int | None = None
    title: str = Field(min_length=1, max_length=500)
    type: str = Field(pattern=r"^(movie|series|music|book)$")
    year: int | None = None
    poster_url: str | None = None
    quality_profile: str | None = None
    target_service: str = Field(pattern=r"^(radarr|sonarr|lidarr|readarr)$")


class MediaRequestResponse(BaseModel):
    """Media request response."""
    id: int
    tmdb_id: int | None = None
    title: str
    type: str
    year: int | None = None
    poster_url: str | None = None
    quality_profile: str | None = None
    status: str
    target_service: str
    arr_id: int | None = None
    requested_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}

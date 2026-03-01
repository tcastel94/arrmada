"""Media schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MediaItemResponse(BaseModel):
    """Media item response."""
    id: int
    external_id: str
    tmdb_id: int | None = None
    title: str
    type: str
    year: int | None = None
    genres: list[str] | None = None
    quality: str | None = None
    size_bytes: int | None = None
    poster_url: str | None = None
    source_service: str
    added_at: datetime | None = None
    synced_at: datetime

    model_config = {"from_attributes": True}

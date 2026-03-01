"""Analytics schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class AnalyticsSnapshotResponse(BaseModel):
    """Analytics snapshot response."""
    id: int
    date: dt.date
    total_movies: int
    total_series: int
    total_albums: int
    total_books: int
    total_size_gb: float
    downloads_count: int
    quality_breakdown: dict | None = None
    genre_breakdown: dict | None = None

    model_config = {"from_attributes": True}


class AnalyticsSummary(BaseModel):
    """Aggregated analytics summary."""
    total_movies: int = 0
    total_series: int = 0
    total_albums: int = 0
    total_books: int = 0
    total_size_gb: float = 0.0
    total_items: int = 0
    snapshots: list[AnalyticsSnapshotResponse] = []

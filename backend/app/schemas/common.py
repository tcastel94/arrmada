"""Health check response schema."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app import __version__


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="arrmada", description="Service name")
    version: str = Field(default=__version__, description="Backend version")

    model_config = {
        "json_schema_extra": {
            "examples": [{"status": "ok", "service": "arrmada", "version": __version__}]
        }
    }


class PaginationMeta(BaseModel):
    """Pagination metadata returned with list endpoints."""

    page: int = Field(ge=1, description="Current page number")
    per_page: int = Field(ge=1, le=200, description="Items per page")
    total: int = Field(ge=0, description="Total number of items")
    total_pages: int = Field(ge=0, description="Total number of pages")


class ErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(description="Human-readable error message")

    model_config = {"json_schema_extra": {"examples": [{"detail": "Not found"}]}}


class MessageResponse(BaseModel):
    """Generic success message response."""

    message: str = Field(description="Success message")
    detail: str | None = Field(None, description="Additional details")

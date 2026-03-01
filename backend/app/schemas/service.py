"""Service schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# ── Input ─────────────────────────────────────────────────────
class ServiceCreate(BaseModel):
    """Create a new *arr service connection."""

    name: str = Field(min_length=1, max_length=100, description="Display name for the service")
    type: str = Field(
        pattern=r"^(sonarr|radarr|lidarr|readarr|prowlarr|bazarr|jellyfin|sabnzbd)$",
        description="Service type",
    )
    url: str = Field(min_length=1, max_length=500, description="Service base URL")
    api_key: str = Field(min_length=1, max_length=200, description="API key for authentication")
    is_enabled: bool = Field(default=True, description="Whether the service is active")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Mon Sonarr",
                    "type": "sonarr",
                    "url": "http://192.168.1.10:8989",
                    "api_key": "abcdef1234567890",
                    "is_enabled": True,
                }
            ]
        }
    }


class ServiceUpdate(BaseModel):
    """Update an existing service (partial)."""

    name: str | None = Field(None, min_length=1, max_length=100)
    url: str | None = Field(None, min_length=1, max_length=500)
    api_key: str | None = Field(None, min_length=1, max_length=200)
    is_enabled: bool | None = None


# ── Output ────────────────────────────────────────────────────
class ServiceResponse(BaseModel):
    """Service response — API key is never exposed."""

    id: int
    name: str
    type: str
    url: str
    is_enabled: bool
    last_health_check: datetime | None = None
    last_status: str = Field(default="unknown", description="Last known health status")
    last_latency_ms: int | None = Field(None, description="Last measured latency in ms")
    version: str | None = Field(None, description="Service version string")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HealthEventResponse(BaseModel):
    """Health event response."""

    id: int
    service_id: int
    status: str = Field(description="online, offline, or degraded")
    latency_ms: int | None = None
    error_message: str | None = None
    checked_at: datetime

    model_config = {"from_attributes": True}


class ServiceHealthResponse(BaseModel):
    """Global health check result for a single service."""

    service_id: int
    service_name: str
    service_type: str
    status: str = Field(description="online, offline, or degraded")
    latency_ms: int | None = None
    error: str | None = None
    version: str | None = None


class TestConnectionResponse(BaseModel):
    """Test connection result."""

    success: bool
    status: str
    latency_ms: int | None = None
    version: str | None = None
    error: str | None = None

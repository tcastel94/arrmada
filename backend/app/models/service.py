"""Service and HealthEvent models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Service(Base):
    """A connected *arr service (Sonarr, Radarr, etc.)."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))  # sonarr, radarr, lidarr, readarr, prowlarr, bazarr, jellyfin, sabnzbd
    url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[str] = mapped_column(String(500))  # Fernet-encrypted
    is_enabled: Mapped[bool] = mapped_column(default=True)
    last_health_check: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="unknown")  # online, offline, degraded
    last_latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    health_events: Mapped[list["HealthEvent"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Service {self.name} ({self.type}) — {self.last_status}>"


class HealthEvent(Base):
    """A health check result for a service."""

    __tablename__ = "health_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    service: Mapped["Service"] = relationship(back_populates="health_events")

    def __repr__(self) -> str:
        return f"<HealthEvent service={self.service_id} status={self.status}>"

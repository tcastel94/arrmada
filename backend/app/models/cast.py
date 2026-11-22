"""CastDevice model — cibles d'envoi : Google Cast (Chromecast / Nest / Google TV) et Apple TV."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class CastDevice(Base):
    """A Google Cast device we can cast Jellyfin streams to.

    Persisted (rather than discovered every request) because mDNS discovery is
    unreliable from inside a bridged container; casting itself connects to the
    device by IP, which works fine LAN-side.
    """

    __tablename__ = "cast_devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    ip: Mapped[str] = mapped_column(String(64))
    port: Mapped[int] = mapped_column(Integer, default=8009)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Cast groups & video-capable devices (screens / Google TV) can play video;
    # audio-only speakers cannot.
    video_capable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # « chromecast » (pychromecast, flux transcodé) ou « appletv » (pyatv :
    # le serveur fait ouvrir le fichier d'origine par VLC sur l'Apple TV)
    kind: Mapped[str] = mapped_column(String(20), default="chromecast", server_default="chromecast")
    # Apple TV : identifiants d'appairage chiffrés, JSON {"airplay": …,
    # "companion": …}. Les deux sont nécessaires (voir services/appletv.py).
    credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CastDevice {self.name} ({self.model}) @ {self.ip}>"

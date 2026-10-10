"""Appareils appairés (Kodi des TV) — ADR-003 § 4 et § 6.

Chaque Kodi appairé reçoit un jeton qui lui est propre. On ne stocke que son
empreinte SHA-256 (comme un mot de passe haché) : une fuite de la base ne
donne pas accès aux TV. Révoquer un appareil = supprimer sa ligne.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# Liste fixe (ADR-003, décision 3) : ce sont les deux profils audio Yamaha.
ROOMS = ("salon", "cinema")

# Sortes d'appareils : une TV (Kodi, périmètre « TV ») ou un écran d'appoint
# (tablette sous la TV, lecture seule : il affiche, il ne commande rien).
KINDS = ("tv", "screen")


class Device(Base):
    """Un Kodi appairé : nom, pièce, ampli, empreinte de son jeton."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    room: Mapped[str] = mapped_column(String(20), default="salon")
    # Ampli Yamaha de la pièce de cet appareil (None = le premier ampli actif)
    avr_service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # « tv » ou « screen » (écran d'appoint) : décide du périmètre du jeton
    kind: Mapped[str] = mapped_column(String(20), default="tv", server_default="tv")
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return f"<Device {self.name} ({self.room})>"

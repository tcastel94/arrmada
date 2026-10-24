"""Profils famille (ADR-008) : qui regarde, sur une TV partagée.

Comme les profils d'un service de streaming : chacun a sa rangée
« Reprendre », ses épisodes vus, son « Pour toi » et ses demandes
« Pour ce soir ». Le profil « Famille » (is_default) est celui des TV sous
Kodi et de tout appel sans profil : ses données sont celles d'avant les
profils (lignes sans profile_id).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class FamilyProfile(Base):
    __tablename__ = "family_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    color: Mapped[str] = mapped_column(String(9), default="#4A9EFF", server_default="#4A9EFF")
    emoji: Mapped[str] = mapped_column(String(8), default="", server_default="")
    is_default: Mapped[bool] = mapped_column(default=False, server_default=false())
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<FamilyProfile {self.id} {self.name}>"

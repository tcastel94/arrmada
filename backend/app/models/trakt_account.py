"""Compte Trakt relié à un profil famille (ADR-022).

Une ligne par profil : « Famille » (profile_key 0), Jeff, Morgane… Chacun
relie SON compte Trakt (trakt.tv/activate) ; ses notes et ce qu'il regarde
partent sur ce compte. Les jetons sont chiffrés comme les clés des services.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class TraktAccount(Base):
    __tablename__ = "trakt_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Profil famille : son id, ou 0 pour « Famille » (profil par défaut, sans id dans les jetons TV)
    profile_key: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120), default="")
    access_token: Mapped[str] = mapped_column(Text)  # chiffré
    refresh_token: Mapped[str] = mapped_column(Text)  # chiffré
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<TraktAccount profil={self.profile_key} @{self.username}>"

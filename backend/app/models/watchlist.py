"""Liste « À voir » par profil famille.

Chaque profil (ADR-008) garde sa liste de films et de séries à regarder :
ajoutés depuis la web app (fiche, recherche, recommandations) ou depuis la
TV, et retrouvés en rangée « Ma liste » sur la TV, la web app et la
tablette. Comme le vu partagé, un titre est repéré par ses identifiants
publics (TMDB pour un film, TVDB pour une série), jamais par l'identifiant
interne de Radarr / Sonarr : un titre peut être dans la liste AVANT d'être
dans la médiathèque.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    # « movie:tmdb:438631 », préfixé « p3: » pour un profil autre que « Famille »
    # (même convention que le vu partagé, voir family_profiles.profiled_key)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    # Profil famille ; null : profil « Famille »
    profile_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(String(10))  # movie | series
    id_type: Mapped[str] = mapped_column(String(10))  # tmdb | tvdb
    external_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(nullable=True)
    poster_url: Mapped[str] = mapped_column(String(500), default="", server_default="")
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<WatchlistItem {self.key}>"

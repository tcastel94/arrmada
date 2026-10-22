"""Séries maison : un dossier vidéo affiché comme une série (Naruto Kai, One Pace…).

Les montages de fans (« Kai ») n'ont pas de fiche TVDB / TMDB : Sonarr ne
peut pas les gérer. Déclarés dans la web app (Réglages › Dossiers vidéo), ils
apparaissent dans la grille Séries de l'appli comme les séries officielles :
sous-dossiers = saisons (arcs), vidéos = épisodes. L'affiche, le fond et le
résumé viennent de la série officielle sur TMDB (tmdb_id), ou des images et
NFO posés dans le dossier.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class LocalSeries(Base):
    __tablename__ = "local_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    root_id: Mapped[int] = mapped_column(ForeignKey("video_roots.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(1000), default="")  # relatif au dossier racine
    title: Mapped[str] = mapped_column(String(120))
    badge: Mapped[str] = mapped_column(String(20), default="Kai", server_default="Kai")
    tmdb_id: Mapped[int | None] = mapped_column(nullable=True)  # série officielle (images)
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fanart_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<LocalSeries {self.id} {self.title}>"

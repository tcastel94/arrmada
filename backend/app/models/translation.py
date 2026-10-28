"""Synopsis en français d'un film ou d'une série, gardés en base.

Radarr est réglé sur l'anglais (langue des infos du film) et Sonarr ne parle
qu'anglais : leurs résumés arrivent en anglais. Le résumé français est
demandé à TMDB (`language=fr-FR`) puis gardé ici, comme un cache disque :
les écrans ne l'interrogent jamais au moment d'afficher (sauf la première
ouverture d'une fiche). Vide = TMDB n'a pas de traduction française (on
garde alors l'anglais).

Même clé que les artworks : « movie:<TMDB> » pour un film, « series:<TVDB> »
pour une série (identifiant de Sonarr).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MediaTranslation(Base):
    __tablename__ = "media_translations"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(10))  # movie | series
    provider_id: Mapped[int] = mapped_column()
    overview: Mapped[str] = mapped_column(Text, default="", server_default="")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<MediaTranslation {self.key} {'fr' if self.overview else '-'}>"

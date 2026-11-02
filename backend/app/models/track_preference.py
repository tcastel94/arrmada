"""Pistes choisies par un profil pour une série ou un film (appli Android TV).

Au lancement, la TV choisit seule les langues (VO + sous-titres français,
ou VF + forcés pour un film français). Si quelqu'un change de piste — passe
une série en VF, coupe les sous-titres —, ce choix est rangé ici et repris
à l'épisode suivant, sur n'importe quelle TV, pour ce profil seulement.

Une ligne = un profil × une série (ou un film, ou une série maison).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class TrackPreference(Base):
    __tablename__ = "track_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    # « 3|series:tvdb:280619 » (profil 0 : « Famille ») — clé d'upsert
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(nullable=True)
    # « series:tvdb:280619 », « movie:tmdb:438631 » ou « local:12 » (série maison)
    scope: Mapped[str] = mapped_column(String(60))
    # Langue entendue (« en », « fr »…), vide : pas de préférence
    audio_language: Mapped[str] = mapped_column(String(8), default="", server_default="")
    # Langue des sous-titres ; « off » : coupés ; vide : pas de préférence
    subtitle_language: Mapped[str] = mapped_column(String(8), default="", server_default="")
    subtitle_forced: Mapped[bool] = mapped_column(default=False, server_default=false())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return (
            f"<TrackPreference {self.key} audio={self.audio_language} st={self.subtitle_language}>"
        )

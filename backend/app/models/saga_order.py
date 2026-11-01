"""Ordre personnalisé des films d'une saga (ADR-016, étape 3).

TMDB ne donne que l'ordre de sortie. Pour une saga dont l'histoire se
déroule dans un autre ordre (Star Wars I à IX, Les Animaux fantastiques
avant Harry Potter…), on enregistre ici l'ordre choisi à la main, repéré
par l'identifiant TMDB de la saga et de ses films (jamais par ceux de
Radarr, qui changent si on supprime et rajoute un film).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SagaOrder(Base):
    __tablename__ = "saga_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifiant TMDB de la saga (collection)
    collection_tmdb: Mapped[int] = mapped_column(unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")
    # Identifiants TMDB des films, dans l'ordre choisi, séparés par des virgules
    tmdb_ids: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def ids(self) -> list[int]:
        return [int(x) for x in self.tmdb_ids.split(",") if x.strip().isdigit()]

    def __repr__(self) -> str:
        return f"<SagaOrder {self.collection_tmdb} {self.tmdb_ids}>"

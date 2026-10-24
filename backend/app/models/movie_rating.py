"""Notes d'un film (IMDb, Metacritic, Rotten Tomatoes, TMDB), gardées en base.

Les films de la médiathèque ont leurs notes directement dans Radarr. Les
films PROPOSÉS (tendances, « Parce que tu as vu… », Découvrir) ne sont pas
dans Radarr : leur note IMDb est demandée une fois à Radarr (recherche par
identifiant TMDB, qui interroge le serveur de métadonnées de Radarr) puis
gardée ici 14 jours. Comme un cache disque : pas de nouvel appel tant que
la copie est récente, et elle survit au redémarrage du serveur.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MovieRating(Base):
    __tablename__ = "movie_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    imdb: Mapped[float | None] = mapped_column(Float, nullable=True)  # sur 10
    imdb_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metacritic: Mapped[int | None] = mapped_column(Integer, nullable=True)  # sur 100
    rotten_tomatoes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # % critiques
    tmdb: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmdb_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<MovieRating tmdb={self.tmdb_id} imdb={self.imdb}>"

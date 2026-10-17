"""Vu / reprise partagés entre les TV (ADR-004, phase 4.4).

Chaque Kodi garde son propre « vu » et sa propre position de reprise dans sa
médiathèque. Cette table est le point de rendez-vous : une TV y dépose l'état
d'un film ou d'un épisode quand il change chez elle, les autres le relisent
et l'appliquent à leur médiathèque (kodi-addon/script.arrmada/lib/watch_sync.py).

Un titre est repéré par ses identifiants publics (TMDB, TVDB, IMDb), jamais
par le numéro interne d'une médiathèque Kodi : ces numéros diffèrent d'une TV
à l'autre. Un épisode = série + saison + numéro.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class WatchState(Base):
    """Dernier état connu d'un film ou d'un épisode, toutes TV confondues."""

    __tablename__ = "watch_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    # « movie:tmdb:438631 » ou « episode:tvdb:280619:2:5 » (clé d'upsert)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(10))  # movie | episode
    id_type: Mapped[str] = mapped_column(String(10))  # tmdb | tvdb | imdb
    external_id: Mapped[str] = mapped_column(String(40))
    season: Mapped[int | None] = mapped_column(nullable=True)
    episode: Mapped[int | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")
    watched: Mapped[bool] = mapped_column(default=False, server_default=false())
    position: Mapped[int] = mapped_column(default=0, server_default="0")  # s
    total: Mapped[int] = mapped_column(default=0, server_default="0")  # s
    # Date « vu le » telle que Kodi l'écrit (heure locale de la maison,
    # « 2026-10-11 21:42:05 ») : recopiée telle quelle sur les autres TV.
    last_played: Mapped[str] = mapped_column(String(19), default="", server_default="")
    device: Mapped[str] = mapped_column(String(100), default="", server_default="")
    # Curseur de relecture des TV : strictement croissant (services/watch_sync.py)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<WatchState {self.key} vu={self.watched} pos={self.position}>"

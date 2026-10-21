"""Dossiers vidéo (écran « Vidéos » de l'appli) : vidéos hors médiathèque.

Les mangas « Kai », montages de fans, vidéos perso… n'ont pas de fiche
TMDB / TVDB : ni Radarr, ni Sonarr, ni Jellyfin ne les rangent. Ces dossiers
du NAS, déclarés dans la web app (Réglages › Dossiers vidéo), se parcourent
comme un explorateur de fichiers depuis les TV et les téléphones.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class VideoRoot(Base):
    __tablename__ = "video_roots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60))  # libellé affiché (« Mangas Kai »)
    path: Mapped[str] = mapped_column(String(500))  # chemin vu par le serveur (/mnt/user/…)
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<VideoRoot {self.id} {self.name} {self.path}>"

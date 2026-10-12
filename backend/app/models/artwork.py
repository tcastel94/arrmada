"""Artworks des films et séries : logo, disque, clearart, bannière, vignette.

Radarr et Sonarr ne connaissent que l'affiche et le fond (et parfois un logo,
souvent en anglais). Le reste vient de fanart.tv (logos HD, disques Blu-ray /
DVD, clearart…) et de TMDB (logos), récupéré par services/artwork.py.

Une ligne par titre, repéré comme partout ailleurs dans ArrMada par son
identifiant public : TMDB pour un film, TVDB pour une série (celui de
Sonarr). Les écrans (web app, Kodi) lisent cette table via la médiathèque et
la fiche : ils n'interrogent jamais fanart.tv ou TMDB au moment d'afficher.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class MediaArtwork(Base):
    """Meilleures images trouvées pour un titre (URL publiques, vides si rien)."""

    __tablename__ = "media_artwork"

    id: Mapped[int] = mapped_column(primary_key=True)
    # « movie:438631 » (TMDB) ou « series:280619 » (TVDB) : clé d'upsert
    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    media_type: Mapped[str] = mapped_column(String(10))  # movie | series
    provider_id: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")
    clearlogo: Mapped[str] = mapped_column(String(500), default="", server_default="")
    discart: Mapped[str] = mapped_column(String(500), default="", server_default="")
    disc_type: Mapped[str] = mapped_column(String(20), default="", server_default="")
    clearart: Mapped[str] = mapped_column(String(500), default="", server_default="")
    banner: Mapped[str] = mapped_column(String(500), default="", server_default="")
    landscape: Mapped[str] = mapped_column(String(500), default="", server_default="")
    poster: Mapped[str] = mapped_column(String(500), default="", server_default="")
    fanart: Mapped[str] = mapped_column(String(500), default="", server_default="")
    # Sites qui ont répondu (« fanart.tv,tmdb »), pour le diagnostic
    sources: Mapped[str] = mapped_column(String(60), default="", server_default="")
    # ok (au moins une image) | empty (rien trouvé) | error (site injoignable)
    status: Mapped[str] = mapped_column(String(10), default="ok", server_default="ok")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<MediaArtwork {self.key} {self.status}>"

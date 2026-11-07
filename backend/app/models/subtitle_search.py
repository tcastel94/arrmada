"""Essais de recherche de sous-titres du gardien (services/subtitle_guardian.py).

Un épisode d'anime sort le samedi, le sous-titre français du fansub arrive
le lundi ou le mercredi : chercher une seule fois ne suffit pas, chercher en
boucle épuise les quotas des fournisseurs. Cette table retient, pour chaque
titre qui n'a toujours pas ses sous-titres, combien d'essais ont été faits et
quand refaire le suivant (1 h, 3 h, 6 h, 12 h, 24 h, 2 j, 4 j, puis 7 j).

Une ligne = un film ou un épisode × une langue. Supprimée dès que le
sous-titre est trouvé.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class SubtitleSearch(Base):
    __tablename__ = "subtitle_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    # « episode:sonarr:42:fr » ou « movie:radarr:7:fr » (clé d'upsert)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    # Dernier résultat : none (rien trouvé), error (panne), found
    last_result: Mapped[str] = mapped_column(String(20), default="", server_default="")
    last_message: Mapped[str] = mapped_column(String(400), default="", server_default="")
    first_try_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_try_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_try_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<SubtitleSearch {self.key} essais={self.attempts} prochain={self.next_try_at}>"

"""Demandes de téléchargement lancées depuis une TV (« pour ce soir »).

Quand quelqu'un lance un film ou une série depuis le canapé, c'est en général
pour le regarder tout de suite : la demande est notée ici, et le gardien de
priorité (services/tv_priority.py) fait passer ses téléchargements devant le
reste de la file SABnzbd.

Une demande vise un film, une série entière, une saison ou des épisodes
précis. Elle se ferme d'elle-même : quand ses téléchargements ont quitté la
file (importés), ou au bout de TV_REQUEST_TTL_HOURS si rien n'a été trouvé.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# open      : en cours (recherche ou téléchargement)
# done      : téléchargements terminés (sortis de la file)
# cancelled : annulée depuis la TV qui l'avait lancée
# expired   : rien trouvé dans le délai
STATUSES = ("open", "done", "cancelled", "expired")

# Portée : film, série entière, une saison, des épisodes précis
SCOPES = ("movie", "series", "season", "episode")


class TvRequest(Base):
    """Une demande « pour ce soir » : quoi, depuis quelle TV, où elle en est."""

    __tablename__ = "tv_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_type: Mapped[str] = mapped_column(String(10))  # radarr | sonarr
    arr_id: Mapped[int] = mapped_column(index=True)  # id du film / de la série dans le *arr
    title: Mapped[str] = mapped_column(String(300), default="", server_default="")
    scope: Mapped[str] = mapped_column(String(10), default="movie")
    season: Mapped[int | None] = mapped_column(nullable=True)
    # Épisodes visés (ids Sonarr), portée « episode » seulement
    episode_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Release choisie à la main sur la TV : seul ce téléchargement est visé
    release_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Passe devant la file (par défaut oui ; la TV pourra proposer « sans priorité »)
    priority: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Titre ajouté au *arr par cette demande : l'annuler arrête aussi sa surveillance
    added: Mapped[bool] = mapped_column(default=False, server_default=false())
    # TV d'origine (vide si l'addon n'est pas appairé : clé API)
    device_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    device_name: Mapped[str] = mapped_column(String(100), default="TV", server_default="TV")
    room: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)
    # Téléchargements vus pour cette demande (downloadId *arr = nzo_id SABnzbd)
    download_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    grabbed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<TvRequest {self.title} ({self.scope}) {self.status} via {self.device_name}>"

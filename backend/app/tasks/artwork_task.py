"""Tâche planifiée : artworks des nouveaux titres (services/artwork.py).

Une fois par jour (ARTWORK_AUTO_INTERVAL_HOURS), la médiathèque est relue et
seuls les titres jamais servis, ou servis il y a longtemps, sont demandés à
fanart.tv / TMDB : un film ajouté dans la semaine a son logo et son disque
sans que personne ne clique sur « Récupérer les artworks ».
"""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services import artwork
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def artwork_job() -> None:
    """Récupère les artworks manquants, sauf si le bouton de la web app tourne déjà."""
    if not artwork.start_refresh(force=False):
        logger.info("Artworks : récupération déjà en cours, passage planifié ignoré")
        return
    await artwork.wait_for_refresh()


def register(scheduler: AsyncIOScheduler) -> None:
    """Inscrit la tâche (seulement si une source d'artworks est configurée)."""
    if not settings.ARTWORK_AUTO_ENABLED:
        logger.info("artwork_refresh job NOT registered (ARTWORK_AUTO_ENABLED=false)")
        return
    if not any(artwork.sources_configured().values()):
        logger.info("artwork_refresh job NOT registered (aucune source : fanart.tv, TMDB, dossiers)")
        return
    hours = max(1, settings.ARTWORK_AUTO_INTERVAL_HOURS)
    scheduler.add_job(
        artwork_job,
        trigger="interval",
        hours=hours,
        # Premier passage 10 min après le démarrage : laisse Radarr/Sonarr
        # répondre aux écrans d'abord.
        next_run_time=datetime.now() + timedelta(minutes=10),
        id="artwork_refresh",
        name="Artworks des nouveaux titres",
        replace_existing=True,
    )
    logger.info("Registered artwork_refresh job (every %d h)", hours)

"""Tâche planifiée : synopsis français des titres de la médiathèque (services/translations.py).

Toutes les 6 heures, la médiathèque est relue et seuls les titres jamais
traduits (ou traduits il y a longtemps) sont demandés à TMDB : un film ajouté
dans la journée a son résumé en français sur l'accueil de la TV sans que
personne n'ouvre sa fiche.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services import translations
from app.utils.logger import get_logger

logger = get_logger(__name__)

INTERVAL_HOURS = 6


async def translation_job() -> None:
    await translations.refresh_library()


def register(scheduler: AsyncIOScheduler) -> None:
    """Inscrit la tâche (seulement si TMDB est configuré)."""
    if not settings.TMDB_API_KEY:
        logger.info("overview_translation job NOT registered (TMDB_API_KEY absent)")
        return
    scheduler.add_job(
        translation_job,
        trigger="interval",
        hours=INTERVAL_HOURS,
        # Premier passage 3 min après le démarrage : la médiathèque d'abord
        next_run_time=datetime.now() + timedelta(minutes=3),
        id="overview_translation",
        name="Synopsis en français",
        replace_existing=True,
    )
    logger.info("Registered overview_translation job (every %d h)", INTERVAL_HOURS)

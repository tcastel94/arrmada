"""Vérification horaire de la release GitHub de l'appli Android (services/android_update.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services import android_update
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _tick() -> None:
    try:
        await android_update.refresh()
    except Exception as exc:  # une passe ratée ne doit jamais tuer la minuterie
        logger.warning("Mise à jour Android : passe en échec (%s)", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Toutes les heures, et une première fois une minute après le démarrage."""
    if not settings.ANDROID_UPDATE_REPO.strip():
        logger.info("Mise à jour Android : pas de dépôt GitHub (APK déposées à la main)")
        return
    scheduler.add_job(
        _tick,
        trigger="interval",
        hours=1,
        next_run_time=datetime.now(UTC) + timedelta(minutes=1),
        id="android_update",
        name="Rapatriement de l'APK Android publiée par la CI",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

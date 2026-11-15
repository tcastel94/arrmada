"""Alertes Telegram des téléchargements bloqués (services/telegram_alerts.py).

Deux minuteries :
  - la passe de détection, toutes les 5 minutes ;
  - la lecture des clics (« long polling ») : chaque passe attend jusqu'à
    25 s une réponse de Telegram, puis la suivante repart 2 s après. Les deux
    sont limitées à une instance à la fois (jamais deux lectures en parallèle,
    Telegram le refuserait).
Rien n'est enregistré si Telegram n'est pas configuré dans le .env.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services import telegram_alerts
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def _scan() -> None:
    try:
        sent = await telegram_alerts.scan()
        if sent:
            logger.info("Alertes Telegram : %d téléchargement(s) bloqué(s) signalé(s)", sent)
    except Exception as exc:  # une passe ratée ne doit jamais tuer la minuterie
        logger.warning("Alertes Telegram : passe en échec (%s)", exc)


async def _poll() -> None:
    try:
        await telegram_alerts.poll_once()
    except Exception as exc:  # réseau coupé, Telegram indisponible : on réessaie
        logger.debug("Alertes Telegram : lecture des clics en échec (%s)", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    if not telegram_alerts.configured():
        logger.info("Alertes Telegram inactives (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID absents)")
        return
    common = {"replace_existing": True, "max_instances": 1, "coalesce": True}
    scheduler.add_job(
        _scan,
        trigger="interval",
        minutes=5,
        id="telegram_alerts_scan",
        name="Alertes Telegram : téléchargements bloqués",
        **common,
    )
    scheduler.add_job(
        _poll,
        trigger="interval",
        seconds=2,
        id="telegram_alerts_poll",
        name="Alertes Telegram : lecture des boutons",
        **common,
    )

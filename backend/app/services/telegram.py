"""Telegram notification service."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to the configured Telegram chat."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — skipping notification")
        return False

    url = f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Telegram notification sent")
            return True
    except Exception as exc:
        logger.error("Failed to send Telegram notification: %s", exc)
        return False


async def notify_service_down(service_name: str, error: str) -> bool:
    """Send alert when a service goes offline."""
    return await send_message(
        f"🔴 <b>Service offline</b>\n"
        f"<code>{service_name}</code> est hors ligne\n"
        f"Erreur: {error}"
    )


async def notify_service_recovered(service_name: str, latency_ms: int) -> bool:
    """Send alert when a service recovers."""
    return await send_message(
        f"🟢 <b>Service rétabli</b>\n"
        f"<code>{service_name}</code> est de retour en ligne ({latency_ms}ms)"
    )


async def notify_download_complete(title: str, quality: str, service: str) -> bool:
    """Send alert when a download completes."""
    return await send_message(
        f"✅ <b>Téléchargement terminé</b>\n"
        f"<code>{title}</code>\n"
        f"Qualité: {quality} | Service: {service}"
    )


async def notify_new_media(title: str, media_type: str, year: int | None) -> bool:
    """Send alert when new media is added."""
    icon = "🎬" if media_type == "movie" else "📺"
    year_str = f" ({year})" if year else ""
    return await send_message(
        f"{icon} <b>Nouveau média ajouté</b>\n"
        f"<code>{title}{year_str}</code>"
    )

"""Settings API — application configuration management."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.services.telegram import send_message
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def get_settings():
    """Return current application settings (non-sensitive)."""
    return {
        "telegram": {
            "configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
            "bot_token_set": bool(settings.TELEGRAM_BOT_TOKEN),
            "chat_id_set": bool(settings.TELEGRAM_CHAT_ID),
        },
        "tmdb": {
            "configured": bool(settings.TMDB_API_KEY),
        },
        "auth": {
            "jwt_expiration_hours": settings.JWT_EXPIRATION_HOURS,
        },
        "cors": {
            "origins": settings.cors_origin_list,
        },
        "scheduler": {
            "health_check_interval": "60s",
        },
    }


class TelegramTestPayload(BaseModel):
    message: str = "🧪 Test de notification ArrMada"


@router.post("/telegram/test")
async def test_telegram(payload: TelegramTestPayload):
    """Send a test Telegram notification."""
    success = await send_message(payload.message)
    return {"success": success}

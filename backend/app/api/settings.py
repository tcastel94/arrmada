"""Settings API — application configuration management."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.services import auth_store
from app.services.telegram import send_message
from app.utils.logger import get_logger


def app_version() -> str:
    """Version exposed by the FastAPI app (single source: app.main)."""
    try:
        from app.main import app

        return app.version
    except Exception:  # pragma: no cover - defensive
        return "unknown"

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
            # True while no admin password exists (instance unclaimed).
            "default_secret": not auth_store.is_password_set(),
            # "file" (hashed, changeable in the UI) or "env" (legacy
            # ARRMADA_AUTH_SECRET, plaintext in .env).
            "password_source": auth_store.password_source(),
        },
        "cors": {
            "origins": settings.cors_origin_list,
        },
        "scheduler": {
            "health_check_interval": "60s",
        },
        "version": app_version(),
    }


class TelegramTestPayload(BaseModel):
    message: str = "🧪 Test de notification ArrMada"


@router.post("/telegram/test")
async def test_telegram(payload: TelegramTestPayload):
    """Send a test Telegram notification."""
    success = await send_message(payload.message)
    return {"success": success}

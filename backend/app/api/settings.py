"""Settings API — application configuration management."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.deps import get_current_user, get_db, require_admin
from app.config import settings
from app.services import auth_store, modules
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
        "version": __version__,
    }


class TelegramTestPayload(BaseModel):
    message: str = "🧪 Test de notification ArrMada"


@router.post("/telegram/test")
async def test_telegram(payload: TelegramTestPayload):
    """Send a test Telegram notification."""
    success = await send_message(payload.message)
    return {"success": success}


# ── Équipement facultatif (TV, tablette, ampli, caméras) ──────
class ModulesPayload(BaseModel):
    tv: bool | None = None
    tablet: bool | None = None
    amplifier: bool | None = None
    cameras: bool | None = None


@router.get("/modules")
async def get_modules(db: AsyncSession = Depends(get_db)):
    """Which optional modules are enabled (explicit choice, else detected)."""
    return {"modules": await modules.get_modules(db)}


@router.put("/modules", dependencies=[Depends(require_admin)])
async def put_modules(payload: ModulesPayload, db: AsyncSession = Depends(get_db)):
    """Save the household's equipment choices (setup wizard or Settings)."""
    modules.save_choices({k: v for k, v in payload.model_dump().items() if v is not None})
    return {"modules": await modules.get_modules(db)}

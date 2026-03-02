"""Application configuration via environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/arrmada.db"

    # ── Auth ──────────────────────────────────────────────────
    ARRMADA_AUTH_SECRET: str = "changeme_use_a_strong_password"
    JWT_SECRET_KEY: str = ""  # auto-derived from AUTH_SECRET if empty
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # ── Encryption (Fernet) ───────────────────────────────────
    FERNET_KEY: str = ""  # auto-generated on first run if empty

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3420,http://192.168.2.3:3420"

    # ── Telegram ──────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # ── TMDB ──────────────────────────────────────────────────
    TMDB_API_KEY: str = ""

    # ── Unraid ────────────────────────────────────────────────
    UNRAID_URL: str = ""
    UNRAID_API_KEY: str = ""
    UNRAID_USERNAME: str = ""
    UNRAID_PASSWORD: str = ""

    # ── Misc ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def effective_jwt_secret(self) -> str:
        """Return JWT secret, falling back to auth secret."""
        return self.JWT_SECRET_KEY or self.ARRMADA_AUTH_SECRET


settings = Settings()

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

    # ── Storage ───────────────────────────────────────────────
    # Everything persistent lives here (SQLite DB, Fernet key, JWT secret,
    # admin password hash): mount this ONE directory as a volume.
    DATA_DIR: str = "data"

    # ── Database ──────────────────────────────────────────────
    # SQLite by default (zero config). PostgreSQL: see docker-compose.postgres.yml
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/arrmada.db"

    # ── Auth ──────────────────────────────────────────────────
    # The admin password is created in the setup wizard and stored hashed in
    # DATA_DIR. ARRMADA_AUTH_SECRET is only a legacy fallback (see auth_store).
    ARRMADA_AUTH_SECRET: str = ""
    JWT_SECRET_KEY: str = ""  # auto-generated in DATA_DIR if empty
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # ── Encryption (Fernet) ───────────────────────────────────
    FERNET_KEY: str = ""  # auto-generated on first run if empty

    # ── CORS ──────────────────────────────────────────────────
    # Empty by default: the UI calls the API on the SAME origin (/api is
    # proxied by Next.js), so no cross-origin access is needed. Only set this
    # when the frontend is served from another host/port than the API.
    CORS_ORIGINS: str = ""

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

    # ── AI / OpenRouter ───────────────────────────────────────
    OPENROUTER_API_KEY: str = ""
    AI_MODEL: str = "google/gemini-2.0-flash-001"  # cost-effective, fast

    # ── Misc ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

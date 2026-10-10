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

    # ── Web app vue depuis le réseau local ────────────────────
    # Sert aux QR codes affichés sur les TV (appairage). Vide = déduite de
    # l'adresse utilisée par Kodi, en remplaçant le port 8420 par 3420.
    PUBLIC_WEB_URL: str = ""

    # ── Dépôt Kodi (mises à jour de l'add-on) ─────────────────
    # Dossier `kodi-addon/` du dépôt Git. Vide = /app/kodi-addon (monté par
    # docker-compose.yml) ou, en développement, celui du dépôt.
    KODI_ADDON_DIR: str = ""

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
    # Local Ollama on the NAS — primary engine for log analysis (OpenRouter = fallback)
    OLLAMA_URL: str = "http://192.168.2.3:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"

    # ── Auto-import ───────────────────────────────────────────
    # Scheduled job that imports completed-but-orphaned downloads.
    # Set AUTO_IMPORT_ENABLED=false to stop it entirely.
    AUTO_IMPORT_ENABLED: bool = True
    AUTO_IMPORT_INTERVAL_MINUTES: int = 5
    # Safety: the scheduled job never replaces an episode/movie that
    # already has a file — *arr parsers do mis-map releases (e.g. anime
    # cour numbering), and an unattended overwrite is unrecoverable.
    # Only explicit, user-initiated imports may overwrite.
    AUTO_IMPORT_ALLOW_OVERWRITE: bool = False
    # Completed-downloads folder as seen from inside Sonarr/Radarr.
    # Keep it on the same mount as the library: a separate Docker bind
    # mount of the same share still fails link() with EXDEV, turning
    # every import into a multi-GB copy.
    ARR_DOWNLOADS_PATH: str = "/media/downloads/complete"

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

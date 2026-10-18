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

    # ── Artworks (logos, disques, clearart, bannières, fonds…) ─
    # Trois sources, combinables :
    #  - fanart.tv : logos HD, disques Blu-ray/DVD, clearart, bannières,
    #    vignettes, affiches, fonds (toutes les variantes). Deux clés possibles,
    #    à créer sur https://fanart.tv/get-an-api-key/ :
    #      FANART_CLIENT_KEY = clé PERSONNELLE (compte gratuit) — suffit seule,
    #        et les nouvelles images arrivent après 2 jours au lieu de 7 ;
    #      FANART_API_KEY    = clé de PROJET (facultative si la personnelle est là).
    #  - TMDB (TMDB_API_KEY, déjà utilisée par « Pour toi ») : logos, affiches, fonds.
    #  - les dossiers des médias (poster.jpg, fanart.jpg, clearlogo.png,
    #    disc.png…) : prioritaires, ce sont tes images.
    FANART_API_KEY: str = ""
    FANART_CLIENT_KEY: str = ""
    # Lire les images rangées à côté des films / séries (chemins Radarr/Sonarr
    # traduits comme pour les NFO : services/scraper_service.map_path).
    ARTWORK_LOCAL_ENABLED: bool = True
    # Récupère tout seul les artworks des nouveaux titres (toutes les N heures).
    # Le bouton « Récupérer les artworks » de la web app reste disponible.
    ARTWORK_AUTO_ENABLED: bool = True
    ARTWORK_AUTO_INTERVAL_HOURS: int = 24

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
    # Packs de saison bloqués par Sonarr (« Single episode file contains all
    # episodes in seasons ») : fichiers « 01. Titre.mkv » rapprochés de leur
    # épisode (numéro ET titre vérifiés), puis import manuel automatique.
    # Voir app/services/blocked_imports.py. false = laisser à l'humain.
    AUTO_IMPORT_BLOCKED_PACKS: bool = True
    # Completed-downloads folder as seen from inside Sonarr/Radarr.
    # Keep it on the same mount as the library: a separate Docker bind
    # mount of the same share still fails link() with EXDEV, turning
    # every import into a multi-GB copy.
    ARR_DOWNLOADS_PATH: str = "/media/downloads/complete"

    # ── Caméras Eufy (via le conteneur eufy-security-ws) ──────
    # Ex. ws://192.168.2.3:8424 (EUFY_WS_PORT du pont) ; vide = pas de caméras. Détections relayées
    # vers la TV : person, ring, motion, pet, vehicle, package (virgules).
    EUFY_WS_URL: str = ""
    EUFY_DETECTIONS: str = "person"

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

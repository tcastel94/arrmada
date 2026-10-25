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
    # Optional, read-only: the folder holding the OTHER apps' config dirs
    # (Sonarr, Radarr, SABnzbd…). Lets ArrMada read their API keys itself.
    APPDATA_DIR: str = "/appdata"

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

    # ── Web app vue depuis le réseau local ────────────────────
    # Sert aux QR codes affichés sur les TV (appairage). Vide = déduite de
    # l'adresse utilisée par Kodi, en remplaçant le port 8420 par 3420.
    PUBLIC_WEB_URL: str = ""

    # ── Dépôt Kodi (mises à jour de l'add-on) ─────────────────
    # Dossier `kodi-addon/` du dépôt Git. Vide = /app/kodi-addon (monté par
    # docker-compose.yml) ou, en développement, celui du dépôt.
    KODI_ADDON_DIR: str = ""

    # ── Appli Android : mises à jour (ADR-009) ─────────────────
    # La CI publie l'APK signée dans la release GitHub ANDROID_UPDATE_TAG du
    # dépôt ANDROID_UPDATE_REPO ; le serveur la rapatrie dans ANDROID_APK_DIR
    # (empreinte SHA-256 vérifiée) et la propose aux TV et téléphones.
    # Dépôt vide : pas de GitHub, seulement les APK déposées à la main dans
    # ANDROID_APK_DIR (nom arrmada-<version>-<n°>-release.apk, sortie de build-apk.sh).
    ANDROID_UPDATE_REPO: str = "tcastel94/arrmada"
    ANDROID_UPDATE_TAG: str = "android-latest"
    ANDROID_APK_DIR: str = "data/apk"

    # ── Vidéos hors médiathèque (écran « Vidéos ») ────────────
    # Les dossiers déclarés dans la web app doivent être sous ce chemin
    # (garde-fou : jamais /app/data, /etc…). Vide = n'importe où.
    VIDEO_ALLOWED_BASE: str = "/mnt/user"

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
    # Local Ollama (e.g. http://192.168.1.10:11434) — primary engine for log
    # analysis when set, OpenRouter as fallback. Empty = no local AI.
    OLLAMA_URL: str = ""
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

    # ── Demandes lancées depuis la TV (services/tv_priority.py) ─
    # Tout ce qui est lancé depuis une TV passe en tête de SABnzbd (priorité
    # Force) : on veut le regarder ce soir. false = file normale pour tous.
    TV_PRIORITY_ENABLED: bool = True
    # Passe du « gardien » : une saison arrive en plusieurs NZB, chacun doit
    # être repassé en Force à son arrivée dans la file.
    TV_PRIORITY_INTERVAL_SECONDS: int = 15
    # Demande sans aucun téléchargement trouvé au bout de N heures : abandonnée.
    TV_REQUEST_TTL_HOURS: int = 24

    # ── Caméras Eufy (via le conteneur eufy-security-ws) ──────
    # Ex. ws://192.168.2.3:8424 (EUFY_WS_PORT du pont) ; vide = pas de caméras. Détections relayées
    # vers la TV : person, ring, motion, pet, vehicle, package (virgules).
    EUFY_WS_URL: str = ""
    EUFY_DETECTIONS: str = "person"

    # ── Appareils hors de la maison (VPN) ─────────────────────
    # Réseaux acceptés comme « locaux » pour les jetons d'appareil (TV,
    # téléphones), en plus des réseaux privés : ceux d'un VPN qui n'est pas
    # en 10.x / 192.168.x, ex. « 100.64.0.0/10 » pour Tailscale. Virgules.
    DEVICE_TRUSTED_NETWORKS: str = ""

    # ── Misc ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

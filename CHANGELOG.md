# Changelog

All notable changes to ArrMada will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Installeur de stack complète

#### Added
- `install.sh`: one-command install of Sonarr, Radarr, Prowlarr, Bazarr, SABnzbd, Deluge or qBittorrent, Jellyfin and ArrMada — platform detection (Unraid, Synology, Linux, macOS/WSL) for paths, PUID/PGID, timezone, IP, `/dev/dri`; TRaSH `/data` layout; pre-generated API keys and passwords in each app's config (never overwriting an existing file); existing containers detected and kept; port check; `docker:cli` fallback when Compose is missing; generated `compose.sh`, `credentials.txt` and `stack.json`; Jellyfin first-run wizard automated (admin account, libraries, API key); `--dry-run`, `--uninstall`; bash 3.2 compatible, shellcheck clean
- Wiring: root folders `/data/media/tv` / `/data/media/movies` for installer-created stacks; torrent passwords read from `stack.json`
- CI: installer shellcheck, dry-run matrix (4 platforms × 3 torrent options) and bash 3.2 run
- `docs/installer.md`

#### Fixed
- Jellyfin ≥ 10.11 authentication (health check, Cast, connection test): `Authorization: MediaBrowser Token` / `ApiKey` sent alongside the legacy forms, which now answer 401
- Jellyfin API key read from `jellyfin.db` even while still in the WAL journal (read-only mount)
- Jellyfin without an API key is reported as "create a key", not "unreachable"

### Auto-configuration de la stack

#### Added
- **Settings → Auto-configuration** (and in the setup wizard): reads API keys from the apps' own config files (appdata folder mounted read-only at `/appdata`) — Sonarr, Radarr, Lidarr, Readarr, Prowlarr (`config.xml`), Bazarr (`config.yaml` / `config.ini`), SABnzbd (`sabnzbd.ini`), Jellyfin (`jellyfin.db`), Deluge (`web.conf` / `core.conf`), qBittorrent (`qBittorrent.conf`)
- Address probing: each app is located (LAN IP, Docker DNS name, Docker host) and validated **with its own key**
- Plan / apply wiring: register apps in ArrMada, Prowlarr → apps (full sync), download clients in every *arr with a dedicated category, Bazarr → Sonarr/Radarr; idempotent, each entry tested by the target app before saving, warnings saved with `forceSave`, one retry on transient failures
- SABnzbd categories created when missing; Deluge Label plugin enabled automatically for categories
- Deluge / qBittorrent default passwords detected from their hashes; qBittorrent 5 login (204 + `QBT_SID_<port>` cookie) supported
- `POST /api/stack/plan`, `POST /api/stack/apply` (authenticated; secrets never sent to the browser)

### Installation zéro configuration — image unique

#### Added
- **Single Docker image** `ghcr.io/tcastel94/arrmada` (amd64 + arm64): UI + API in one container, **one port (3420)**, no `.env` required
- `docker/gateway.js`: dependency-free Node gateway routing `/api/*` to FastAPI and the rest to Next.js; streams SSE unbuffered, no 30 s timeout, forwards the client IP (per-client login rate limiting) and the original Host/Proto (works behind any HTTPS reverse proxy)
- First-run **admin password creation** in the setup wizard (new « Sécurité » step) and on the login page for instances without a password; stored as a scrypt hash in `data/.admin_password`
- Password change in Settings (current password required); migrates a legacy `ARRMADA_AUTH_SECRET` to a hash
- `arrmada-cli` inside the container: `set-password`, `reset-password`, `status`
- JWT secret auto-generated per instance (`data/.jwt_secret`)
- `PUID` / `PGID` support (data dir ownership, processes run unprivileged)
- SSE keep-alive comment every 15 s (proxies no longer drop idle streams, dead clients are detected)
- `docker-compose.postgres.yml` overlay for optional PostgreSQL; `docs/deploy-unraid.md` migration guide
- CI: image build + smoke test; release workflow publishing multi-arch images on `main` and `v*` tags

#### Changed
- SQLite is now the default database (WAL mode + busy timeout)
- The UI calls the API on the same origin (`/api/...`): no more hard-coded `:8420`, CORS closed by default
- `ARRMADA_AUTH_SECRET` is optional and legacy; shipped placeholders (`changeme…`) are **refused**
- Webhook URLs now use port 3420 (`http://<host>:3420/api/webhooks/sonarr`)

#### Removed
- `backend/Dockerfile`, `frontend/Dockerfile`, the 3-container compose and the hard-coded `/mnt/user` mount

#### Fixed
- Backend tests: login rate limiter reset between tests (15 tests were erroring on `main`)

### UI v2 — « Neon Armada »

#### Added
- New dark-only design system: #4A9EFF / brand-cyan tokens, glassmorphism, animated aurora background, grain, shimmer skeletons, Geist fonts (bundled, no Google Fonts at build time)
- Motion kit: animated counters, ring gauges, 3D-tilt posters, mouse spotlight, gradient progress bars, page transitions, `prefers-reduced-motion` support
- App shell: floating animated sidebar with live badges (downloads, unread, missing), breadcrumb header with live (SSE) indicator and notifications popover, floating mobile tab bar, global mini-player following Kodi playback
- Command palette (⌘K / `/`): direct media sheets, all pages, actions (Kodi sync, refresh, mark all read, add a title)
- Keyboard shortcuts `g` + key, `[` (sidebar), `?` (cheat-sheet)
- Real-time toasts on imports, grabs and service outages
- **Dashboard** "command bridge": greeting + fleet summary, KPIs with gauges, services strip, recently-added carousel, unified activity, live queue, this week's releases, storage, TRaSH compliance
- **Salon** page (`/remote`): Kodi player (seekable slider, ±10/30 s, volume), Yamaha amp remote, Cast devices
- **Santé médiathèque** hub (`/health`): quality / duplicates / cleanup with health score and per-row actions
- Settings hub with sub-navigation (general, *arr services, Kodi, Cast & Jellyfin, Yamaha)
- Media library: URL state, grid/list views, filter chips, cross-page selection + floating action bar; Missing: bulk search with progress & stop; Search: manual add by TMDB/TVDB id, preview, streaming-style suggestion rails
- Media sheet split into components with cinematic hero, accessible seasons accordion with "upcoming" state, sortable/filterable releases
- Downloads hub (queue + imports), calendar month/agenda views, grouped notifications, unified indexers table, live server resources + Docker panel, analytics with table views
- `?refresh=1` on `/api/cleanup` and `/api/quality`; `start`/`end` on `/api/calendar`; `category` filter and `POST /api/services/test`; `PUT` for Kodi/Yamaha settings; version + default-secret flag in `/api/settings`

#### Changed
- Navigation reorganised; legacy URLs (`/quality`, `/duplicates`, `/cleanup`, `/fichiers`, `/docker`, `/requests`, `/recommendations`, `/services`, `/settings/profile-overrides`, `/settings/sabnzbd-config`) redirect to their new home
- French UI everywhere (tutoiement), French byte units (Go, To) from the backend too, genres displayed in French
- Kodi now-playing polling is adaptive (3 s while playing, 20 s idle, 60 s when unreachable)

#### Fixed
- Toasts from the legacy `useToast` hook were never rendered (TRaSH Guides, Settings)
- Naive UTC timestamps displayed 1–2 h off; calendar shifted by one day (UTC keys); past months empty
- Wrong series added from TMDB trending (TMDB id treated as TVDB); broken "because you have…" suggestions
- Series quality showed the numeric Sonarr profile id; movie crew always empty
- Kodi/Yamaha devices health-checked with the *arr client and listed as *arr services
- Media deletion without cache invalidation, scraper offered for series, stale edit dialogs, unaired episodes flagged as missing, duplicated imports in the activity timeline, Docker failures returned as HTTP 200
- `alert()`/`confirm()` replaced by toasts and confirmation dialogs everywhere; error states instead of blank pages
- Collapsing the sidebar left an empty gutter; menu double highlight; backend outage redirected to the setup wizard
- TypeScript errors that broke `tsc --noEmit` in CI

#### Security
- `GET /api/kodi/settings` no longer returns the decrypted Kodi password; empty password on update keeps the stored one

### Platform

#### Added
- Rate limiting on `/api/auth/login` (5 attempts/minute) to prevent brute force
- Security headers: HSTS, CSP, Permissions-Policy
- CI/CD pipeline via GitHub Actions (lint, test, build)
- Test coverage for media, downloads, analytics, duplicates, recommendations, requests, search endpoints
- Security-specific tests (headers, rate limiting)
- `.dockerignore` for smaller production images
- `pyproject.toml` with ruff, pytest, and coverage configuration
- OpenAPI examples in Pydantic schemas for better Swagger docs
- Docker resource limits in `docker-compose.yml`
- Explicit Docker network (`arrmada-network`)

#### Changed
- CORS: restricted `allow_methods` and `allow_headers` (was `*`)
- Dockerfile: multi-stage build, non-root user, Python-based healthcheck
- docker-compose: removed deprecated `version` field, Python-based healthcheck

#### Security
- Fixed overly permissive CORS configuration
- Added brute force protection via rate limiting
- Added HSTS header for transport security
- Added Content-Security-Policy header
- Docker container now runs as non-root user

## [0.1.0] — 2025-12-15

### Added
- Initial release
- Unified dashboard for all *arr services
- Cross-platform media search
- AI recommendations via scikit-learn
- Library analytics and charts
- Duplicate detection
- Overseerr-like media request system
- Real-time health monitoring
- Telegram notifications
- Dark mode UI
- JWT authentication with Fernet-encrypted API keys
- Docker Compose deployment

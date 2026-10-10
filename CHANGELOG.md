# Changelog

All notable changes to ArrMada will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Kodi app — phase 2 "wow screens" (ADR-003)

#### Added
- Kodi add-on 1.5.0: three new full-screen windows, built like the Home window (on-device rendering, network calls in background threads, no UI freeze)
- **Media detail** (OK on a poster or on a download): Ken Burns fanart, ClearLogo, year · runtime · rating · genres, TMDB / IMDb / Rotten Tomatoes scores, 4K / HDR / Atmos / Remux badges, scrolling synopsis, director and composer, poster with status, file details and subtitles
  - movies: cast rail with round photos (initials when there is no photo);
  - series: season cards with per-season progress, and the latest downloaded episode as the reference file;
  - actions: **Play** (device's Kodi library, with resume, plus the Yamaha preset of the device's room), **Trailer** (YouTube add-on, movies), **Better release** (Radarr/Sonarr search), **Subtitles** (Bazarr search, movies)
- **Downloads** (`action=queue`): the whole Radarr/Sonarr queue with progress bars, percentage, time left, estimated speed (from the remaining bytes between two refreshes), size and colour-coded status (downloading, paused, queued, import pending, error with its reason). Refreshed every 5 s in place, without flicker or losing the selection. Buttons *Pause all* / *Resume all*
- **Living room** (`action=salon`, also listed in the add-on menu): now playing on this device (art, title, resolution, audio, elapsed / total, end time, paused pill; −30 s, play/pause, +30 s, stop), read from Kodi itself so it works offline. Yamaha amplifier state (power, volume in % and dB, input, sound program) with volume, mute and power buttons, refreshed every 3 s and right after each command. *Living room* / *Cinema room* presets, with the device's own room marked
- Home header: *Downloads* and *Living room* buttons; quick actions gain *Detail*
- Pre-rendered progress bar textures (`progress/bar-000…100.png`, 2 % steps): Kodi's progress control cannot read list item properties
- Bench: detail, downloads, living-room and playback steps (25 screenshots), mock backend for media detail, queue and amplifier; silent demo video (Xvfb has no audio output, and Kodi's busy dialog would block other windows for 10 s)
- Tests: phase 2 data logic, and XML ↔ Python checks for all four windows, including "only the focused control is solid accent"

#### Changed
- Only the focused control is solid blue. The main button of a screen (*Play*, *Vol +*) is a blue tint when the focus is elsewhere, and a selected card only looks active while its list has the focus
- `<defaultcontrol always="false">` on every window: focus is kept when coming back from a sub-window

#### Fixed
- A paused SABnzbd showed "Downloading": Radarr/Sonarr keep `trackedDownloadState = downloading` and report the pause in `status`. Status now wins while downloading, the import step wins once downloaded
- Home: when only the "recently added" call failed, the poster rail was emptied and the cache overwritten. Both calls must now succeed before the display and the cache are replaced

#### Known limitations
- *Pause all* / *Resume all* act on the whole SABnzbd queue: the backend endpoints are global, not per item. Radarr/Sonarr show the pause after about a minute
- No deletion from the TV (ADR-003 decision 1), except in the legacy "[TELECHARG.]" menu, to be removed later

### Kodi app — phase 0 prototype (ADR-003)

#### Added
- Kodi add-on 1.4.2: full-screen **Home** window (WindowXML, Aeon Nox SiLVO fonts). It shows a fleet summary, four KPI tiles, live downloads (refreshed every 20 s), a "recently added" poster rail with focus zoom and glow, fanart backdrop, ClearLogo, tech badges and service status
- The window opens instantly from an on-device cache, then refreshes in a background thread (no network call in the UI thread). It has an offline mode, and a **Diagnostic** panel (font and glyph bench, system info, measured open / network / render times)
- Motion: staggered opening cascade, KPI count-up and animated progress bars (Python tweens), Ken Burns fanart, focused poster lift with breathing glow and badge pop, direction-aware info slide, poster rail slide-in when data arrives
- **Intro** (≈ 2.4 s, once per Kodi session, any key skips it): the two legs of the "A" join, the play button pops, two shockwaves, a light sweep, then wordmark and tagline. The home screen is revealed with its cascade afterwards
- **Remote control**:
  - long-press OK (Android TV "context menu") or the Menu key opens quick actions: *Play*, *Search a better release* (Radarr/Sonarr);
  - the Play/Pause key plays the movie from the device's Kodi library, matched by TMDB/TVDB id, then by title and year, with resume; for a series it opens its seasons;
  - a key-hint row is shown under the rail;
  - a **Search** button opens Kodi's keyboard, whose microphone allows voice input on Android
- **New brand: "Lecture" logo** (an "A" whose crossbar is a play button), vector, in the UI accent colours. `branding/arrmada-mark.svg` is the single source, and `branding/export.py` derives every image from it: favicon, app icons, share image, README banner, Kodi icon, fanart and intro layers. The web app draws it inline (`BrandMark` / `BrandIcon`); on the login page, the splash screen and the dashboard hero, the "A" draws itself and the play button pops
- Entry "Accueil ArrMada (apercu v2)" in the add-on, also reachable from the SiLVO menu with `RunPlugin(plugin://script.arrmada/?action=home)`
- Media items expose `fanart_url`
- CI job "Kodi add-on — Tests": ruff + pytest, without Kodi. It checks the home logic, cache, XML ↔ Python ids, SiLVO font names, texture files and unsupported glyphs
- Visual bench `kodi-addon/bench/run.sh`: real Kodi under Xvfb, mock backend with realistic posters and backdrops, SiLVO fonts, remote-control script, 11 screenshots, optional video (`RECORD=1`)
- `kodi-addon/tools/make_textures.py`: dependency-free generator for the window textures

#### Fixed
- `/api/kodi/widgets/recent` was not sorted (it sorted on a missing `added_at` key)
- Kodi download queue: `timeleft` was always empty and `size` always 0 (wrong source keys). Items now also carry `id` and `size_left`

### Server features (developed on the Unraid host, merged into UI v2)

#### Added
- **Kodi add-on** (`kodi-addon/`, v1.3.2) and its API under `/api/kodi`: live scrobbling, add-on dashboard and status, home-screen widgets, media lookup/add, interactive releases, queue pause/resume/remove, subtitle search & audio sync (Bazarr), library maintenance. The add-on authenticates with `X-Api-Key` = `ARRMADA_AUTH_SECRET`
- **Docker logs**: aggregated, level-classified logs from the service containers (`/api/files/docker/logs`, needs `/var/run/docker.sock:ro`) and AI analysis grouping problems with causes and fixes (`POST …/logs/analyze`, local Ollama or OpenRouter)
- **Local AI assistant** (Ollama): weekly summary of added media
- **Yamaha room profiles** (Salon / Cinéma): sound program, dialogue lift, DRC, enhancer, extra bass; applied automatically when playing a movie on Kodi
- Recommendations: "because you have…" for series too, TMDB detail modal endpoint, targeted recommendations based on a library title
- Media items expose resolution, video/audio codecs, HDR, channels, studio/network and ClearLogo
- Auto-import: scans the folder as seen by *arr (`ARR_DOWNLOADS_PATH`), never overwrites an existing file unless `AUTO_IMPORT_ALLOW_OVERWRITE=true`, execution reports
- Scripts: orphan import/cleanup, cinema audio profile, weekly summary
- UI (ported to the v2 design): technical badges on posters and media sheet, studio/network marks, ClearLogo title, trailer modal, split "Play on Kodi · room" button that also tunes the amp, saved library filter presets; TMDB detail modal and "from a title of your library" recommendations in Discover; Docker log stream + AI diagnosis in System → Docker; room profile editor (Settings → Yamaha) and room presets in the Salon

#### Fixed
- Yamaha room profiles crashed on save (`cache.set` does not exist) and were kept in memory only: now persisted to `data/yamaha_room_profiles.json`
- Series "because you have…" recommendations queried TMDB with the Sonarr TVDB id (wrong show)
- API-key authentication uses a constant-time comparison

#### Security
- The add-on no longer ships a hard-coded default API key; `.gitignore` now covers `.env.*` copies and `*.bak` files

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

<p align="center">
  <img src="docs/banner.png" alt="ArrMada Banner" width="100%"/>
</p>

<h1 align="center">🏴‍☠️ ArrMada</h1>

<p align="center">
  <strong>The unified dashboard for your *arr media stack</strong>
</p>

<p align="center">
  <a href="#-features"><img src="https://img.shields.io/badge/Features-✨-blue?style=for-the-badge" alt="Features"/></a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-🚀-green?style=for-the-badge" alt="Quick Start"/></a>
  <a href="#-screenshots"><img src="https://img.shields.io/badge/Screenshots-📸-purple?style=for-the-badge" alt="Screenshots"/></a>
  <a href="#-architecture"><img src="https://img.shields.io/badge/Architecture-🏗️-orange?style=for-the-badge" alt="Architecture"/></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Next.js_14-black?style=flat-square&logo=next.js&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"/>
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
</p>

---

## 🎯 What is ArrMada?

**ArrMada** is a self-hosted, unified dashboard that brings all your *arr services together in one beautiful interface. Stop switching between Sonarr, Radarr, Bazarr, and Prowlarr tabs — manage everything from a single pane of glass.

> Think of it as **Organizr**, but built specifically for the *arr ecosystem, with deep API integration instead of just iframes.

### Why ArrMada?

| Problem | ArrMada Solution |
|---------|-----------------|
| 🔀 Switching between 6+ tabs | One unified dashboard |
| 🔑 Managing API keys in configs | Setup Wizard with encrypted storage |
| 🧩 Painful self-hosting | One container, one port, zero config file |
| 📊 No cross-service analytics | Aggregated library statistics |
| 🔍 Searching across services | Unified search across all media |
| 📱 Apps don't look great on mobile | Responsive mobile-first design |

---

## ✨ Features

> 🎨 **Interface « Neon Armada »** — dark-only glassmorphism UI with animated aurora background, 3D-tilt posters, animated counters & gauges, page transitions and real-time toasts. Fully responsive (floating mobile tab bar) and `prefers-reduced-motion` aware.

### 🧭 Navigation
| Group | Pages |
|-------|-------|
| — | **Dashboard** (command bridge) · **Salon** (Kodi / Yamaha / Cast remote) |
| Bibliothèque | Médiathèque · Manquants · Calendrier · Rechercher & Ajouter |
| Activité | Téléchargements (queue + imports) · Journal · Notifications |
| Maintenance | Santé médiathèque (qualité, doublons, nettoyage) · TRaSH Guides (profils, overrides, SABnzbd) · Indexers |
| Système | Serveur & Docker · Statistiques |
| ⚙️ | Paramètres (général, services *arr, Kodi, Cast & Jellyfin, ampli Yamaha) |

Legacy URLs (`/quality`, `/duplicates`, `/cleanup`, `/fichiers`, `/docker`, `/requests`, `/recommendations`, `/services`, `/settings/profile-overrides`, `/settings/sabnzbd-config`) redirect to their new location.

### ⌨️ Keyboard-first
| Shortcut | Action |
|----------|--------|
| `⌘K` / `Ctrl+K` / `/` | Command palette: open a media sheet, jump to a page, run an action (Kodi sync, refresh, mark all read…) |
| `g` then `d` `r` `m` `x` `c` `s` `t` `j` `n` `h` `i` `y` `p` | Go to Dashboard, Salon, Médiathèque, Manquants, Calendrier, Recherche, Téléchargements, Journal, Notifications, Santé, Indexers, Serveur, Paramètres |
| `[` | Collapse / expand the sidebar |
| `?` | Shortcut cheat-sheet |

### 🧙 Setup Wizard
Auto-discover your *arr services on the local network or configure them manually. API keys are **encrypted at rest** with Fernet (AES-128-CBC).

### 📊 Command Bridge (Dashboard)
Greeting with live fleet summary, animated KPIs (films, séries, stockage, téléchargements) with ring gauges, services health strip, recently-added carousel, unified activity timeline, live download queue, this week's releases, disk usage and TRaSH compliance.

### 🔍 Search & Add
Unified title search, natural-language AI search, TMDB trending / "because you have…" suggestions and request tracking — all in one hub.

### 🎬 Detailed Media View
Cinematic hero, seasons & episodes, cast & filmography, files & quality, interactive release search, Bazarr subtitles, TRaSH profile overrides, Kodi playback & Chromecast casting.

### 📥 Downloads & Imports
Live SABnzbd / Deluge queue with per-item actions (retry, blocklist, remove) and an Imports tab for stuck downloads, manual/bulk import and auto-import history.

### 🔔 Real-time
Server-Sent Events keep every page fresh and raise toasts on imports, grabs and service outages; a floating mini-player follows Kodi playback across pages.

### 🛡️ Security First
- Admin password created in the setup wizard, stored as a scrypt hash (no default password)
- JWT authentication with a per-instance random secret
- Fernet-encrypted API keys at rest
- Rate limiting (anti brute-force)
- HSTS, CSP, Permissions-Policy headers
- Non-root Docker container
- Same-origin API (CORS closed by default)

---

## 📸 Screenshots

<p align="center">
  <img src="docs/screenshot-wizard.png" alt="Setup Wizard" width="48%"/>
  <img src="docs/screenshot-dashboard.png" alt="Dashboard" width="48%"/>
</p>

<p align="center">
  <em>Left: Setup Wizard with network discovery — Right: Dashboard overview</em>
</p>

<p align="center">
  <img src="docs/screenshot-config.png" alt="Service Configuration" width="48%"/>
</p>

<p align="center">
  <em>Service configuration with type selection, URL, and encrypted API key storage</em>
</p>

---

## 🚀 Quick Start

**One container, one port, no `.env` file.** Works on any machine running Docker:
Linux server, Synology, Unraid, TrueNAS, Windows/macOS (Docker Desktop), Raspberry Pi
(images are published for `amd64` and `arm64`).

### Linux server / NAS over SSH

```bash
mkdir -p /opt/arrmada && cd /opt/arrmada
curl -fsSLO https://raw.githubusercontent.com/tcastel94/arrmada/main/docker-compose.yml
docker compose up -d
```

### Synology (DSM 7.2+)

1. **File Station**: create the folder `docker/arrmada`.
2. **Container Manager → Project → Create**: path `/volume1/docker/arrmada`,
   source *Create docker-compose.yml*, paste [docker-compose.yml](docker-compose.yml).
3. Optionally set `PUID`/`PGID` to your DSM user (`id` over SSH, often `1026`/`100`).

### Windows / macOS

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), save
[docker-compose.yml](docker-compose.yml) in a folder, then `docker compose up -d` in that folder.

### Then

Open **`http://<machine-ip>:3420`**: the setup wizard creates the admin password,
scans your network for Sonarr/Radarr/Prowlarr/SABnzbd… and stores the API keys encrypted. 🧙

| Task | Command |
|------|---------|
| Update | `docker compose pull && docker compose up -d` |
| Logs | `docker logs -f arrmada` |
| Forgot password | `docker exec -it arrmada arrmada-cli set-password` |
| Backup | copy the `./data` folder (database, keys, password hash) |

> **Behind a reverse proxy** (Synology, Traefik, Nginx Proxy Manager, Caddy): proxy
> everything to port `3420`. The UI calls the API on the same origin, so HTTPS and
> custom domains work without extra settings.

---

## 🏗️ Architecture

```
┌──────────────────── conteneur arrmada ────────────────────┐
│                                                           │
│  :3420  gateway.js ──┬── /api/* ──► FastAPI   127.0.0.1:8420 │
│  (seul port exposé)  └── reste  ──► Next.js   127.0.0.1:3421 │
│                                                           │
│  /app/data : SQLite · clé Fernet · secret JWT · hash admin │
└───────────────────────────────────────────────────────────┘
```

The gateway is a ~100-line dependency-free Node proxy: it streams Server-Sent Events
without buffering, has no 30 s timeout, and forwards the client IP (login rate limiting).

### Supported Services

| Service | Type | Default Port | Integration |
|---------|------|:----:|-------------|
| 📺 Sonarr | TV Shows | 8989 | Full (library, search, import) |
| 🎬 Radarr | Movies | 7878 | Full (library, search, import) |
| 🎵 Lidarr | Music | 8686 | Health monitoring |
| 📚 Readarr | Books | 8787 | Health monitoring |
| 🔍 Prowlarr | Indexers | 9696 | Health monitoring |
| 💬 Bazarr | Subtitles | 6767 | Subtitle management |
| 🍿 Jellyfin | Media Server | 8096 | Health monitoring |
| ⬇️ SABnzbd | Downloader | 8080 | Download monitoring |

---

## 🐘 Database

**SQLite** by default (`./data/arrmada.db`, WAL mode): nothing to configure.

> Keep `./data` on a **local disk**: SQLite must not live on an NFS/SMB share.

To use **PostgreSQL**, combine the two compose files:

```bash
echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)" >> .env
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up -d
```

For an external PostgreSQL server, set
`DATABASE_URL=postgresql+asyncpg://user:password@host:5432/arrmada`.

Migrating the former 3-container Unraid deployment: see [docs/deploy-unraid.md](docs/deploy-unraid.md).

---

## 🛠️ Development

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000 — /api is proxied to :8000 in dev
```

### Docker image

```bash
docker build -t ghcr.io/tcastel94/arrmada:latest .
docker compose up -d
```

### Running Tests

```bash
cd backend
python -m pytest -v --cov
```

### Linting

```bash
cd backend
ruff check .
ruff format .
```

---

## 🔒 Security

| Layer | Implementation |
|-------|---------------|
| **Authentication** | scrypt-hashed admin password · JWT (HS256) with auto-generated secret |
| **API Key Storage** | Fernet encryption (AES-128-CBC) at rest |
| **Rate Limiting** | 5 attempts/min on login endpoint |
| **Headers** | HSTS, CSP, X-Frame-Options, Permissions-Policy |
| **CORS** | Same-origin by default (no cross-origin access) |
| **Docker** | Non-root user, multi-stage build |
| **Database** | Connection pooling, prepared statements |

> See [ADR-002: Security Architecture](docs/adr/002-security-architecture.md) for detailed rationale.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG](CHANGELOG.md) | Version history (Keep a Changelog format) |
| [ADR-001](docs/adr/001-unified-arr-stack.md) | Tech stack decisions |
| [ADR-002](docs/adr/002-security-architecture.md) | Security architecture |
| [.env.example](.env.example) | Environment variables reference |

---

## 🗺️ Roadmap

- [x] Unified dashboard with real-time stats
- [x] Setup Wizard with network discovery
- [x] Encrypted API key storage
- [x] PostgreSQL support
- [x] CI/CD pipeline (GitHub Actions)
- [x] Security hardening (HSTS, CSP, rate limiting)
- [x] Docker multi-stage production build
- [x] UI v2 « Neon Armada » (design system, command palette, keyboard shortcuts, real-time toasts)
- [x] Living-room remote (Kodi, Yamaha, Chromecast)
- [x] Media detail view with cast & subtitles
- [x] Duplicate media detection (Santé médiathèque)
- [ ] AI-powered recommendations (TMDB)
- [ ] Notification center (Telegram, Discord)
- [ ] Mobile app (React Native)
- [ ] Multi-user support with RBAC

---

## 🤝 Contributing

Contributions are welcome! Please read the [CHANGELOG](CHANGELOG.md) to understand the current state of the project.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with ☠️ by the ArrMada crew
</p>

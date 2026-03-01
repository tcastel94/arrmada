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
| 📊 No cross-service analytics | Aggregated library statistics |
| 🔍 Searching across services | Unified search across all media |
| 📱 Apps don't look great on mobile | Responsive mobile-first design |

---

## ✨ Features

### 🧙 Setup Wizard
Auto-discover your *arr services on the local network or configure them manually. API keys are **encrypted at rest** with Fernet (AES-128-CBC).

### 📊 Unified Dashboard
Real-time overview of your entire media library: movies, series, storage, downloads, and service health — all in one view.

### 🔍 Unified Search
Search across Sonarr, Radarr, and more simultaneously. Find any media in your library or search for new content to add.

### 🎬 Detailed Media View
Browse your library with rich metadata: cast, subtitles, file quality, storage size. Take actions like downloading directly.

### 📥 Download Manager
Monitor active downloads across SABnzbd with real-time progress, speed, and ETA.

### 🔔 Notifications
Telegram integration for import events, health alerts, and more.

### 🛡️ Security First
- JWT authentication with configurable expiration
- Fernet-encrypted API keys at rest
- Rate limiting (anti brute-force)
- HSTS, CSP, Permissions-Policy headers
- Non-root Docker container
- CORS with explicit origin whitelist

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

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- At least one *arr service running on your network

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/arrmada.git
cd arrmada
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your admin password:

```env
ARRMADA_AUTH_SECRET=your_secure_password_here
```

> **That's it!** API keys for Sonarr, Radarr, etc. are configured through the Setup Wizard. No need to add them to `.env`.

### 3. Launch

```bash
docker compose up -d
```

### 4. Open ArrMada

Navigate to `http://your-server:3420` — the Setup Wizard will guide you through the rest! 🧙

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Docker Compose                    │
├────────────────┬─────────────────┬───────────────────┤
│   Frontend     │    Backend      │   PostgreSQL      │
│   Next.js 14   │    FastAPI      │   16-alpine       │
│   :3420        │    :8420        │   :5432 (internal) │
│                │                 │                   │
│   TypeScript   │    Python 3.10+ │   Persistent      │
│   Tailwind CSS │    SQLAlchemy   │   Volume           │
│   shadcn/ui    │    Pydantic     │                   │
│   React Query  │    Fernet       │                   │
└────────────────┴─────────────────┴───────────────────┘
         │                 │                │
         └────── arrmada-network ───────────┘
```

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

ArrMada uses **PostgreSQL** by default (included in the Docker stack). No configuration needed.

### Use an external PostgreSQL database

If you already have a PostgreSQL server, set the connection string in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@your-host:5432/arrmada
```

Then remove (or comment out) the `arrmada-db` service in `docker-compose.yml`.

### Use SQLite (development only)

For local development without Docker:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/arrmada.db
```

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
npm run dev
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
| **Authentication** | JWT Bearer tokens (HS256) |
| **API Key Storage** | Fernet encryption (AES-128-CBC) at rest |
| **Rate Limiting** | 5 attempts/min on login endpoint |
| **Headers** | HSTS, CSP, X-Frame-Options, Permissions-Policy |
| **CORS** | Explicit origin whitelist |
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
- [ ] Media detail view with cast & subtitles
- [ ] Duplicate media detection
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

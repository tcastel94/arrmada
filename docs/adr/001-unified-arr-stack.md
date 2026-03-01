# ADR-001: Unified *arr Stack with FastAPI + Next.js

## Status

Accepted

## Context

Managing multiple *arr services (Sonarr, Radarr, Lidarr, Readarr, Prowlarr, Bazarr) plus Jellyfin and SABnzbd requires switching between many different dashboards. Each service has its own UI, authentication, and API. This creates friction for daily operations.

## Decision

Build a unified frontend dashboard (**ArrMada**) that aggregates all services into a single interface.

### Technology choices:

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Backend | **FastAPI** (Python) | Async-first, auto OpenAPI docs, Pydantic validation |
| Frontend | **Next.js 14** (TypeScript) | App Router, SSR/CSR flexibility, large ecosystem |
| Database | **SQLite** (async via aiosqlite) | Zero-config, single-file, sufficient for single-user |
| ORM | **SQLAlchemy 2.x** (async) | Mature, typed, migration support via Alembic |
| UI Components | **shadcn/ui** + Tailwind CSS | Composable, accessible, themeable |
| Animations | **Framer Motion** | Smooth micro-animations, React-native integration |
| Auth | **JWT** (HS256) | Stateless, simple, no external auth provider needed |
| Encryption | **Fernet** | Symmetric encryption for API keys in DB |

### Key patterns:

- **Service-as-client**: Each *arr service is wrapped in a typed client class inheriting from `ArrBaseClient`
- **Aggregator pattern**: `media_aggregator.py` fans out requests to all services concurrently
- **Encrypted storage**: API keys are Fernet-encrypted before DB storage, never exposed in API responses
- **PIN-based auth**: Single-user mode with a shared secret (appropriate for home lab use)

## Consequences

### Positive
- Single dashboard for all media operations
- Unified search across library + indexers
- Cross-service analytics and duplicate detection
- Consistent dark UI with modern design patterns

### Negative
- Single point of failure — if ArrMada is down, must use individual UIs
- SQLite limits to single-writer concurrency (acceptable for single-user)
- Additional maintenance burden for the wrapper layer

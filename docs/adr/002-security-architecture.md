# ADR-002: Security Architecture

## Status

Accepted

## Context

ArrMada exposes a web API that controls media services on a home network. While it is intended for personal/home lab use, it still needs to follow security best practices to prevent:

1. Unauthorized access to the dashboard
2. Exposure of API keys stored in the database
3. Brute force attacks on the login endpoint
4. Common web vulnerabilities (XSS, clickjacking, CSRF)

## Decision

### Authentication
- **JWT tokens** (HS256) with configurable expiration (default 24h)
- **Bearer token** via `Authorization` header or `arrmada_token` cookie
- **No refresh tokens** — session expires, user re-authenticates (acceptable for single-user)

### API Key Protection
- **Fernet symmetric encryption** for all service API keys stored in the database
- Key auto-generated on first run and persisted in `data/.fernet_key`
- API keys **never exposed** in API responses (`ServiceResponse` schema excludes `api_key`)

### Rate Limiting
- **slowapi** on `/api/auth/login` — 5 attempts per minute per IP
- Returns HTTP 429 when exceeded

### Security Headers
All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### CORS
- **Explicit origins** from configuration (no wildcards)
- **Restricted methods**: GET, POST, PUT, DELETE, PATCH
- **Restricted headers**: Authorization, Content-Type, Accept

### Docker
- Container runs as **non-root user** (`arrmada`)
- Resource limits enforced via docker-compose

## Consequences

### Positive
- Defense in depth — multiple layers of protection
- API keys cannot be extracted even with DB access (without Fernet key)
- Brute force protection prevents credential stuffing
- Security headers mitigate common web attacks

### Negative
- Rate limiting is IP-based — may block legitimate use behind shared NAT
- Fernet key file must be backed up (loss = re-configure all API keys)
- CSP may need adjustment if embedding external resources

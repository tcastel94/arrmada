# syntax=docker/dockerfile:1.7
# ╔════════════════════════════════════════════════════════════╗
# ║   ArrMada — image unique (interface + API dans 1 conteneur)  ║
# ╚════════════════════════════════════════════════════════════╝
#
# Dans le conteneur, 3 processus supervisés par docker/entrypoint.sh :
#   gateway.js (0.0.0.0:3420, SEUL port exposé)
#     ├─ /api/* → FastAPI / uvicorn  127.0.0.1:8420
#     └─ reste  → Next.js standalone 127.0.0.1:3421
#
# Multi-architecture (amd64 + arm64) :
#   docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/<owner>/arrmada .
# L'étape « web-build » tourne sur l'architecture de la machine de build
# ($BUILDPLATFORM) : elle ne produit que du JavaScript, inutile de
# l'émuler (sous QEMU, un build Next.js arm64 prend 10× plus de temps).

ARG NODE_VERSION=20
ARG PYTHON_VERSION=3.11

# ── 1. Build de l'interface (Next.js → sortie « standalone ») ─────────
FROM --platform=$BUILDPLATFORM node:${NODE_VERSION}-bookworm-slim AS web-build
WORKDIR /src
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── 2. Dépendances Python (architecture cible : roues natives) ─────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS api-build
WORKDIR /build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── 3. Binaire Node.js de l'architecture cible ────────────────────────
FROM node:${NODE_VERSION}-bookworm-slim AS node-runtime

# ── 4. Image finale ───────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm

LABEL org.opencontainers.image.title="ArrMada" \
      org.opencontainers.image.description="Unified dashboard for your *arr media stack" \
      org.opencontainers.image.source="https://github.com/tcastel94/arrmada" \
      org.opencontainers.image.licenses="MIT"

# Aucun paquet apt à installer : l'image python:slim contient déjà tout
# ce que le binaire node requiert (libstdc++6, libgcc_s) ainsi que
# setpriv (changement d'UID) et bash 5 (supervision des processus).
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=api-build /install /usr/local

WORKDIR /app

# API (le .dockerignore écarte tests, scripts de debug, data locale…)
COPY backend/ ./
# Interface : serveur standalone + fichiers statiques
COPY --from=web-build /src/.next/standalone ./web/
COPY --from=web-build /src/.next/static ./web/.next/static
COPY --from=web-build /src/public ./web/public
# Add-on Kodi, servi aux TV en dépôt (/kodi/repo) : embarqué pour que le
# dépôt marche sans clone Git. Un montage ./kodi-addon:/app/kodi-addon:ro
# le remplace (nouvelle version proposée aux TV après un simple git pull).
COPY kodi-addon/script.arrmada ./kodi-addon/script.arrmada
# Passerelle, démarrage, outils d'admin
COPY docker/gateway.js ./docker/gateway.js
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/arrmada-cli /usr/local/bin/arrmada-cli
COPY docker/healthcheck.py /usr/local/bin/arrmada-healthcheck
RUN chmod 0755 /usr/local/bin/entrypoint.sh /usr/local/bin/arrmada-cli /usr/local/bin/arrmada-healthcheck \
    && mkdir -p /app/data

# Valeurs par défaut — toutes surchargeables dans le compose.
ENV DATA_DIR=/app/data \
    PUID=1000 \
    PGID=1000 \
    TZ=UTC \
    ARRMADA_PORT=3420 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3420
VOLUME ["/app/data"]

# Passe par la passerelle : valide à la fois le proxy ET l'API.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python", "/usr/local/bin/arrmada-healthcheck"]

# PID 1 : entrypoint.sh relaie SIGTERM aux 3 processus (trap) et attend
# leur fin. `init: true` dans le compose ajoute en plus le mini-init de
# Docker (tini) qui ramasse les processus zombies.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

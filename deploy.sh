#!/usr/bin/env bash
# ╔════════════════════════════════════════════════════════════╗
# ║         ArrMada — déploiement manuel (image unique)          ║
# ╚════════════════════════════════════════════════════════════╝
#
# Usage :
#   ./deploy.sh              # récupère l'image publiée (GHCR) et redémarre
#   ./deploy.sh --build      # construit l'image depuis les sources locales
#   ./deploy.sh --build --full   # idem, sans cache Docker
#   ./deploy.sh --logs       # déploie puis suit les logs
#
# Le compose utilisé est docker-compose.yml + docker-compose.override.yml
# s'il existe (fusion automatique par Docker Compose) : c'est là que se
# mettent les réglages propres à l'hôte (PostgreSQL, montages, PUID…).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

IMAGE="ghcr.io/tcastel94/arrmada:latest"
PORT="${ARRMADA_PORT:-3420}"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[ArrMada]${NC} $1"; }
ok()   { echo -e "${GREEN}  ✅ $1${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️  $1${NC}"; }
err()  { echo -e "${RED}  ❌ $1${NC}"; }

# ── Arguments ────────────────────────────────────────────────
BUILD=false
NO_CACHE=""
TAIL_LOGS=false

for arg in "$@"; do
    case $arg in
        --build)     BUILD=true ;;
        --full)      NO_CACHE="--no-cache" ;;
        --logs)      TAIL_LOGS=true ;;
        --help|-h)
            sed -n '5,13p' "$0"
            exit 0
            ;;
        *)
            err "Option inconnue : $arg (voir --help)"
            exit 64
            ;;
    esac
done

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       🏴‍☠️  ArrMada Deploy — $(date '+%H:%M:%S')       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# ── Git ──────────────────────────────────────────────────────
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse --short HEAD)
    DIRTY=$(git status --porcelain | wc -l)
    log "Branche : ${CYAN}$BRANCH${NC} @ ${CYAN}$COMMIT${NC}"
    if [ "$DIRTY" -gt 0 ]; then
        warn "$DIRTY modification(s) non commitée(s)"
    fi
fi

# ── Prérequis ────────────────────────────────────────────────
log "Vérification des prérequis…"
command -v docker > /dev/null 2>&1 || { err "Docker introuvable"; exit 1; }
docker compose version > /dev/null 2>&1 || { err "Docker Compose v2 introuvable (docker compose …)"; exit 1; }
[ -f docker-compose.yml ] || { err "docker-compose.yml introuvable"; exit 1; }
ok "Docker et Compose disponibles"

if [ -f docker-compose.override.yml ]; then
    ok "docker-compose.override.yml détecté (réglages propres à l'hôte)"
else
    warn "Pas de docker-compose.override.yml : configuration par défaut (SQLite dans ./data)"
fi
echo ""

# ── Image ────────────────────────────────────────────────────
STARTED=$(date +%s)
if $BUILD; then
    log "Construction de l'image depuis les sources… ${NO_CACHE:+(sans cache)}"
    docker build $NO_CACHE -t "$IMAGE" .
    ok "Image construite en $(($(date +%s) - STARTED)) s"
else
    log "Récupération de l'image publiée…"
    docker compose pull
    ok "Image à jour"
fi

# ── Démarrage ────────────────────────────────────────────────
log "Démarrage…"
docker compose up -d --remove-orphans
ok "Conteneur démarré"

# ── Santé ────────────────────────────────────────────────────
log "Attente du contrôle de santé (90 s max)…"
HEALTHY=false
for _ in $(seq 1 30); do
    if curl -sf "http://localhost:${PORT}/api/health" > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 3
done

if $HEALTHY; then
    ok "ArrMada répond !"
else
    err "Pas de réponse sur :${PORT} — derniers logs :"
    docker logs arrmada --tail 30 2>&1
fi

# ── Nettoyage ────────────────────────────────────────────────
docker image prune -f > /dev/null 2>&1 || true

echo ""
docker compose ps
echo ""
log "Durée totale : $(($(date +%s) - STARTED)) s"
log "Interface : http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PORT}"
echo ""

if $TAIL_LOGS; then
    log "Logs en continu (Ctrl+C pour quitter)…"
    docker compose logs -f --tail 50
fi

$HEALTHY

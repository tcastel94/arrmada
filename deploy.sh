#!/usr/bin/env bash
# ╔════════════════════════════════════════════════════════════╗
# ║         ArrMada — Quick Deploy Script (Unraid)             ║
# ╚════════════════════════════════════════════════════════════╝
#
# Usage:
#   ./deploy.sh              # Standard deploy (rebuild + restart)
#   ./deploy.sh --full       # Full rebuild (no Docker cache)
#   ./deploy.sh --backend    # Backend only
#   ./deploy.sh --frontend   # Frontend only
#   ./deploy.sh --logs       # Deploy then tail logs
#
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Colors
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

# ── Parse args ────────────────────────────────────────────────
MODE="all"
NO_CACHE=""
TAIL_LOGS=false

for arg in "$@"; do
    case $arg in
        --full)      NO_CACHE="--no-cache" ;;
        --backend)   MODE="backend" ;;
        --frontend)  MODE="frontend" ;;
        --logs)      TAIL_LOGS=true ;;
        --help|-h)
            echo "Usage: ./deploy.sh [--full|--backend|--frontend|--logs]"
            exit 0
            ;;
    esac
done

# ── Header ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       🏴‍☠️  ArrMada Deploy — $(date '+%H:%M:%S')       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo ""

# ── Git status ────────────────────────────────────────────────
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse --short HEAD)
    DIRTY=$(git status --porcelain | wc -l)
    log "Branch: ${CYAN}$BRANCH${NC} @ ${CYAN}$COMMIT${NC}"
    if [ "$DIRTY" -gt 0 ]; then
        warn "$DIRTY uncommitted changes"
    fi
fi

# ── Pre-deploy checks ────────────────────────────────────────
log "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    err "Docker not found!"
    exit 1
fi
ok "Docker available"

if ! command -v docker compose &> /dev/null 2>&1; then
    # Fallback to docker-compose
    if ! command -v docker-compose &> /dev/null; then
        err "Docker Compose not found!"
        exit 1
    fi
fi
ok "Docker Compose available"

if [ ! -f "$COMPOSE_FILE" ]; then
    err "$COMPOSE_FILE not found!"
    exit 1
fi
ok "docker-compose.yml found"

if [ ! -f ".env" ]; then
    warn ".env file not found — using defaults"
else
    ok ".env loaded"
fi

echo ""

# ── Save current state (for rollback) ────────────────────────
log "Saving current container IDs for rollback..."
BACKEND_OLD=$(docker inspect --format='{{.Image}}' arrmada-backend 2>/dev/null || echo "none")
FRONTEND_OLD=$(docker inspect --format='{{.Image}}' arrmada-frontend 2>/dev/null || echo "none")

# ── Build ─────────────────────────────────────────────────────
STARTED=$(date +%s)

case $MODE in
    all)
        log "Building all services... ${NO_CACHE:+(no cache)}"
        docker compose build $NO_CACHE
        ;;
    backend)
        log "Building backend only... ${NO_CACHE:+(no cache)}"
        docker compose build $NO_CACHE arrmada-backend
        ;;
    frontend)
        log "Building frontend only... ${NO_CACHE:+(no cache)}"
        docker compose build $NO_CACHE arrmada-frontend
        ;;
esac

BUILD_TIME=$(($(date +%s) - STARTED))
ok "Build completed in ${BUILD_TIME}s"

# ── Deploy ────────────────────────────────────────────────────
log "Deploying..."

case $MODE in
    all)
        docker compose up -d --remove-orphans
        ;;
    backend)
        docker compose up -d --no-deps arrmada-backend
        ;;
    frontend)
        docker compose up -d --no-deps arrmada-frontend
        ;;
esac

ok "Containers started"

# ── Health check ──────────────────────────────────────────────
log "Waiting for health check (15s)..."
sleep 15

BACKEND_HEALTHY=false
for i in $(seq 1 5); do
    if curl -sf http://localhost:8420/api/health > /dev/null 2>&1; then
        BACKEND_HEALTHY=true
        break
    fi
    sleep 3
done

if $BACKEND_HEALTHY; then
    ok "Backend is healthy!"
else
    warn "Backend health check failed — checking logs..."
    docker logs arrmada-backend --tail 20 2>&1 | tail -10
fi

# ── Cleanup ───────────────────────────────────────────────────
log "Cleaning up dangling images..."
docker image prune -f > /dev/null 2>&1
ok "Cleanup done"

# ── Summary ───────────────────────────────────────────────────
TOTAL_TIME=$(($(date +%s) - STARTED))
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          Deploy complete! 🎉               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
log "Total time: ${TOTAL_TIME}s"
echo ""

docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps

echo ""
log "Backend:  http://$(hostname -I | awk '{print $1}'):8420"
log "Frontend: http://$(hostname -I | awk '{print $1}'):3420"
echo ""

# ── Tail logs if requested ────────────────────────────────────
if $TAIL_LOGS; then
    log "Tailing logs (Ctrl+C to stop)..."
    docker compose logs -f --tail 50
fi

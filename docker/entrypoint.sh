#!/usr/bin/env bash
# ╔════════════════════════════════════════════════════════════╗
# ║         ArrMada — démarrage du conteneur (image unique)      ║
# ╚════════════════════════════════════════════════════════════╝
#
# Lance et surveille 3 processus :
#   1. uvicorn  (API FastAPI)     127.0.0.1:${ARRMADA_API_PORT:-8420}
#   2. node     (Next.js)         127.0.0.1:${ARRMADA_WEB_PORT:-3421}
#   3. node     (gateway.js)      0.0.0.0:${ARRMADA_PORT:-3420}  ← seul port public
#
# Si UN processus meurt, on arrête les deux autres et on sort avec son
# code retour : la politique `restart: unless-stopped` de Docker relance
# alors le conteneur proprement (plutôt qu'une appli à moitié vivante).
#
# Droits : démarré en root, le script donne le dossier data à PUID:PGID
# puis exécute tout sous cet utilisateur (convention linuxserver.io,
# attendue sur Synology / Unraid / TrueNAS). PUID=0 garde root.
set -euo pipefail

log() { printf '%s [entrypoint] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
DATA_DIR="${DATA_DIR:-/app/data}"
export ARRMADA_API_PORT="${ARRMADA_API_PORT:-8420}"
export ARRMADA_WEB_PORT="${ARRMADA_WEB_PORT:-3421}"
export ARRMADA_PORT="${ARRMADA_PORT:-3420}"
# Pas de $HOME exploitable pour un UID arbitraire : /tmp suffit.
export HOME=/tmp

for v in PUID PGID; do
    if ! [[ "${!v}" =~ ^[0-9]+$ ]]; then
        log "ERREUR : $v doit être un nombre (reçu : '${!v}')"
        exit 64
    fi
done

mkdir -p "$DATA_DIR"
RUN_AS=()
if [ "$(id -u)" = "0" ]; then
    # Volume monté depuis l'hôte : il garde le propriétaire de l'hôte
    # (souvent root). On le rend à l'utilisateur applicatif.
    chown -R "$PUID:$PGID" "$DATA_DIR"
    RUN_AS=(setpriv --reuid="$PUID" --regid="$PGID" --clear-groups --)
    log "Utilisateur applicatif : UID=$PUID GID=$PGID"
else
    log "Conteneur lancé sans root (UID=$(id -u)) : PUID/PGID ignorés"
fi

declare -A NAMES=()
PIDS=()

start() {
    local name="$1"
    shift
    "$@" &
    PIDS+=("$!")
    NAMES[$!]="$name"
    log "Démarré : $name (pid $!)"
}

cd /app
start "api" "${RUN_AS[@]}" uvicorn app.main:app \
    --host 127.0.0.1 --port "$ARRMADA_API_PORT" \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}" \
    --no-server-header \
    --log-level "$(printf '%s' "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')"

start "web" env HOSTNAME=127.0.0.1 PORT="$ARRMADA_WEB_PORT" \
    "${RUN_AS[@]}" node /app/web/server.js

start "gateway" "${RUN_AS[@]}" node /app/docker/gateway.js

stop_all() {
    trap - TERM INT
    log "Arrêt des processus…"
    kill -TERM "${PIDS[@]}" 2>/dev/null || true
}
trap stop_all TERM INT

# Attend le PREMIER processus qui se termine (ou un signal d'arrêt).
set +e
wait -n -p DEAD "${PIDS[@]}"
STATUS=$?
set -e

if [ -n "${DEAD:-}" ]; then
    log "Le processus « ${NAMES[$DEAD]} » s'est arrêté (code $STATUS) : arrêt du conteneur"
fi
stop_all
wait
exit "$STATUS"

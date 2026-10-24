#!/bin/bash
#===============================================================================
# @name        : bascule_arrmada.sh
# @description : Bascule l'ArrMada de l'Unraid de l'ancienne stack (3 conteneurs :
#                arrmada-backend + arrmada-frontend + arrmada-db) vers l'image
#                unique (arrmada + arrmada-db), SANS perte de données, avec
#                retour arrière automatique si un contrôle échoue.
# @author      : ArrMada (généré avec Claude Code)
# @version     : 1.0.0
# @date        : 2026-10-24
# @usage       : ./bascule_arrmada.sh [--dry-run] [--yes] [--rollback] [options]
#
# Déroulé (la coupure ne commence qu'à l'étape 5 et dure ~30 s) :
#   1. Contrôles     : Docker, git propre, ancienne stack en marche, base,
#                      secrets, montages, maj-arrmada.sh, place disque
#   2. Plan          : résumé, confirmation
#   3. Préparation   : image récupérée sur GHCR (sinon construite), override
#                      GÉNÉRÉ à partir de l'ancien conteneur, puis validé
#   4. Sauvegarde    : pg_dump + archive data/ + .env + compose
#   5. Bascule       : down de l'ancienne stack, git pull, override, up
#   6. Vérification  : santé 3420 et 8420, même base, même mot de passe,
#                      même nombre de services qu'avant
#   7. En cas d'échec : retour arrière automatique vers l'ancienne stack
#
# Codes retour : 0 OK · 1 erreur · 2 configuration · 3 dépendance manquante ·
#                4 paramètres · 5 contrôle préalable bloquant ·
#                6 échec de la bascule, ancienne stack RESTAURÉE ·
#                7 échec ET retour arrière en échec (intervention manuelle)
#===============================================================================
#
# Pas de common.sh ici : le script tourne sur le NAS, qui ne l'a pas. Les
# fonctions de log sont donc embarquées.

set -euo pipefail

#-------------------------------------------------------------------------------
# Constantes et valeurs par défaut
#-------------------------------------------------------------------------------
readonly SCRIPT_NAME="${0##*/}"
readonly VERSION="1.0.0"

readonly E_OK=0
readonly E_ERROR=1
readonly E_CONFIG=2
readonly E_DEPS=3
readonly E_PARAMS=4
readonly E_PREFLIGHT=5
readonly E_ROLLED_BACK=6
readonly E_ROLLBACK_FAILED=7

APP_DIR="/mnt/user/appdata/arrmada"
BACKUP_ROOT="/mnt/user/appdata/arrmada-backups"
IMAGE="ghcr.io/tcastel94/arrmada:latest"
PUID_VALUE="99"          # nobody (convention Unraid, comme linuxserver.io)
PGID_VALUE="100"         # users
HEALTH_TIMEOUT=180       # secondes d'attente du nouveau conteneur
OLD_HEALTH_TIMEOUT=120   # secondes d'attente de l'ancienne stack (retour arrière)

OPT_DRY_RUN=false
OPT_YES=false
OPT_ROLLBACK=false
OPT_NO_PULL=false
OPT_SKIP_DATA_BACKUP=false
OPT_CHECK_PERMS=true

# Renseignées pendant les contrôles
OLD_PROJECT=""           # projet compose de l'ancienne stack (label du conteneur)
OLD_COMMIT=""            # commit git avant bascule (retour arrière)
PG_MODE=""               # integrated | external | sqlite
PG_VOLUME=""             # nom réel du volume PostgreSQL
OLD_SERVICES=""          # nombre de services vus par l'ancienne API
OLD_PASSWORD_SET=""      # mot de passe défini avant ?
OLD_DB_TYPE=""           # postgresql | sqlite
EXTRA_MOUNTS=()          # montages de l'ancien backend à reprendre
IMAGE_SOURCE=""          # ghcr | local-existing | local-build
EUFY_RUNNING=false       # pont caméras Eufy à relancer après la bascule
BACKUP_DIR=""
LOG_FILE=""
STATE_FILE=""
PRE_LOG=""
TMP_DIR=""
WARNINGS=()

#-------------------------------------------------------------------------------
# Affichage et journal
#-------------------------------------------------------------------------------
if [ -t 1 ]; then
    C_RED=$'\033[0;31m'; C_GREEN=$'\033[0;32m'; C_YELLOW=$'\033[1;33m'
    C_BLUE=$'\033[0;34m'; C_BOLD=$'\033[1m'; C_RESET=$'\033[0m'
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""; C_RESET=""
fi

_ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() {
    local level="$1"; shift
    local color=""
    case "$level" in
        INFO)  color="$C_BLUE" ;;
        OK)    color="$C_GREEN" ;;
        WARN)  color="$C_YELLOW" ;;
        ERROR) color="$C_RED" ;;
    esac
    printf '%s %s%-5s%s %s\n' "$(_ts)" "$color" "$level" "$C_RESET" "$*"
}
info() { log INFO "$@"; }
ok()   { log OK "$@"; }
warn() { log WARN "$@"; WARNINGS+=("$*"); }
err()  { log ERROR "$@"; }

die() {
    local code="${2:-$E_ERROR}"
    err "$1"
    exit "$code"
}

step() { printf '\n%s━━ %s ━━%s\n' "$C_BOLD" "$*" "$C_RESET"; }

usage() {
    cat <<EOF
${SCRIPT_NAME} ${VERSION} — bascule ArrMada vers l'image unique (Unraid)

Usage : ${SCRIPT_NAME} [options]

  --dry-run             contrôles + override généré affiché, AUCUN changement
  -y, --yes             pas de confirmation
  --rollback            revenir à l'ancienne stack après une bascule réussie
                        (utilise le dernier dossier de sauvegarde)
  --dir DIR             dossier d'ArrMada         (défaut : ${APP_DIR})
  --backup-root DIR     dossier des sauvegardes   (défaut : ${BACKUP_ROOT})
  --puid N / --pgid N   propriétaire des fichiers (défaut : ${PUID_VALUE}/${PGID_VALUE})
  --no-pull             ne pas télécharger l'image : utiliser celle déjà
                        présente localement, sinon la construire
  --skip-data-backup    ne pas archiver data/ (la base est toujours exportée)
  --no-perms-check      ne pas chercher les fichiers root dans /mnt/user
  -h, --help            cette aide

Codes retour : 0 OK · 2 config · 3 dépendance · 4 paramètres · 5 contrôle
bloquant · 6 échec mais ancienne stack restaurée · 7 échec du retour arrière
EOF
}

#-------------------------------------------------------------------------------
# Paramètres
#-------------------------------------------------------------------------------
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --dry-run)          OPT_DRY_RUN=true ;;
            -y|--yes)           OPT_YES=true ;;
            --rollback)         OPT_ROLLBACK=true ;;
            --dir)              APP_DIR="${2:?--dir attend un chemin}"; shift ;;
            --backup-root)      BACKUP_ROOT="${2:?--backup-root attend un chemin}"; shift ;;
            --puid)             PUID_VALUE="${2:?--puid attend un nombre}"; shift ;;
            --pgid)             PGID_VALUE="${2:?--pgid attend un nombre}"; shift ;;
            --no-pull)          OPT_NO_PULL=true ;;
            --skip-data-backup) OPT_SKIP_DATA_BACKUP=true ;;
            --no-perms-check)   OPT_CHECK_PERMS=false ;;
            -h|--help)          usage; exit "$E_OK" ;;
            *)                  usage >&2; die "Option inconnue : $1" "$E_PARAMS" ;;
        esac
        shift
    done
    [[ "$PUID_VALUE" =~ ^[0-9]+$ ]] || die "--puid doit être un nombre" "$E_PARAMS"
    [[ "$PGID_VALUE" =~ ^[0-9]+$ ]] || die "--pgid doit être un nombre" "$E_PARAMS"
    APP_DIR="${APP_DIR%/}"
    BACKUP_ROOT="${BACKUP_ROOT%/}"
}

#-------------------------------------------------------------------------------
# Outils
#-------------------------------------------------------------------------------
check_deps() {
    local missing=() cmd
    for cmd in docker git curl gzip tar sed awk grep sha256sum timeout; do
        command -v "$cmd" > /dev/null 2>&1 || missing+=("$cmd")
    done
    [ ${#missing[@]} -eq 0 ] || die "Commande(s) introuvable(s) : ${missing[*]}" "$E_DEPS"
    docker info > /dev/null 2>&1 || die "Docker ne répond pas (lancer en root, Docker démarré ?)" "$E_DEPS"
    docker compose version > /dev/null 2>&1 || die "Docker Compose v2 introuvable (« docker compose »)" "$E_DEPS"
}

# Empreinte courte : compare des secrets sans jamais les afficher.
fingerprint() { printf '%s' "$1" | sha256sum | cut -c1-12; }

# Valeur d'une variable d'environnement d'un conteneur (vide si absente).
container_env() {
    local container="$1" name="$2"
    docker inspect "$container" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | sed -n "s/^${name}=//p" | head -n 1
}

# Valeur d'une variable telle que Compose la résout pour le service arrmada
# (sortie YAML de « docker compose config », guillemets retirés).
resolved_env() {
    local config_file="$1" name="$2"
    sed -n "s/^ *${name}: *//p" "$config_file" | head -n 1 \
        | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/" -e 's/\$\$/$/g'
    # (« config » double les $ des valeurs : on les remet à l'unité)
}

# Champ entier ou booléen d'une réponse JSON simple (sans jq, absent d'Unraid).
json_field() {
    local json="$1" field="$2"
    printf '%s' "$json" | grep -o "\"${field}\":[^,}]*" | head -n 1 | cut -d: -f2- | tr -d ' "'
}

http_get() { curl -fsS --max-time 5 "$1" 2>/dev/null; }

# IP de la machine sur le réseau local (hostname -I n'existe pas sur Unraid).
lan_ip() {
    local ip_addr
    ip_addr="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
    printf '%s' "${ip_addr:-<ip-du-NAS>}"
}

# Attend que l'URL réponde, au plus N secondes.
wait_http() {
    local url="$1" timeout="$2" waited=0
    while [ "$waited" -lt "$timeout" ]; do
        http_get "$url" > /dev/null && return 0
        sleep 3
        waited=$((waited + 3))
    done
    return 1
}

confirm() {
    $OPT_YES && return 0
    local answer
    read -r -p "$1 [o/N] " answer < /dev/tty || return 1
    [[ "$answer" =~ ^[oOyY]$ ]]
}

# Appelée par le trap EXIT : shellcheck la croit inaccessible (SC2317 avant
# la 0.10, SC2329 depuis).
# shellcheck disable=SC2317,SC2329
cleanup() {
    [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ] && rm -rf "$TMP_DIR"
    return 0
}
trap cleanup EXIT

# État de la bascule, relu par --rollback (aucun secret dedans).
save_state() {
    {
        printf 'OLD_COMMIT=%q\n' "$OLD_COMMIT"
        printf 'OLD_PROJECT=%q\n' "$OLD_PROJECT"
        printf 'APP_DIR=%q\n' "$APP_DIR"
        printf 'IMAGE_SOURCE=%q\n' "$IMAGE_SOURCE"
        printf 'EUFY_RUNNING=%q\n' "$EUFY_RUNNING"
        printf 'DATE=%q\n' "$(_ts)"
    } > "$STATE_FILE"
}

#-------------------------------------------------------------------------------
# 1. Contrôles préalables (rien n'est modifié)
#-------------------------------------------------------------------------------
preflight() {
    step "1/6 Contrôles préalables"
    local blocking=0

    check_deps
    ok "Docker $(docker version --format '{{.Server.Version}}'), Compose $(docker compose version --short)"
    [ -f /etc/unraid-version ] && ok "Unraid $(sed -n 's/^version="\(.*\)"/\1/p' /etc/unraid-version)"

    # ── Dépôt git ──────────────────────────────────────────────
    [ -d "$APP_DIR/.git" ] || die "$APP_DIR n'est pas un clone git d'ArrMada (--dir ?)" "$E_CONFIG"
    cd "$APP_DIR"
    OLD_COMMIT="$(git rev-parse HEAD)"
    local branch dirty
    branch="$(git rev-parse --abbrev-ref HEAD)"
    if [ "$branch" != "main" ]; then
        err "Branche actuelle « $branch » : la bascule se fait depuis main"
        blocking=1
    fi
    dirty="$(git status --porcelain --untracked-files=no)"
    if [ -n "$dirty" ]; then
        err "Fichiers suivis modifiés localement (le git pull échouerait ou les écraserait) :"
        printf '        %s\n' "$dirty"
        err "→ les mettre de côté : git stash   (ou les commiter), puis relancer"
        blocking=1
    fi
    info "Récupération de origin/main…"
    git fetch --quiet origin main || die "git fetch origin main impossible (réseau ?)" "$E_ERROR"
    if ! git cat-file -e origin/main:Dockerfile 2>/dev/null; then
        err "origin/main ne contient pas encore l'image unique (Dockerfile racine absent)"
        blocking=1
    fi
    # Un git pull (maj-arrmada.sh…) a déjà amené l'image unique alors que
    # l'ancienne stack tourne : le retour arrière doit viser le dernier
    # commit SANS Dockerfile racine (celui des 3 conteneurs), pas HEAD.
    if git cat-file -e HEAD:Dockerfile 2>/dev/null; then
        local c
        OLD_COMMIT=""
        while IFS= read -r c; do
            if ! git cat-file -e "$c:Dockerfile" 2>/dev/null; then
                OLD_COMMIT="$c"
                break
            fi
        done < <(git rev-list --first-parent HEAD)
        if [ -z "$OLD_COMMIT" ]; then
            err "Impossible de retrouver le commit de l'ancienne stack dans l'historique"
            blocking=1
        else
            warn "Le code est déjà à jour (git pull fait) : retour arrière éventuel vers $(git rev-parse --short "$OLD_COMMIT")"
        fi
    fi
    if ! git merge-base --is-ancestor HEAD origin/main; then
        err "La branche locale a des commits absents de origin/main : avance rapide impossible"
        blocking=1
    fi
    ok "Git : main @ $(git rev-parse --short HEAD) → origin/main @ $(git rev-parse --short origin/main)"

    # ── Ancienne stack ─────────────────────────────────────────
    if ! docker container inspect arrmada-backend > /dev/null 2>&1; then
        if docker container inspect arrmada > /dev/null 2>&1; then
            ok "Conteneur « arrmada » déjà présent et plus d'arrmada-backend : bascule déjà faite"
            exit "$E_OK"
        fi
        die "Conteneur arrmada-backend introuvable : rien à basculer" "$E_PREFLIGHT"
    fi
    if [ "$(docker inspect -f '{{.State.Running}}' arrmada-backend)" != "true" ]; then
        err "arrmada-backend est arrêté : le démarrer d'abord (docker compose up -d) pour relever sa config"
        blocking=1
    fi
    OLD_PROJECT="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' arrmada-backend)"
    [ -n "$OLD_PROJECT" ] || OLD_PROJECT="arrmada"
    if [ "$OLD_PROJECT" != "arrmada" ]; then
        warn "Projet compose actuel « $OLD_PROJECT » (le nouveau s'appelle « arrmada »)"
    fi
    ok "Ancienne stack : projet « $OLD_PROJECT »"

    # ── Dossier data ───────────────────────────────────────────
    local data_src
    data_src="$(docker inspect arrmada-backend --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}}{{end}}{{end}}')"
    # Sur Unraid, le même dossier peut apparaître en /mnt/user/… ou en
    # /mnt/cache/… : on compare alors la clé de chiffrement des deux côtés.
    if [ "$data_src" = "$APP_DIR/data" ]; then
        ok "Données : $data_src ($(du -sh "$data_src" 2>/dev/null | cut -f1))"
    elif [ -n "$data_src" ] && [ -f "$data_src/.fernet_key" ] && [ -f "$APP_DIR/data/.fernet_key" ] \
        && [ "$(sha256sum < "$data_src/.fernet_key")" = "$(sha256sum < "$APP_DIR/data/.fernet_key")" ]; then
        ok "Données : $APP_DIR/data (= $data_src, même clé de chiffrement)"
    else
        err "Le dossier data de l'ancien backend est « ${data_src:-aucun} », pas « $APP_DIR/data »"
        blocking=1
    fi

    # ── Base de données ────────────────────────────────────────
    local db_url
    db_url="$(container_env arrmada-backend DATABASE_URL)"
    case "$db_url" in
        postgresql*@arrmada-db:*|postgresql*@arrmada-db/*)
            PG_MODE="integrated"
            if ! docker container inspect arrmada-db > /dev/null 2>&1; then
                err "DATABASE_URL vise arrmada-db mais ce conteneur n'existe pas"
                blocking=1
            else
                PG_VOLUME="$(docker inspect arrmada-db --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')"
                if [ -z "$PG_VOLUME" ]; then
                    err "Volume PostgreSQL de arrmada-db introuvable (montage en dossier ?)"
                    blocking=1
                else
                    ok "Base : PostgreSQL intégré, volume « $PG_VOLUME »"
                fi
            fi
            ;;
        postgresql*)
            PG_MODE="external"
            ok "Base : PostgreSQL externe (hôte $(printf '%s' "$db_url" | sed 's|.*@\([^:/]*\).*|\1|'))"
            ;;
        sqlite*)
            PG_MODE="sqlite"
            ok "Base : SQLite ($db_url)"
            ;;
        *)
            err "DATABASE_URL de l'ancien backend non reconnue"
            blocking=1
            ;;
    esac

    # ── État vu par l'ancienne API (comparé après bascule) ─────
    local status
    status="$(http_get http://127.0.0.1:8420/api/setup/status || true)"
    if [ -z "$status" ]; then
        err "L'ancienne API ne répond pas sur 127.0.0.1:8420"
        blocking=1
    else
        OLD_SERVICES="$(json_field "$status" services_count)"
        OLD_DB_TYPE="$(json_field "$status" database_type)"
        ok "Ancienne API : ${OLD_SERVICES:-?} service(s), base ${OLD_DB_TYPE:-?}"
    fi

    # ── Secrets (comparés par empreinte, jamais affichés) ──────
    local old_secret old_jwt env_secret
    old_secret="$(container_env arrmada-backend ARRMADA_AUTH_SECRET)"
    old_jwt="$(container_env arrmada-backend JWT_SECRET_KEY)"
    env_secret="$(sed -n 's/^ARRMADA_AUTH_SECRET=//p' "$APP_DIR/.env" 2>/dev/null | head -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
    case "$old_secret" in
        ""|changeme|changeme_use_a_strong_password)
            OLD_PASSWORD_SET="false"
            warn "Mot de passe actuel = valeur par défaut : la nouvelle version la REFUSE."
            warn "→ ArrMada demandera d'en créer un au premier accès : le faire tout de suite après la bascule,"
            warn "  puis mettre ce mot de passe dans le réglage « Clé API » des TV non appairées."
            ;;
        *)
            OLD_PASSWORD_SET="true"
            if [ "$env_secret" = "$old_secret" ]; then
                ok "Mot de passe : repris de .env (empreinte $(fingerprint "$old_secret"))"
            else
                err "Le mot de passe du conteneur ne correspond pas à ARRMADA_AUTH_SECRET du .env"
                err "→ corriger le .env pour qu'il contienne le mot de passe utilisé aujourd'hui"
                blocking=1
            fi
            ;;
    esac
    [ -n "$old_jwt" ] && ok "JWT_SECRET_KEY dédié présent (empreinte $(fingerprint "$old_jwt"))"

    # ── Montages de l'ancien backend à reprendre ───────────────
    local type src dst rw
    while IFS='|' read -r type src dst rw; do
        [ -z "$dst" ] && continue
        case "$dst" in
            /app/data|/app/app|/app/kodi-addon) continue ;;   # gérés à part
        esac
        if [ "$type" != "bind" ]; then
            warn "Montage « $dst » de type $type non repris (à ajouter à la main si besoin)"
            continue
        fi
        EXTRA_MOUNTS+=("${src}:${dst}:$([ "$rw" = "true" ] && echo rw || echo ro)")
    done < <(docker inspect arrmada-backend --format '{{range .Mounts}}{{.Type}}|{{.Source}}|{{.Destination}}|{{.RW}}{{"\n"}}{{end}}')
    if [ ${#EXTRA_MOUNTS[@]} -gt 0 ]; then
        ok "Montages repris : ${EXTRA_MOUNTS[*]}"
    fi

    # ── Autres conteneurs sur le réseau arrmada-network ────────
    local others
    others="$(docker network inspect arrmada-network --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null \
        | tr ' ' '\n' | grep -v -E '^(arrmada-backend|arrmada-frontend|arrmada-db|)$' || true)"
    if [ -n "$others" ]; then
        warn "Autres conteneurs rattachés au réseau arrmada-network : $(echo "$others" | tr '\n' ' ')(ils y restent)"
    fi
    # « docker compose down » arrête AUSSI les services à profil (eufy) :
    # on note s'il tournait pour le relancer après la bascule.
    if [ "$(docker inspect -f '{{.State.Running}}' eufy-security-ws 2>/dev/null)" = "true" ]; then
        EUFY_RUNNING=true
        ok "eufy-security-ws en marche : relancé après la bascule (mêmes données data/eufy)"
    fi

    # ── Scripts qui appellent deploy.sh (maj-arrmada.sh, User Scripts) ──
    local f
    while IFS= read -r f; do
        [ -f "$f" ] || continue
        if grep -q -E 'deploy\.sh[^#]*--(backend|frontend)' "$f"; then
            warn "« $f » appelle deploy.sh avec --backend/--frontend : options supprimées, il faudra les retirer"
        else
            ok "Script de mise à jour compatible : $f"
        fi
    done < <(grep -rl -E 'deploy\.sh|maj-arrmada' \
        "$APP_DIR"/maj-arrmada.sh "$APP_DIR"/../maj-arrmada.sh /root/maj-arrmada.sh \
        /boot/config/plugins/user.scripts/scripts 2>/dev/null || true)

    # ── Place disque ───────────────────────────────────────────
    local docker_root free_kb
    docker_root="$(docker info --format '{{.DockerRootDir}}')"
    free_kb="$(df -Pk "$docker_root" | awk 'NR==2 {print $4}')"
    if [ "${free_kb:-0}" -lt 3145728 ]; then
        err "Moins de 3 Go libres pour Docker ($docker_root) : l'image fait ~1,5 Go"
        blocking=1
    else
        ok "Place Docker : $((free_kb / 1048576)) Go libres"
    fi
    mkdir -p "$BACKUP_ROOT" 2>/dev/null || true
    free_kb="$(df -Pk "$BACKUP_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
    ok "Place sauvegardes ($BACKUP_ROOT) : $(( ${free_kb:-0} / 1048576 )) Go libres"

    # ── Fichiers créés par root dans les médias ────────────────
    if $OPT_CHECK_PERMS && [ -d /mnt/user ]; then
        info "Recherche de fichiers appartenant à root dans /mnt/user (60 s max)…"
        local roots
        # Seulement ce qu'ArrMada modifie : vidéos (import, nettoyage),
        # images et .nfo (artworks), sous-titres. Les autres fichiers root
        # (sauvegardes Immich, APK copiées à la main…) ne le gênent pas.
        roots="$(timeout 60 find /mnt/user -maxdepth 6 \
            \( -path /mnt/user/appdata -o -path /mnt/user/system -o -path /mnt/user/domains -o -path /mnt/user/isos \) -prune \
            -o -user root -type f \( -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.avi' -o -iname '*.m4v' \
                -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.nfo' \
                -o -iname '*.srt' -o -iname '*.ass' -o -iname '*.sub' \) -print 2>/dev/null | head -n 20 || true)"
        if [ -n "$roots" ]; then
            warn "Fichiers appartenant à root dans les médias (ArrMada, désormais en ${PUID_VALUE}:${PGID_VALUE}, ne pourra plus les modifier) :"
            printf '        %s\n' "$roots"
            WARNINGS+=("$(printf '   %s\n' "$roots")")
            warn "→ Tools › New Permissions sur le partage concerné, ou : chown -R nobody:users <dossier>"
        else
            ok "Aucun fichier média, artwork ou sous-titre appartenant à root (6 niveaux)"
        fi
    fi

    [ "$blocking" -eq 0 ] || die "Contrôle(s) bloquant(s) : rien n'a été modifié" "$E_PREFLIGHT"
    ok "Contrôles terminés"
}

#-------------------------------------------------------------------------------
# Override généré à partir de l'ancien conteneur
#-------------------------------------------------------------------------------
generate_override() {
    local out="$1" mount
    {
        cat <<EOF
# ╔════════════════════════════════════════════════════════════╗
# ║   ArrMada — réglages propres à cet hôte (NON versionné)       ║
# ╚════════════════════════════════════════════════════════════╝
# Généré par ${SCRIPT_NAME} le $(_ts) à partir de l'ancien
# conteneur arrmada-backend. Fusionné automatiquement avec
# docker-compose.yml par Docker Compose. Voir docs/deploy-unraid.md.
# Aucun secret ici : les valeurs viennent du fichier .env.

services:
  arrmada:
EOF
        if [ "$IMAGE_SOURCE" = "local-build" ]; then
            cat <<'EOF'
    # Image construite sur place (GHCR indisponible lors de la bascule).
    # Dès que « docker pull ghcr.io/tcastel94/arrmada:latest » marche :
    # supprimer cette ligne, les mises à jour seront alors téléchargées.
    build: .
EOF
        fi
        cat <<'EOF'
    volumes:
EOF
        for mount in "${EXTRA_MOUNTS[@]}"; do
            printf '      - %s\n' "$mount"
        done
        cat <<EOF
      # Add-on Kodi du clone git : nouvelle version proposée aux TV dès le
      # git pull, sans attendre une nouvelle image
      - ./kodi-addon:/app/kodi-addon:ro
      # Optionnel, LECTURE SEULE : configs des autres applis, pour que
      # Paramètres › Auto-configuration vérifie et complète leur câblage
      # - /mnt/user/appdata:/appdata:ro
    environment:
      - PUID=${PUID_VALUE}
      - PGID=${PGID_VALUE}
      # Ancien mot de passe (.env) : accepté tel quel. Le redéfinir dans
      # Paramètres › Mot de passe administrateur le stocke haché.
      - ARRMADA_AUTH_SECRET=\${ARRMADA_AUTH_SECRET:-}
      # Même secret de signature que l'ancienne stack (JWT_SECRET_KEY, sinon
      # ARRMADA_AUTH_SECRET) : sessions et URL d'artworks restent valides.
      - JWT_SECRET_KEY=\${JWT_SECRET_KEY:-\${ARRMADA_AUTH_SECRET:-}}
EOF
        case "$PG_MODE" in
            integrated)
                cat <<'EOF'
      # Même base PostgreSQL que l'ancienne stack
      - DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://arrmada:${POSTGRES_PASSWORD:-arrmada}@arrmada-db:5432/arrmada}
    depends_on:
      arrmada-db:
        condition: service_healthy

  arrmada-db:
    image: postgres:16-alpine
    container_name: arrmada-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: arrmada
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-arrmada}
      POSTGRES_DB: arrmada
    volumes:
      - arrmada-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arrmada"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  # Volume EXISTANT de l'ancienne stack. « external » : Compose ne le crée
  # pas et ne le supprime jamais, même avec « down -v ».
  arrmada-pgdata:
    external: true
EOF
                printf '    name: %s\n' "$PG_VOLUME"
                ;;
            external|sqlite)
                cat <<'EOF'
      # Même base que l'ancienne stack (DATABASE_URL du .env)
      - DATABASE_URL=${DATABASE_URL}
EOF
                ;;
        esac
        cat <<'EOF'

networks:
  default:
    # Même réseau Docker que l'ancienne stack
    name: arrmada-network
EOF
    } > "$out"
}

# Valide l'override avec le docker-compose.yml de origin/main et vérifie que
# la base et les secrets résolus sont IDENTIQUES à ceux de l'ancien backend.
validate_override() {
    local override="$1" compose_new="$TMP_DIR/docker-compose.yml" resolved="$TMP_DIR/resolved.yml"
    git -C "$APP_DIR" show origin/main:docker-compose.yml > "$compose_new"
    docker compose --project-directory "$APP_DIR" -f "$compose_new" -f "$override" config > "$resolved" 2> "$TMP_DIR/config.err" \
        || { cat "$TMP_DIR/config.err"; die "Override invalide" "$E_CONFIG"; }

    local name old new
    for name in DATABASE_URL ARRMADA_AUTH_SECRET; do
        old="$(container_env arrmada-backend "$name")"
        new="$(resolved_env "$resolved" "$name")"
        if [ "$name" = "ARRMADA_AUTH_SECRET" ] && [ "$OLD_PASSWORD_SET" = "false" ]; then
            continue   # valeur par défaut refusée de toute façon (prévenu plus haut)
        fi
        if [ "$old" != "$new" ]; then
            die "$name résolue ($(fingerprint "$new")) ≠ ancien conteneur ($(fingerprint "$old")) : vérifier le .env" "$E_CONFIG"
        fi
    done
    old="$(container_env arrmada-backend JWT_SECRET_KEY)"
    [ -n "$old" ] || old="$(container_env arrmada-backend ARRMADA_AUTH_SECRET)"
    new="$(resolved_env "$resolved" JWT_SECRET_KEY)"
    if [ "$OLD_PASSWORD_SET" = "true" ] && [ "$old" != "$new" ]; then
        die "Secret de signature résolu ≠ ancien : sessions et artworks seraient invalidés" "$E_CONFIG"
    fi
    ok "Override validé : même base, même mot de passe, même secret de signature"
}

#-------------------------------------------------------------------------------
# 3. Préparation (l'ancienne stack tourne toujours)
#-------------------------------------------------------------------------------
fetch_image() {
    if ! $OPT_NO_PULL; then
        info "Téléchargement de $IMAGE…"
        if docker pull --quiet "$IMAGE" > /dev/null 2>&1; then
            IMAGE_SOURCE="ghcr"
            ok "Image téléchargée depuis GHCR"
            return 0
        fi
        warn "Téléchargement impossible (paquet GHCR privé ? réseau ?) : construction locale"
    elif docker image inspect "$IMAGE" > /dev/null 2>&1; then
        IMAGE_SOURCE="local-existing"
        ok "Image locale utilisée (--no-pull)"
        return 0
    fi

    # Construction depuis origin/main, dans un dossier temporaire : le clone
    # n'est pas touché tant que l'ancienne stack tourne.
    IMAGE_SOURCE="local-build"
    local src="$TMP_DIR/src" arch
    mkdir -p "$src"
    git -C "$APP_DIR" archive origin/main | tar -x -C "$src"
    arch="$(docker info --format '{{.Architecture}}')"
    case "$arch" in x86_64) arch=amd64 ;; aarch64) arch=arm64 ;; esac
    info "Construction de l'image (3 à 5 min, architecture $arch)…"
    if docker buildx version > /dev/null 2>&1; then
        docker buildx build --load -t "$IMAGE" "$src" \
            || die "Construction de l'image en échec : rien n'a été modifié" "$E_ERROR"
    else
        # Sans buildx (builder classique) : $BUILDPLATFORM n'existe pas et le
        # FROM --platform=$BUILDPLATFORM échoue. On le déclare dans la copie.
        warn "buildx absent : builder classique (plus lent)"
        grep -q '^ARG BUILDPLATFORM' "$src/Dockerfile" || sed -i "0,/^FROM /s//ARG BUILDPLATFORM=linux\/${arch}\nFROM /" "$src/Dockerfile"
        DOCKER_BUILDKIT=0 docker build --build-arg "BUILDPLATFORM=linux/${arch}" -t "$IMAGE" "$src" \
            || die "Construction de l'image en échec : rien n'a été modifié" "$E_ERROR"
    fi
    ok "Image construite localement"
}

#-------------------------------------------------------------------------------
# 4. Sauvegarde (l'ancienne stack tourne toujours)
#-------------------------------------------------------------------------------
backup() {
    step "4/6 Sauvegarde dans $BACKUP_DIR"
    if [ "$PG_MODE" = "integrated" ]; then
        info "Export de la base PostgreSQL…"
        docker exec arrmada-db pg_dump -U arrmada -d arrmada --no-owner | gzip > "$BACKUP_DIR/arrmada-db.sql.gz"
        gzip -t "$BACKUP_DIR/arrmada-db.sql.gz" || die "Export de la base corrompu" "$E_ERROR"
        [ "$(gzip -cd "$BACKUP_DIR/arrmada-db.sql.gz" | head -c 4096 | wc -c)" -gt 100 ] || die "Export de la base vide" "$E_ERROR"
        ok "Base exportée ($(du -h "$BACKUP_DIR/arrmada-db.sql.gz" | cut -f1))"
    else
        warn "Base $PG_MODE : pas d'export automatique, sauvegarde-la avec tes outils habituels"
    fi
    if ! $OPT_SKIP_DATA_BACKUP; then
        info "Archive du dossier data/…"
        tar -C "$APP_DIR" -czf "$BACKUP_DIR/data.tar.gz" data
        ok "data/ archivé ($(du -h "$BACKUP_DIR/data.tar.gz" | cut -f1))"
    fi
    local f
    for f in .env docker-compose.yml docker-compose.override.yml docker-compose.override.yml.next; do
        [ -f "$APP_DIR/$f" ] && cp -p "$APP_DIR/$f" "$BACKUP_DIR/$f.avant"
    done
    chmod 600 "$BACKUP_DIR"/*
    ok "Fichiers de configuration copiés (.env, compose)"
}

#-------------------------------------------------------------------------------
# 5-6. Bascule et vérification
#-------------------------------------------------------------------------------
switch_stack() {
    step "5/6 Bascule (coupure ~30 s)"
    cd "$APP_DIR"

    info "Arrêt de l'ancienne stack (volumes conservés)…"
    # Pas de « -v » : la base reste sur son volume. Le réseau peut rester si
    # un autre conteneur y est rattaché (avertissement sans gravité).
    docker compose -p "$OLD_PROJECT" down --remove-orphans || warn "down a signalé une erreur (vérification ci-dessous)"
    local c
    for c in arrmada-backend arrmada-frontend; do
        if docker container inspect "$c" > /dev/null 2>&1; then
            docker rm -f "$c" > /dev/null || return 1
        fi
    done
    ok "Ancienne stack arrêtée"

    info "Mise à jour du code (git, avance rapide)…"
    git merge --quiet --ff-only origin/main || return 1
    ok "Code : $(git rev-parse --short HEAD)"

    install -m 0644 "$BACKUP_DIR/docker-compose.override.yml" "$APP_DIR/docker-compose.override.yml" || return 1
    [ -f "$APP_DIR/docker-compose.override.yml.next" ] && rm -f "$APP_DIR/docker-compose.override.yml.next"
    docker compose config --quiet || return 1
    ok "Override en place"

    info "Démarrage de l'image unique…"
    docker compose up -d --remove-orphans || return 1
    if $EUFY_RUNNING; then
        docker compose --profile eufy up -d eufy-security-ws || warn "Relance de eufy-security-ws en échec : docker compose --profile eufy up -d eufy-security-ws"
    fi
}

verify_new() {
    step "6/6 Vérifications"
    if ! wait_http http://127.0.0.1:3420/api/health "$HEALTH_TIMEOUT"; then
        err "Pas de réponse sur :3420 après ${HEALTH_TIMEOUT} s"
        docker logs --tail 40 arrmada 2>&1 | sed 's/^/        /'
        return 1
    fi
    ok "Santé :3420"
    http_get http://127.0.0.1:8420/api/health > /dev/null || { err "Pas de réponse sur :8420 (TV Kodi, appli Android)"; return 1; }
    ok "Santé :8420 (TV, applis, webhooks)"
    http_get http://127.0.0.1:3420/kodi/repo/addons.xml > /dev/null || { err "Dépôt Kodi injoignable"; return 1; }
    ok "Dépôt Kodi"

    local status new_services new_db new_pw
    status="$(http_get http://127.0.0.1:3420/api/setup/status)"
    new_services="$(json_field "$status" services_count)"
    new_db="$(json_field "$status" database_type)"
    new_pw="$(json_field "$status" password_set)"
    if [ -n "$OLD_DB_TYPE" ] && [ "$new_db" != "$OLD_DB_TYPE" ]; then
        err "Base « $new_db » au lieu de « $OLD_DB_TYPE »"
        return 1
    fi
    if [ -n "$OLD_SERVICES" ] && [ "$new_services" != "$OLD_SERVICES" ]; then
        err "$new_services service(s) au lieu de $OLD_SERVICES : ce n'est pas la même base"
        return 1
    fi
    ok "Même base : ${new_db}, ${new_services} service(s)"
    if [ "$OLD_PASSWORD_SET" = "true" ] && [ "$new_pw" != "true" ]; then
        err "Mot de passe non reconnu par la nouvelle version"
        return 1
    fi
    [ "$OLD_PASSWORD_SET" = "true" ] && ok "Mot de passe repris"
    docker logs arrmada 2>&1 | grep -m1 'Utilisateur applicatif' | sed 's/^.*\] /        /' || true
    return 0
}

#-------------------------------------------------------------------------------
# 7. Retour arrière
#-------------------------------------------------------------------------------
rollback() {
    step "Retour arrière vers l'ancienne stack"
    cd "$APP_DIR"
    docker compose down --remove-orphans 2>/dev/null || true
    docker rm -f arrmada > /dev/null 2>&1 || true
    if [ -f docker-compose.override.yml ]; then
        mv docker-compose.override.yml docker-compose.override.yml.next
        info "Override remis de côté (docker-compose.override.yml.next)"
    fi
    if [ "$(git rev-parse HEAD)" != "$OLD_COMMIT" ]; then
        git reset --quiet --keep "$OLD_COMMIT" || { err "git reset vers $OLD_COMMIT impossible"; return 1; }
    fi
    info "Code revenu à $(git rev-parse --short HEAD)"
    # Les anciennes images sont toujours là : redémarrage sans reconstruction.
    docker compose -p "$OLD_PROJECT" up -d --remove-orphans || return 1
    if $EUFY_RUNNING; then
        docker compose -p "$OLD_PROJECT" --profile eufy up -d eufy-security-ws || true
    fi
    if wait_http http://127.0.0.1:8420/api/health "$OLD_HEALTH_TIMEOUT"; then
        ok "Ancienne stack de nouveau en ligne (:8420 et :3420)"
        return 0
    fi
    err "L'ancienne stack ne répond pas"
    return 1
}

manual_rollback() {
    local last
    # « || true » : dossier absent → find échoue, et pipefail arrêterait le script
    last="$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name 'bascule-*' 2>/dev/null | sort | tail -n 1 || true)"
    if [ -z "$last" ] || [ ! -f "$last/state" ]; then
        die "Aucune bascule enregistrée dans $BACKUP_ROOT" "$E_CONFIG"
    fi
    # shellcheck source=/dev/null
    source "$last/state"
    info "Bascule du $DATE (dossier $last), commit d'origine ${OLD_COMMIT:0:7}"
    check_deps
    confirm "Revenir à l'ancienne stack (3 conteneurs) ?" || die "Abandon" "$E_OK"
    if rollback; then
        ok "Retour arrière terminé. Sauvegardes conservées dans $last"
        exit "$E_OK"
    fi
    exit "$E_ROLLBACK_FAILED"
}

#-------------------------------------------------------------------------------
# Résumé final
#-------------------------------------------------------------------------------
summary() {
    step "Bascule terminée"
    cat <<EOF
  Conteneurs   : $(docker ps --filter "label=com.docker.compose.project=arrmada" --format '{{.Names}} ({{.Status}})' | paste -sd ' ' -)
  Interface    : http://$(lan_ip):3420  (et :8420 pour les TV / applis)
  Sauvegardes  : $BACKUP_DIR
  Journal      : $LOG_FILE
  Retour arrière possible tant que les anciennes images existent :
                 $0 --rollback

  Mises à jour : maj-arrmada.sh (git pull + ./deploy.sh) comme avant.
EOF
    case "$IMAGE_SOURCE" in
        ghcr|local-existing)
            echo "                 ./deploy.sh télécharge l'image publiée par la CI (rien à construire sur le NAS)." ;;
        local-build)
            echo "                 L'image est construite sur place : ./deploy.sh --build (ou rendre le paquet GHCR public"
            echo "                 puis retirer « build: . » de l'override)." ;;
    esac
    if [ ${#WARNINGS[@]} -gt 0 ]; then
        printf '\n%sÀ regarder :%s\n' "$C_YELLOW" "$C_RESET"
        printf '  • %s\n' "${WARNINGS[@]}"
    fi
    cat <<EOF

  Une fois satisfait (quelques jours), place libérée par les anciennes images
  (elles servent au retour arrière, ne les supprimer qu'ensuite) :
    docker image rm ${OLD_PROJECT}-arrmada-backend ${OLD_PROJECT}-arrmada-frontend
EOF
}

#-------------------------------------------------------------------------------
# Principal
#-------------------------------------------------------------------------------
main() {
    parse_args "$@"
    $OPT_ROLLBACK && manual_rollback

    TMP_DIR="$(mktemp -d)"
    # Journal dès la 1re ligne (contrôles compris) : d'abord dans le dossier
    # temporaire, puis recopié dans le dossier de sauvegarde une fois créé.
    PRE_LOG="$TMP_DIR/bascule.log"
    exec > >(tee -a "$PRE_LOG") 2>&1
    preflight

    step "2/6 Plan"
    cat <<EOF
  1. Récupérer l'image unique ($IMAGE) — l'ancienne stack tourne pendant ce temps
  2. Générer docker-compose.override.yml à partir de l'ancien conteneur
  3. Sauvegarder : base ($PG_MODE)$($OPT_SKIP_DATA_BACKUP || echo ", data/"), .env, compose → $BACKUP_ROOT/bascule-…
  4. Arrêter les 3 anciens conteneurs (volumes conservés), git pull, démarrer « arrmada »
  5. Vérifier : santé, même base, même nombre de services (${OLD_SERVICES:-?}), même mot de passe
  6. En cas d'échec : retour automatique à l'ancienne stack
EOF

    if $OPT_DRY_RUN; then
        IMAGE_SOURCE="ghcr"
        step "Override qui serait généré (--dry-run)"
        generate_override "$TMP_DIR/docker-compose.override.yml"
        validate_override "$TMP_DIR/docker-compose.override.yml"
        sed 's/^/    /' "$TMP_DIR/docker-compose.override.yml"
        ok "Dry-run terminé : rien n'a été modifié"
        exit "$E_OK"
    fi

    confirm "Lancer la bascule ?" || die "Abandon : rien n'a été modifié" "$E_OK"

    BACKUP_DIR="$BACKUP_ROOT/bascule-$(date '+%Y%m%d-%H%M%S')"
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
    LOG_FILE="$BACKUP_DIR/bascule.log"
    STATE_FILE="$BACKUP_DIR/state"
    cp "$PRE_LOG" "$LOG_FILE"
    exec > >(tee -a "$LOG_FILE") 2>&1
    info "Journal : $LOG_FILE"

    step "3/6 Préparation (ArrMada reste en ligne)"
    fetch_image
    generate_override "$BACKUP_DIR/docker-compose.override.yml"
    validate_override "$BACKUP_DIR/docker-compose.override.yml"
    save_state

    backup

    if switch_stack && verify_new; then
        summary
        exit "$E_OK"
    fi

    err "La bascule a échoué : retour automatique à l'ancienne stack"
    if rollback; then
        err "Ancienne stack restaurée. Rien n'est perdu ; journal : $LOG_FILE"
        exit "$E_ROLLED_BACK"
    fi
    err "RETOUR ARRIÈRE EN ÉCHEC. Sauvegardes : $BACKUP_DIR (arrmada-db.sql.gz, data.tar.gz)"
    err "À la main : cd $APP_DIR && git reset --keep $OLD_COMMIT && mv docker-compose.override.yml docker-compose.override.yml.next && docker compose up -d"
    exit "$E_ROLLBACK_FAILED"
}

main "$@"

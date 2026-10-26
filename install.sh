#!/usr/bin/env bash
#===============================================================================
# @name        : install.sh
# @description : Installe une stack média complète (Sonarr, Radarr, Prowlarr,
#                Bazarr, SABnzbd, Deluge ou qBittorrent, Jellyfin) + ArrMada,
#                adaptée à la plateforme (Synology, Unraid, Linux, macOS/WSL),
#                avec clés API pré-générées pour un câblage 100 % automatique.
# @author      : ArrMada
# @version     : 1.0.0
# @date        : 2026-10-17
# @usage       : curl -fsSL https://raw.githubusercontent.com/tcastel94/arrmada/main/install.sh | sudo bash
#                sudo ./install.sh [options]          (./install.sh --help)
#===============================================================================
#
# Ce que fait le script, dans l'ordre :
#   1. détecte la plateforme → chemins, PUID/PGID, IP, commande compose ;
#   2. repère les applis DÉJÀ installées (conteneur du même nom) : elles sont
#      laissées telles quelles, ArrMada les câblera ;
#   3. crée l'arborescence TRaSH Guides (/data/{torrents,usenet,media}) :
#      un seul système de fichiers → hardlinks et déplacements instantanés ;
#   4. pré-écrit la config de chaque NOUVELLE appli avec une clé API générée
#      (jamais d'écrasement d'un fichier existant) ;
#   5. génère docker-compose.yml + credentials.txt, puis démarre la stack ;
#   6. affiche les URL : il reste à ouvrir ArrMada → assistant → « Appliquer ».
#
# Idempotent : relancer le script conserve les clés, mots de passe et
# fichiers existants ; seul docker-compose.yml est régénéré (avec sauvegarde).
#
# Compatible bash 3.2 (macOS) : pas de tableaux associatifs ni de mapfile.

set -euo pipefail

#-------------------------------------------------------------------------------
# Constantes
#-------------------------------------------------------------------------------
readonly SCRIPT_VERSION="1.0.0"

# Codes retour (convention : 0 OK, 1 générique, 2 config, 3 dépendance, 4 paramètres)
readonly E_GENERIC=1
readonly E_CONFIG=2
readonly E_DEPS=3
readonly E_PARAMS=4
readonly E_PORTS=5   # port déjà utilisé par autre chose qu'une appli de la stack
readonly E_START=6   # échec du démarrage des conteneurs

# Synology installe docker dans /usr/local/bin, absent du PATH de certains sudo.
export PATH="${PATH}:/usr/local/bin:/usr/syno/bin:/usr/local/sbin"

ARRMADA_IMAGE="${ARRMADA_IMAGE:-ghcr.io/tcastel94/arrmada:latest}"

# Ports publiés sur l'hôte (ceux des applis = leurs ports par défaut).
readonly PORT_ARRMADA=3420
# Ancien port de l'API d'ArrMada : l'add-on Kodi des TV s'y connecte (il
# convertit même :3420 en :8420). Publié s'il est libre, vers le même 3420.
readonly PORT_ARRMADA_TV=8420
PUBLISH_TV_PORT=true
readonly PORT_SONARR=8989
readonly PORT_RADARR=7878
readonly PORT_PROWLARR=9696
readonly PORT_BAZARR=6767
readonly PORT_SABNZBD=8080
readonly PORT_DELUGE=8112
readonly PORT_QBITTORRENT=8090   # 8080 est déjà celui de SABnzbd
readonly PORT_TORRENT=6881       # entrant BitTorrent (TCP + UDP)
readonly PORT_JELLYFIN=8096

#-------------------------------------------------------------------------------
# Options (valeurs par défaut, complétées par detect_platform)
#-------------------------------------------------------------------------------
OPT_YES=false
OPT_DRY_RUN=false
OPT_UNINSTALL=false
OPT_TORRENT=""        # deluge | qbittorrent | none
OPT_USENET=""         # yes | no
OPT_JELLYFIN=""       # yes | no
OPT_CONFIG_ROOT=""
OPT_DATA_ROOT=""
OPT_PUID=""
OPT_PGID=""
OPT_TZ=""
OPT_PLATFORM="${ARRMADA_PLATFORM:-}"   # forcer la détection (tests)

# Rempli au fil de l'exécution
PLATFORM=""
PLATFORM_LABEL=""
CONFIG_ROOT=""
DATA_ROOT=""
STACK_DIR=""
PUID=""
PGID=""
TZ_VALUE=""
HOST_IP=""
INTERACTIVE=false
COMPOSE_MODE=""       # plugin | standalone | container
APPS=()               # applis à INSTALLER
EXISTING=()           # applis déjà présentes (laissées telles quelles)
CREATED_DIRS=()
# --dry-run : préfixe d'ÉCRITURE (dossier jetable). Les chemins inscrits dans
# docker-compose.yml restent les vrais chemins de la plateforme.
ROOT_PREFIX=""

#-------------------------------------------------------------------------------
# Affichage
#-------------------------------------------------------------------------------
if [ -t 1 ]; then
    C_RED=$'\033[0;31m' C_GREEN=$'\033[0;32m' C_YELLOW=$'\033[1;33m'
    C_BLUE=$'\033[0;34m' C_CYAN=$'\033[0;36m' C_BOLD=$'\033[1m' C_RESET=$'\033[0m'
else
    C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_CYAN="" C_BOLD="" C_RESET=""
fi

log()   { printf '%s[ArrMada]%s %s\n' "$C_CYAN" "$C_RESET" "$*"; }
ok()    { printf '  %s✔%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '  %s⚠%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die()   { local code="${2:-$E_GENERIC}"; printf '%s✖ %s%s\n' "$C_RED" "$1" "$C_RESET" >&2; exit "$code"; }
title() { printf '\n%s%s── %s %s%s\n' "$C_BOLD" "$C_BLUE" "$*" "────────────────────────────────" "$C_RESET"; }

usage() {
    cat <<EOF
ArrMada — installeur de stack média ${SCRIPT_VERSION}

Usage : sudo ./install.sh [options]
        curl -fsSL https://raw.githubusercontent.com/tcastel94/arrmada/main/install.sh | sudo bash -s -- [options]

Options :
  -y, --yes                 aucune question, valeurs par défaut
      --torrent CLIENT      deluge (défaut) | qbittorrent | none
      --no-usenet           sans SABnzbd
      --no-jellyfin         sans Jellyfin
      --config-root DIR     dossier des configs des applis (« appdata »)
      --data-root DIR       dossier des médias et téléchargements (/data)
      --puid N / --pgid N   propriétaire des fichiers (défaut : détecté)
      --tz ZONE             fuseau horaire (défaut : détecté, ex. Europe/Paris)
      --dry-run             génère les fichiers dans un dossier temporaire, sans rien démarrer
      --uninstall           arrête et supprime les conteneurs (configs et médias CONSERVÉS)
  -h, --help                cette aide

Variables : ARRMADA_IMAGE (image ArrMada), ARRMADA_PLATFORM (forcer : linux|synology|unraid|macos),
            ARRMADA_COMPOSE (forcer : plugin|standalone|container)
EOF
}

#-------------------------------------------------------------------------------
# Arguments
#-------------------------------------------------------------------------------
parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -y|--yes)        OPT_YES=true ;;
            --torrent)       OPT_TORRENT="${2:-}"; shift ;;
            --no-usenet)     OPT_USENET=no ;;
            --no-jellyfin)   OPT_JELLYFIN=no ;;
            --config-root)   OPT_CONFIG_ROOT="${2:-}"; shift ;;
            --data-root)     OPT_DATA_ROOT="${2:-}"; shift ;;
            --puid)          OPT_PUID="${2:-}"; shift ;;
            --pgid)          OPT_PGID="${2:-}"; shift ;;
            --tz)            OPT_TZ="${2:-}"; shift ;;
            --dry-run)       OPT_DRY_RUN=true ;;
            --uninstall)     OPT_UNINSTALL=true ;;
            -h|--help)       usage; exit 0 ;;
            *)               usage >&2; die "Option inconnue : $1" "$E_PARAMS" ;;
        esac
        shift
    done
    case "$OPT_TORRENT" in
        ""|deluge|qbittorrent|none) ;;
        *) die "--torrent : deluge, qbittorrent ou none (reçu : $OPT_TORRENT)" "$E_PARAMS" ;;
    esac
    for v in "$OPT_PUID" "$OPT_PGID"; do
        case "$v" in ""|*[!0-9]*) [ -z "$v" ] || die "PUID/PGID doivent être numériques (reçu : $v)" "$E_PARAMS" ;; esac
    done
    # Questions possibles uniquement avec un terminal (curl | bash : stdin = le script).
    if ! $OPT_YES && [ -r /dev/tty ] && { : < /dev/tty; } 2>/dev/null; then
        INTERACTIVE=true
    fi
}

# ask "Question" "défaut" → réponse sur stdout (lit /dev/tty, pas stdin)
ask() {
    local answer=""
    if $INTERACTIVE; then
        printf '  %s?%s %s [%s] : ' "$C_BOLD" "$C_RESET" "$1" "$2" > /dev/tty
        IFS= read -r answer < /dev/tty || true
    fi
    printf '%s' "${answer:-$2}"
}

# ask_yn "Question" "o|n" → code retour 0 = oui
ask_yn() {
    local answer
    answer="$(ask "$1 (o/n)" "$2")"
    case "$answer" in o|O|oui|Oui|y|Y|yes) return 0 ;; *) return 1 ;; esac
}

#-------------------------------------------------------------------------------
# Plateforme
#-------------------------------------------------------------------------------
detect_platform() {
    PLATFORM="$OPT_PLATFORM"
    if [ -z "$PLATFORM" ]; then
        if [ -f /etc/unraid-version ]; then
            PLATFORM=unraid
        elif [ -f /etc/synoinfo.conf ] || [ -f /etc.defaults/VERSION ]; then
            PLATFORM=synology
        elif [ "$(uname -s)" = "Darwin" ]; then
            PLATFORM=macos
        else
            PLATFORM=linux
        fi
    fi

    local default_config default_data default_uid default_gid
    case "$PLATFORM" in
        unraid)
            PLATFORM_LABEL="Unraid $(sed -n 's/^version="\(.*\)"/\1/p' /etc/unraid-version 2>/dev/null || true)"
            default_config=/mnt/user/appdata
            default_data=/mnt/user/data
            default_uid=99 default_gid=100        # nobody:users, convention Unraid
            ;;
        synology)
            PLATFORM_LABEL="Synology DSM $(sed -n 's/^productversion="\(.*\)"/\1/p' /etc.defaults/VERSION 2>/dev/null || true)"
            default_config=/volume1/docker
            default_data=/volume1/data
            default_uid="$(id -u "${SUDO_USER:-admin}" 2>/dev/null || echo 1026)"
            default_gid=100                       # groupe « users » de DSM
            ;;
        macos)
            PLATFORM_LABEL="macOS (Docker Desktop)"
            default_config="${HOME}/arrmada/config"
            default_data="${HOME}/arrmada/data"
            default_uid="$(id -u)" default_gid="$(id -g)"
            ;;
        linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                PLATFORM_LABEL="Linux (WSL / Docker Desktop)"
            else
                # shellcheck disable=SC1091 # fichier de l'hôte, lu à l'exécution
                PLATFORM_LABEL="Linux $(. /etc/os-release 2>/dev/null && printf '%s' "${PRETTY_NAME:-}")"
            fi
            default_config=/opt/arrmada/config
            default_data=/srv/data
            default_uid="${SUDO_UID:-$(id -u)}" default_gid="${SUDO_GID:-$(id -g)}"
            ;;
        *) die "Plateforme inconnue : $PLATFORM (linux|synology|unraid|macos)" "$E_PARAMS" ;;
    esac

    CONFIG_ROOT="${OPT_CONFIG_ROOT:-$default_config}"
    DATA_ROOT="${OPT_DATA_ROOT:-$default_data}"
    PUID="${OPT_PUID:-$default_uid}"
    PGID="${OPT_PGID:-$default_gid}"
    # root comme propriétaire des fichiers : à éviter (lancé via « su » sans sudo).
    if [ "$PUID" = "0" ] && [ -z "$OPT_PUID" ] && [ "$PLATFORM" = "linux" ]; then
        PUID=1000 PGID=1000
    fi
    TZ_VALUE="${OPT_TZ:-$(detect_timezone)}"
    HOST_IP="$(detect_ip)"
}

detect_timezone() {
    local tz=""
    if [ -n "${TZ:-}" ]; then
        tz="$TZ"
    elif [ -f /etc/timezone ]; then
        tz="$(cat /etc/timezone)"
    elif [ -L /etc/localtime ]; then
        tz="$(readlink /etc/localtime | sed -n 's|.*zoneinfo/||p')"
    fi
    printf '%s' "${tz:-Europe/Paris}"
}

detect_ip() {
    local ip=""
    if command -v ip >/dev/null 2>&1; then
        ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") { print $(i + 1); exit }}')"
    fi
    if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
    fi
    if [ -z "$ip" ] && command -v ipconfig >/dev/null 2>&1; then
        ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
    fi
    printf '%s' "${ip:-localhost}"
}

#-------------------------------------------------------------------------------
# Dépendances : docker + compose (plugin, binaire, ou conteneur docker:cli)
#-------------------------------------------------------------------------------
check_deps() {
    if ! command -v docker >/dev/null 2>&1; then
        case "$PLATFORM" in
            linux)
                warn "Docker n'est pas installé."
                if ask_yn "L'installer maintenant avec le script officiel (get.docker.com) ?" "o"; then
                    curl -fsSL https://get.docker.com | sh || die "Installation de Docker échouée" "$E_DEPS"
                else
                    die "Docker est requis : https://docs.docker.com/engine/install/" "$E_DEPS"
                fi
                ;;
            synology) die "Installe « Container Manager » depuis le Centre de paquets DSM, puis relance." "$E_DEPS" ;;
            unraid)   die "Active Docker : Settings → Docker → Enable Docker = Yes, puis relance." "$E_DEPS" ;;
            macos)    die "Installe Docker Desktop : https://www.docker.com/products/docker-desktop/" "$E_DEPS" ;;
        esac
    fi
    docker info >/dev/null 2>&1 || die "Le démon Docker ne répond pas (démarré ? droits ? relance avec sudo)." "$E_DEPS"

    if [ -n "${ARRMADA_COMPOSE:-}" ]; then
        COMPOSE_MODE="$ARRMADA_COMPOSE"   # forcé (tests) : plugin | standalone | container
    elif docker compose version >/dev/null 2>&1; then
        COMPOSE_MODE=plugin
    elif command -v docker-compose >/dev/null 2>&1 && docker-compose version 2>/dev/null | grep -q 'v2\|version 2'; then
        COMPOSE_MODE=standalone
    else
        # Unraid (sans plugin Compose Manager), vieux DSM… : compose tourne
        # dans un conteneur officiel docker:cli qui pilote le démon de l'hôte.
        COMPOSE_MODE=container
        warn "Docker Compose absent : utilisation de l'image officielle docker:cli à la place."
    fi
    ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) — compose : ${COMPOSE_MODE}"
}

# compose <args…> — dans le dossier de la stack, quel que soit le mode.
compose() {
    case "$COMPOSE_MODE" in
        plugin)     (cd "$STACK_DIR" && docker compose "$@") ;;
        standalone) (cd "$STACK_DIR" && docker-compose "$@") ;;
        container)
            docker run --rm \
                -v /var/run/docker.sock:/var/run/docker.sock \
                -v "${STACK_DIR}:${STACK_DIR}" -w "$STACK_DIR" \
                docker:cli compose "$@"
            ;;
    esac
}

#-------------------------------------------------------------------------------
# Choix des applis
#-------------------------------------------------------------------------------
app_port() {
    case "$1" in
        arrmada) echo "$PORT_ARRMADA" ;;   sonarr) echo "$PORT_SONARR" ;;
        radarr) echo "$PORT_RADARR" ;;     prowlarr) echo "$PORT_PROWLARR" ;;
        bazarr) echo "$PORT_BAZARR" ;;     sabnzbd) echo "$PORT_SABNZBD" ;;
        deluge) echo "$PORT_DELUGE" ;;     qbittorrent) echo "$PORT_QBITTORRENT" ;;
        jellyfin) echo "$PORT_JELLYFIN" ;;
    esac
}

app_label() {
    case "$1" in
        arrmada) echo "ArrMada" ;; sabnzbd) echo "SABnzbd" ;; qbittorrent) echo "qBittorrent" ;;
        *) printf '%s%s' "$(printf '%s' "${1:0:1}" | tr '[:lower:]' '[:upper:]')" "${1:1}" ;;
    esac
}

has_app() {
    local a
    for a in "${APPS[@]}"; do [ "$a" = "$1" ] && return 0; done
    return 1
}

choose_apps() {
    title "Applications"
    if [ -z "$OPT_TORRENT" ]; then
        local choice
        choice="$(ask "Client torrent : 1) Deluge  2) qBittorrent  3) aucun" "1")"
        case "$choice" in 2|qbittorrent) OPT_TORRENT=qbittorrent ;; 3|none|aucun) OPT_TORRENT=none ;; *) OPT_TORRENT=deluge ;; esac
    fi
    if [ -z "$OPT_USENET" ]; then
        if ask_yn "Usenet avec SABnzbd ?" "o"; then OPT_USENET=yes; else OPT_USENET=no; fi
    fi
    if [ -z "$OPT_JELLYFIN" ]; then
        if ask_yn "Serveur multimédia Jellyfin ?" "o"; then OPT_JELLYFIN=yes; else OPT_JELLYFIN=no; fi
    fi

    local wanted=(arrmada sonarr radarr prowlarr bazarr)
    [ "$OPT_USENET" = "yes" ] && wanted+=(sabnzbd)
    [ "$OPT_TORRENT" != "none" ] && wanted+=("$OPT_TORRENT")
    [ "$OPT_JELLYFIN" = "yes" ] && wanted+=(jellyfin)

    # Une appli dont le conteneur existe déjà (même nom) n'est pas réinstallée.
    local existing_names="" app
    if ! $OPT_DRY_RUN; then
        existing_names=" $(docker ps -a --format '{{.Names}}' 2>/dev/null | tr '\n' ' ') "
    fi
    for app in "${wanted[@]}"; do
        if [[ "$existing_names" == *" ${app} "* ]] && ! stack_owns "$app"; then
            EXISTING+=("$app")
        else
            APPS+=("$app")
        fi
    done
    ok "À installer : $(printf '%s ' "${APPS[@]}")"
    if [ ${#EXISTING[@]} -gt 0 ]; then
        ok "Déjà présentes (gardées, câblées par ArrMada) : $(printf '%s ' "${EXISTING[@]}")"
    fi
    case " ${EXISTING[*]+"${EXISTING[*]}"} " in
        *" arrmada "*) warn "ArrMada existe déjà : ajoute-lui le montage « ${CONFIG_ROOT}:/appdata:ro » pour l'auto-configuration." ;;
    esac
}

# Le conteneur appartient-il à NOTRE stack (relance du script) ?
stack_owns() {
    [ "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$1" 2>/dev/null)" = "arrmada-stack" ]
}

choose_paths() {
    title "Emplacements (${PLATFORM_LABEL})"
    CONFIG_ROOT="$(ask "Configs des applis (appdata)" "$CONFIG_ROOT")"
    DATA_ROOT="$(ask "Médias + téléchargements (data)" "$DATA_ROOT")"
    PUID="$(ask "PUID (propriétaire des fichiers)" "$PUID")"
    PGID="$(ask "PGID (groupe)" "$PGID")"
    CONFIG_ROOT="${CONFIG_ROOT%/}" DATA_ROOT="${DATA_ROOT%/}"
    case "$CONFIG_ROOT$DATA_ROOT" in *" "*) die "Les chemins ne doivent pas contenir d'espace." "$E_PARAMS" ;; esac
    STACK_DIR="${CONFIG_ROOT}/arrmada"
    if [ "$PLATFORM" = "synology" ] && ! $OPT_DRY_RUN; then
        local share
        for share in "$CONFIG_ROOT" "$DATA_ROOT"; do
            # /volume1/<partage> : un dossier créé en ligne de commande n'est
            # PAS un « dossier partagé » DSM (invisible dans File Station).
            case "$share" in /volume[0-9]*/*/*|/volume[0-9]*) continue ;; /volume[0-9]*/*) ;; *) continue ;; esac
            if [ ! -d "$share" ]; then
                warn "Crée d'abord le dossier partagé « $(basename "$share") » : Panneau de configuration → Dossier partagé."
                ask_yn "Continuer quand même ?" "n" || die "Annulé : crée le dossier partagé puis relance." "$E_CONFIG"
            fi
        done
    fi
    ok "Configs : ${CONFIG_ROOT}/<appli>   Médias : ${DATA_ROOT}   Stack : ${STACK_DIR}"
    ok "PUID/PGID : ${PUID}/${PGID}   Fuseau : ${TZ_VALUE}   IP : ${HOST_IP}"
}

#-------------------------------------------------------------------------------
# Ports : refuse un port occupé par autre chose que notre stack
#-------------------------------------------------------------------------------
port_busy() {
    # /dev/tcp : intégré à bash, aucun outil externe (ss/netstat absents sur NAS).
    (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

check_ports() {
    local app port busy=()
    for app in "${APPS[@]}"; do
        stack_owns "$app" && continue
        port="$(app_port "$app")"
        if port_busy "$port"; then busy+=("${app}:${port}"); fi
        # Port des TV : utile mais pas indispensable → avertissement seulement
        if [ "$app" = arrmada ] && port_busy "$PORT_ARRMADA_TV"; then
            PUBLISH_TV_PORT=false
            warn "Port ${PORT_ARRMADA_TV} occupé : non publié. L'add-on Kodi des TV devra pointer sur :${PORT_ARRMADA} (sans conversion vers ${PORT_ARRMADA_TV})."
        fi
    done
    if [ ${#busy[@]} -gt 0 ]; then
        die "Port(s) déjà utilisé(s) par un autre programme : ${busy[*]}. Libère-les ou retire l'appli (--no-usenet, --torrent none…)." "$E_PORTS"
    fi
    ok "Ports libres"
}

#-------------------------------------------------------------------------------
# Secrets
#-------------------------------------------------------------------------------
gen_hex() {   # gen_hex <octets> → chaîne hexadécimale (clé API *arr = 16 octets = 32 car.)
    od -An -tx1 -N "$1" /dev/urandom | tr -d ' \n'
}

gen_password() {   # 20 caractères alphanumériques (aucun caractère à échapper)
    local pw=""
    while [ ${#pw} -lt 20 ]; do
        pw="${pw}$(od -An -tu1 -N 64 /dev/urandom | tr -s ' ' '\n' | awk 'NF { c = $1 % 62; printf "%c", (c < 10 ? 48 + c : (c < 36 ? 55 + c : 61 + c)) }')"
    done
    printf '%s' "${pw:0:20}"
}

sha1_hex() {
    if command -v sha1sum >/dev/null 2>&1; then printf '%s' "$1" | sha1sum | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then printf '%s' "$1" | shasum -a 1 | awk '{print $1}'
    else printf '%s' "$1" | openssl sha1 | awk '{print $NF}'
    fi
}

hex_to_b64() {   # hex_to_b64 <hex> → base64 (sans xxd, absent des NAS)
    # shellcheck disable=SC2059 # le format EST la donnée : séquences \xHH
    printf "$(printf '%s' "$1" | sed 's/../\\x&/g')" | base64 | tr -d '\n'
}

# Hash qBittorrent : PBKDF2-HMAC-SHA512, 100 000 itérations → "sel_b64:clé_b64".
# Par ordre de préférence : python3 de l'hôte, openssl ≥ 3 (« openssl kdf »),
# puis un conteneur python jetable (Docker est forcément présent).
qbit_hash() {
    local code='import base64,hashlib,os,sys
s=os.urandom(16);k=hashlib.pbkdf2_hmac("sha512",sys.argv[1].encode(),s,100000,64)
print(base64.b64encode(s).decode()+":"+base64.b64encode(k).decode())'
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "$code" "$1"
        return
    fi
    if openssl kdf -help >/dev/null 2>&1; then
        local salt key
        salt="$(gen_hex 16)"
        key="$(openssl kdf -keylen 64 -kdfopt digest:SHA512 -kdfopt "pass:$1" \
            -kdfopt "hexsalt:${salt}" -kdfopt iter:100000 PBKDF2 | tr -d ':\n')"
        printf '%s:%s\n' "$(hex_to_b64 "$salt")" "$(hex_to_b64 "$key")"
        return
    fi
    if $OPT_DRY_RUN && ! command -v docker >/dev/null 2>&1; then
        echo "APERCU:dry-run"   # aperçu seulement : rien ne sera démarré
        return
    fi
    docker run --rm python:3.12-alpine python -c "$code" "$1"
}


#-------------------------------------------------------------------------------
# Arborescence
#-------------------------------------------------------------------------------
# fs <chemin> → chemin réel sur disque (préfixé en --dry-run)
fs() { printf '%s%s' "$ROOT_PREFIX" "$1"; }

make_dir() {
    # Mémorise CHAQUE dossier réellement créé, ancêtres compris (mkdir -p crée
    # aussi les parents : ils doivent appartenir à PUID, pas à root).
    local path missing=()
    path="$(fs "$1")"
    while [ -n "$path" ] && [ "$path" != "/" ] && [ "$path" != "$ROOT_PREFIX" ] && [ ! -d "$path" ]; do
        missing+=("$path")
        path="$(dirname "$path")"
    done
    [ ${#missing[@]} -eq 0 ] && return 0
    mkdir -p "$(fs "$1")"
    CREATED_DIRS+=("${missing[@]}")
}

create_tree() {
    title "Arborescence"
    local sub
    # Layout TRaSH Guides : tout sous UN SEUL point de montage /data.
    for sub in torrents/tv torrents/movies torrents/incomplete \
               usenet/incomplete usenet/complete/tv usenet/complete/movies \
               media/tv media/movies; do
        make_dir "${DATA_ROOT}/${sub}"
    done
    make_dir "$STACK_DIR/data"
    local app
    for app in "${APPS[@]}"; do
        [ "$app" = "arrmada" ] || make_dir "${CONFIG_ROOT}/${app}"
    done
    # Uniquement les dossiers CRÉÉS ici (jamais un chown -R sur une médiathèque existante).
    if [ "$(id -u)" = "0" ] && [ -z "$ROOT_PREFIX" ] && [ ${#CREATED_DIRS[@]} -gt 0 ]; then
        chown "${PUID}:${PGID}" "${CREATED_DIRS[@]}"
    fi
    ok "${DATA_ROOT}/{torrents,usenet,media}/{tv,movies} prêts (${#CREATED_DIRS[@]} dossier(s) créé(s))"
}

#-------------------------------------------------------------------------------
# Configs pré-remplies (UNIQUEMENT si absentes : jamais d'écrasement)
#-------------------------------------------------------------------------------
# Variables exportées dans stack.json / credentials.txt
DELUGE_PASSWORD=""
QBIT_PASSWORD=""
JELLYFIN_PASSWORD=""

write_file() {   # write_file <chemin> <mode>  (contenu sur stdin)
    local dir
    dir="$(dirname "$1")"
    make_dir "$dir"
    cat > "$(fs "$1")"
    chmod "$2" "$(fs "$1")"
    if [ "$(id -u)" = "0" ] && [ -z "$ROOT_PREFIX" ]; then chown "${PUID}:${PGID}" "$1" "$dir"; fi
}

seed_arr() {   # seed_arr <appli> <port> — config.xml commun Sonarr/Radarr/Prowlarr
    local file="${CONFIG_ROOT}/$1/config.xml"
    if [ -f "$(fs "$file")" ]; then
        ok "$(app_label "$1") : config existante conservée"
        return
    fi
    write_file "$file" 644 <<EOF
<Config>
  <BindAddress>*</BindAddress>
  <Port>$2</Port>
  <SslPort>$(( $2 + 1 ))</SslPort>
  <EnableSsl>False</EnableSsl>
  <LaunchBrowser>False</LaunchBrowser>
  <ApiKey>$(gen_hex 16)</ApiKey>
  <UrlBase></UrlBase>
  <InstanceName>$(app_label "$1")</InstanceName>
  <UpdateMechanism>Docker</UpdateMechanism>
  <LogLevel>info</LogLevel>
</Config>
EOF
    ok "$(app_label "$1") : clé API générée"
}

seed_bazarr() {
    local file="${CONFIG_ROOT}/bazarr/config/config.yaml"
    if [ -f "$(fs "$file")" ]; then ok "Bazarr : config existante conservée"; return; fi
    write_file "$file" 644 <<EOF
auth:
  apikey: $(gen_hex 16)
general:
  port: ${PORT_BAZARR}
  base_url: ''
EOF
    ok "Bazarr : clé API générée"
}

seed_sabnzbd() {
    local file="${CONFIG_ROOT}/sabnzbd/sabnzbd.ini"
    if [ -f "$(fs "$file")" ]; then ok "SABnzbd : config existante conservée"; return; fi
    # host_whitelist : autorise l'accès par le nom DNS Docker « sabnzbd »
    # (sinon « Access denied - Hostname verification failed »).
    write_file "$file" 600 <<EOF
[misc]
api_key = $(gen_hex 16)
nzb_key = $(gen_hex 16)
host_whitelist = sabnzbd, $(hostname 2>/dev/null || echo localhost),
download_dir = /data/usenet/incomplete
complete_dir = /data/usenet/complete
permissions = 775
[categories]
[[*]]
name = *
order = 0
pp = 3
script = None
dir = ""
priority = 0
[[movies]]
name = movies
order = 1
pp = ""
script = Default
dir = movies
priority = -100
[[tv]]
name = tv
order = 2
pp = ""
script = Default
dir = tv
priority = -100
EOF
    ok "SABnzbd : clé API + catégories tv/movies"
}

seed_deluge() {
    local dir="${CONFIG_ROOT}/deluge"
    if [ -f "$(fs "${dir}/web.conf")" ]; then ok "Deluge : config existante conservée"; return; fi
    local salt
    salt="$(gen_hex 20)"
    DELUGE_PASSWORD="$(gen_password)"
    # Format Deluge : deux objets JSON concaténés (en-tête de version + réglages).
    write_file "${dir}/web.conf" 600 <<EOF
{"file": 2, "format": 1}{
    "port": ${PORT_DELUGE},
    "pwd_salt": "${salt}",
    "pwd_sha1": "$(sha1_hex "${salt}${DELUGE_PASSWORD}")",
    "first_login": false
}
EOF
    if [ ! -f "$(fs "${dir}/core.conf")" ]; then
        write_file "${dir}/core.conf" 644 <<EOF
{"file": 1, "format": 1}{
    "download_location": "/data/torrents/incomplete",
    "move_completed": true,
    "move_completed_path": "/data/torrents",
    "enabled_plugins": ["Label"],
    "listen_ports": [${PORT_TORRENT}, ${PORT_TORRENT}],
    "random_port": false
}
EOF
    fi
    ok "Deluge : mot de passe web généré, plugin Label activé"
}

seed_qbittorrent() {
    local file="${CONFIG_ROOT}/qbittorrent/qBittorrent/qBittorrent.conf"
    if [ -f "$(fs "$file")" ]; then ok "qBittorrent : config existante conservée"; return; fi
    QBIT_PASSWORD="$(gen_password)"
    local hash
    hash="$(qbit_hash "$QBIT_PASSWORD")" || die "Impossible de calculer le hash qBittorrent" "$E_DEPS"
    write_file "$file" 600 <<EOF
[BitTorrent]
Session\\DefaultSavePath=/data/torrents
Session\\TempPath=/data/torrents/incomplete
Session\\TempPathEnabled=true
Session\\Port=${PORT_TORRENT}

[Preferences]
Downloads\\SavePath=/data/torrents
WebUI\\Port=${PORT_QBITTORRENT}
WebUI\\Username=admin
WebUI\\Password_PBKDF2="@ByteArray(${hash})"
WebUI\\ServerDomains=*
EOF
    ok "qBittorrent : mot de passe généré (utilisateur admin)"
}

seed_configs() {
    title "Configuration des applis"
    local app
    for app in "${APPS[@]}"; do
        case "$app" in
            sonarr|radarr|prowlarr) seed_arr "$app" "$(app_port "$app")" ;;
            bazarr)      seed_bazarr ;;
            sabnzbd)     seed_sabnzbd ;;
            deluge)      seed_deluge ;;
            qbittorrent) seed_qbittorrent ;;
            jellyfin)    ok "Jellyfin : configuré après démarrage (compte admin, bibliothèques, clé API)" ;;
        esac
    done
    write_stack_json
}

# stack.json : lu par ArrMada (mots de passe torrent + dossiers racine TRaSH).
# Lisible seulement par PUID : il contient les mots de passe générés.
write_stack_json() {
    local file="${STACK_DIR}/data/stack.json" old_deluge="" old_qbit=""
    if [ -f "$(fs "$file")" ]; then   # relance : garder les mots de passe déjà générés
        old_deluge="$(sed -n 's/.*"deluge": *{"password": *"\([^"]*\)".*/\1/p' "$(fs "$file")")"
        old_qbit="$(sed -n 's/.*"qbittorrent": *{"username": *"admin", *"password": *"\([^"]*\)".*/\1/p' "$(fs "$file")")"
    fi
    DELUGE_PASSWORD="${DELUGE_PASSWORD:-$old_deluge}"
    QBIT_PASSWORD="${QBIT_PASSWORD:-$old_qbit}"
    local creds=""
    [ -n "$DELUGE_PASSWORD" ] && creds="\"deluge\": {\"password\": \"${DELUGE_PASSWORD}\"}"
    if [ -n "$QBIT_PASSWORD" ]; then
        [ -n "$creds" ] && creds="${creds}, "
        creds="${creds}\"qbittorrent\": {\"username\": \"admin\", \"password\": \"${QBIT_PASSWORD}\"}"
    fi
    # Compte Jellyfin créé par l'installeur : affiché à l'admin dans l'assistant
    # d'ArrMada (« Ce qu'il te reste à faire »). credentials.txt appartient à
    # root : sur un NAS, son propriétaire ne peut souvent pas l'ouvrir.
    if [ -n "$JELLYFIN_PASSWORD" ]; then
        [ -n "$creds" ] && creds="${creds}, "
        creds="${creds}\"jellyfin\": {\"username\": \"admin\", \"password\": \"${JELLYFIN_PASSWORD}\"}"
    fi
    write_file "$file" 600 <<EOF
{
  "installer_version": "${SCRIPT_VERSION}",
  "platform": "${PLATFORM}",
  "layout": "trash",
  "root_folders": {"sonarr": "/data/media/tv", "radarr": "/data/media/movies"},
  "credentials": {${creds}}
}
EOF
}

#-------------------------------------------------------------------------------
# docker-compose.yml
#-------------------------------------------------------------------------------
svc_common() {   # svc_common <nom> <image> → en-tête commun à tous les services
    cat <<EOF

  $1:
    image: $2
    container_name: $1
    restart: unless-stopped
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ_VALUE}
      - UMASK=002
EOF
}

write_compose() {
    title "docker-compose.yml"
    local file="${STACK_DIR}/docker-compose.yml"
    if [ -f "$(fs "$file")" ]; then
        cp "$(fs "$file")" "$(fs "$file").bak-$(date +%Y%m%d-%H%M%S)"
        ok "Ancien compose sauvegardé"
    fi
    local media_dev=""
    # Transcodage matériel Jellyfin (Intel Quick Sync / AMD) si un GPU est exposé.
    [ -e /dev/dri ] && media_dev="yes"

    {
        cat <<EOF
# Généré par install.sh ${SCRIPT_VERSION} le $(date '+%Y-%m-%d %H:%M') — plateforme : ${PLATFORM_LABEL}
# Relancer install.sh régénère ce fichier (l'ancien est sauvegardé en .bak-*).
# Mise à jour des images : docker compose pull && docker compose up -d
# Projet « arrmada-stack » (≠ « arrmada » du compose ArrMada seul) : un
# --remove-orphans ici ne peut jamais toucher une installation séparée.
name: arrmada-stack

services:
EOF
        local app
        for app in "${APPS[@]}"; do
            case "$app" in
                arrmada)
                    cat <<EOF

  arrmada:
    image: ${ARRMADA_IMAGE}
    container_name: arrmada
    restart: unless-stopped
    init: true
    ports:
      - "${PORT_ARRMADA}:3420"
$($PUBLISH_TV_PORT && echo "      - \"${PORT_ARRMADA_TV}:3420\"   # add-on Kodi des TV")
    volumes:
      - ./data:/app/data
      - ${CONFIG_ROOT}:/appdata:ro      # lecture des clés API des autres applis
      - ${DATA_ROOT}:/data
      # Écran « Vidéos » (mangas, vidéos perso hors médiathèque) : ce qui est
      # sous /data se déclare tel quel. Un autre dossier du NAS se monte
      # d'abord sous /mnt/user (lecture seule), puis se déclare dans
      # Paramètres › Dossiers vidéo avec le chemin de DROITE, par exemple :
      # - ${DATA_ROOT%/*}/mangas:/mnt/user/mangas:ro
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ_VALUE}
      # Dossiers vidéo acceptés (chemins vus depuis le conteneur, séparés par des virgules)
      - VIDEO_ALLOWED_BASE=/mnt/user,/data
EOF
                    ;;
                sonarr|radarr|prowlarr|bazarr)
                    svc_common "$app" "lscr.io/linuxserver/${app}:latest"
                    cat <<EOF
    ports:
      - "$(app_port "$app"):$(app_port "$app")"
    volumes:
      - ${CONFIG_ROOT}/${app}:/config
EOF
                    [ "$app" = "prowlarr" ] || echo "      - ${DATA_ROOT}:/data"
                    ;;
                sabnzbd)
                    svc_common sabnzbd "lscr.io/linuxserver/sabnzbd:latest"
                    cat <<EOF
    ports:
      - "${PORT_SABNZBD}:8080"
    volumes:
      - ${CONFIG_ROOT}/sabnzbd:/config
      - ${DATA_ROOT}:/data
EOF
                    ;;
                deluge)
                    svc_common deluge "lscr.io/linuxserver/deluge:latest"
                    cat <<EOF
    ports:
      - "${PORT_DELUGE}:8112"
      - "${PORT_TORRENT}:${PORT_TORRENT}"
      - "${PORT_TORRENT}:${PORT_TORRENT}/udp"
    volumes:
      - ${CONFIG_ROOT}/deluge:/config
      - ${DATA_ROOT}:/data
EOF
                    ;;
                qbittorrent)
                    svc_common qbittorrent "lscr.io/linuxserver/qbittorrent:latest"
                    cat <<EOF
      - WEBUI_PORT=${PORT_QBITTORRENT}
      - TORRENTING_PORT=${PORT_TORRENT}
    ports:
      - "${PORT_QBITTORRENT}:${PORT_QBITTORRENT}"
      - "${PORT_TORRENT}:${PORT_TORRENT}"
      - "${PORT_TORRENT}:${PORT_TORRENT}/udp"
    volumes:
      - ${CONFIG_ROOT}/qbittorrent:/config
      - ${DATA_ROOT}:/data
EOF
                    ;;
                jellyfin)
                    svc_common jellyfin "lscr.io/linuxserver/jellyfin:latest"
                    cat <<EOF
    ports:
      - "${PORT_JELLYFIN}:8096"
    volumes:
      - ${CONFIG_ROOT}/jellyfin:/config
      - ${DATA_ROOT}/media:/data/media
EOF
                    if [ -n "$media_dev" ]; then
                        cat <<EOF
    devices:
      - /dev/dri:/dev/dri              # transcodage matériel (GPU détecté)
EOF
                    fi
                    ;;
            esac
        done
    } | write_file "$file" 644
    ok "${file}"
    write_compose_wrapper
}

# compose.sh : même commande de gestion sur toutes les plateformes, y compris
# celles sans Docker Compose (Unraid nu…) où compose tourne dans docker:cli.
write_compose_wrapper() {
    local file="${STACK_DIR}/compose.sh" run
    # shellcheck disable=SC2016 # $DIR et $@ doivent rester littéraux : ils sont pour compose.sh
    case "$COMPOSE_MODE" in
        plugin)     run='docker compose "$@"' ;;
        standalone) run='docker-compose "$@"' ;;
        *)          run='docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$DIR:$DIR" -w "$DIR" docker:cli compose "$@"' ;;
    esac
    write_file "$file" 755 <<EOF
#!/usr/bin/env bash
# Généré par install.sh — gestion de la stack ArrMada (mode compose : ${COMPOSE_MODE:-plugin}).
#   ./compose.sh ps            état des conteneurs
#   ./compose.sh logs -f sonarr
#   ./compose.sh pull && ./compose.sh up -d     mise à jour
set -euo pipefail
DIR="\$(cd "\$(dirname "\$0")" && pwd)"
cd "\$DIR"
exec ${run}
EOF
}

write_credentials() {
    local file="${STACK_DIR}/credentials.txt"
    # Relance : l'assistant Jellyfin n'est pas rejoué, on garde son mot de passe.
    if [ -z "$JELLYFIN_PASSWORD" ] && [ -f "$(fs "$file")" ]; then
        JELLYFIN_PASSWORD="$(sed -n 's|^Jellyfin  *admin / ||p' "$(fs "$file")")"
    fi
    {
        echo "# ArrMada — accès générés par install.sh le $(date '+%Y-%m-%d %H:%M')"
        echo "# Fichier lisible par son propriétaire uniquement. Change ces mots de passe si tu veux."
        echo
        local app
        for app in "${APPS[@]}" "${EXISTING[@]+"${EXISTING[@]}"}"; do
            printf '%-12s http://%s:%s\n' "$(app_label "$app")" "$HOST_IP" "$(app_port "$app")"
        done
        echo
        [ -n "$DELUGE_PASSWORD" ] && echo "Deluge       mot de passe web : ${DELUGE_PASSWORD}"
        [ -n "$QBIT_PASSWORD" ] && echo "qBittorrent  admin / ${QBIT_PASSWORD}"
        [ -n "$JELLYFIN_PASSWORD" ] && echo "Jellyfin     admin / ${JELLYFIN_PASSWORD}"
        echo
        echo "Clés API : lues automatiquement par ArrMada (Paramètres → Auto-configuration)."
    } | write_file "$file" 600
}

#-------------------------------------------------------------------------------
# Démarrage
#-------------------------------------------------------------------------------
# http_ok <port> → 0 si un VRAI serveur HTTP répond. Un simple test TCP ne
# suffit pas : docker-proxy accepte la connexion sur un port publié avant
# même que l'appli ait fini de démarrer dans son conteneur.
http_ok() {
    (
        exec 3<>"/dev/tcp/127.0.0.1/$1" || exit 1
        printf 'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n' >&3
        IFS= read -r -t 5 line <&3 || exit 1
        [[ "$line" == HTTP/* ]]
    ) 2>/dev/null
}

wait_http() {   # wait_http <port> <secondes>
    local deadline=$(( $(date +%s) + $2 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if http_ok "$1"; then return 0; fi
        sleep 3
    done
    return 1
}

start_stack() {
    title "Démarrage"
    log "Téléchargement des images (premier lancement : quelques minutes)…"
    # Hors ligne / registre injoignable : on tente quand même avec les images locales.
    compose pull --quiet || warn "Téléchargement incomplet : utilisation des images déjà présentes"
    compose up -d --remove-orphans || die "Échec du démarrage (voir : cd ${STACK_DIR} && docker compose logs)" "$E_START"
    local app port failed=()
    for app in "${APPS[@]}"; do
        port="$(app_port "$app")"
        if wait_http "$port" 180; then ok "$(app_label "$app") répond sur :${port}"; else failed+=("$app"); fi
    done
    if [ ${#failed[@]} -gt 0 ]; then
        warn "Pas encore de réponse : ${failed[*]} (docker logs <nom> pour voir où ça en est)"
    fi
}

#-------------------------------------------------------------------------------
# Jellyfin : assistant de 1er démarrage piloté par son API
#   compte admin (mot de passe généré) + bibliothèques Films/Séries + clé API
#   « ArrMada » (lue ensuite par ArrMada dans jellyfin.db).
#-------------------------------------------------------------------------------
jf() {   # jf <méthode> <chemin> [corps JSON] [jeton] → corps de la réponse
    local auth='MediaBrowser Client="ArrMada", Device="install.sh", DeviceId="arrmada-installer", Version="'"${SCRIPT_VERSION}"'"'
    [ -n "${4:-}" ] && auth="${auth}, Token=\"$4\""
    curl -fsS -X "$1" "http://127.0.0.1:${PORT_JELLYFIN}$2" \
        -H "Content-Type: application/json" -H "Authorization: ${auth}" \
        ${3:+-d "$3"}
}

setup_jellyfin() {
    has_app jellyfin || return 0
    if ! command -v curl >/dev/null 2>&1; then
        warn "curl absent : termine l'assistant Jellyfin à la main (http://${HOST_IP}:${PORT_JELLYFIN})"
        return 0
    fi
    local info="" deadline=$(( $(date +%s) + 120 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        info="$(jf GET /System/Info/Public 2>/dev/null || true)"
        [[ "$info" == *StartupWizardCompleted* ]] && break
        sleep 3
    done
    if [[ "$info" != *'"StartupWizardCompleted":false'* ]]; then
        ok "Jellyfin : déjà configuré (assistant terminé), rien à faire"
        return 0
    fi
    local lang=en country=US
    case "${LANG:-}" in fr*) lang=fr country=FR ;; esac
    JELLYFIN_PASSWORD="$(gen_password)"
    if ! {
        jf POST /Startup/Configuration "{\"UICulture\":\"${lang}\",\"MetadataCountryCode\":\"${country}\",\"PreferredMetadataLanguage\":\"${lang}\"}" >/dev/null &&
        jf GET /Startup/User >/dev/null &&
        jf POST /Startup/User "{\"Name\":\"admin\",\"Password\":\"${JELLYFIN_PASSWORD}\"}" >/dev/null &&
        jf POST /Startup/RemoteAccess '{"EnableRemoteAccess":true,"EnableAutomaticPortMapping":false}' >/dev/null &&
        jf POST /Startup/Complete >/dev/null
    }; then
        JELLYFIN_PASSWORD=""
        warn "Assistant Jellyfin non automatisable ici : termine-le à la main (http://${HOST_IP}:${PORT_JELLYFIN})"
        return 0
    fi
    local token
    token="$(jf POST /Users/AuthenticateByName "{\"Username\":\"admin\",\"Pw\":\"${JELLYFIN_PASSWORD}\"}" | sed -n 's/.*"AccessToken":"\([^"]*\)".*/\1/p')"
    if [ -z "$token" ]; then
        warn "Jellyfin : compte créé mais connexion impossible — clé API à créer à la main"
        return 0
    fi
    jf POST "/Auth/Keys?app=ArrMada" "" "$token" >/dev/null || warn "Jellyfin : création de la clé API échouée"
    jf POST "/Library/VirtualFolders?name=Films&collectionType=movies&paths=/data/media/movies&refreshLibrary=false" '{"LibraryOptions":{}}' "$token" >/dev/null || true
    jf POST "/Library/VirtualFolders?name=S%C3%A9ries&collectionType=tvshows&paths=/data/media/tv&refreshLibrary=false" '{"LibraryOptions":{}}' "$token" >/dev/null || true
    ok "Jellyfin : compte admin, bibliothèques Films/Séries et clé API ArrMada créés"
}

summary() {
    title "Terminé"
    cat <<EOF
  ${C_BOLD}1.${C_RESET} Ouvre ${C_GREEN}http://${HOST_IP}:${PORT_ARRMADA}${C_RESET}
     → crée ton mot de passe → étape Découverte → « Import automatique » → ${C_BOLD}Appliquer${C_RESET}
     (indexeurs Prowlarr, clients de téléchargement, Bazarr, dossiers médias : tout est câblé)
  ${C_BOLD}2.${C_RESET} À faire dans les applis (impossible à deviner) :
EOF
    has_app prowlarr && echo "     • Prowlarr  http://${HOST_IP}:${PORT_PROWLARR}  : ajoute tes indexeurs (ils seront poussés partout)"
    has_app sabnzbd && echo "     • SABnzbd   http://${HOST_IP}:${PORT_SABNZBD}  : ajoute ton fournisseur Usenet"
    if has_app jellyfin && [ -z "$JELLYFIN_PASSWORD" ]; then
        echo "     • Jellyfin  http://${HOST_IP}:${PORT_JELLYFIN}  : assistant + bibliothèques /data/media/tv et /data/media/movies"
    fi
    has_app sonarr && echo "     • Sonarr/Radarr : au 1er accès, choisis la méthode d'authentification"
    cat <<EOF
  ${C_BOLD}3.${C_RESET} Accès et mots de passe générés : ${STACK_DIR}/credentials.txt
     Gestion : ${STACK_DIR}/compose.sh ps | logs -f <appli> | pull && …/compose.sh up -d
EOF
}

uninstall() {
    title "Désinstallation"
    detect_platform
    STACK_DIR="${OPT_CONFIG_ROOT:-$CONFIG_ROOT}/arrmada"
    [ -f "${STACK_DIR}/docker-compose.yml" ] || die "Aucune stack trouvée dans ${STACK_DIR} (--config-root ?)" "$E_CONFIG"
    check_deps
    local default=n
    $OPT_YES && default=o   # --yes vaut confirmation explicite
    if ! ask_yn "Arrêter et supprimer les conteneurs de ${STACK_DIR} ? (configs et médias conservés)" "$default"; then
        die "Annulé" "$E_GENERIC"
    fi
    compose down
    ok "Conteneurs supprimés. Configs (${CONFIG_ROOT}) et médias intacts : relance install.sh pour réinstaller."
}

#-------------------------------------------------------------------------------
# Principal
#-------------------------------------------------------------------------------
main() {
    parse_args "$@"
    printf '%s%s🏴‍☠️  ArrMada — installeur de stack média %s%s\n' "$C_BOLD" "$C_CYAN" "$SCRIPT_VERSION" "$C_RESET"

    if $OPT_UNINSTALL; then uninstall; exit 0; fi

    detect_platform
    if [ "$(id -u)" != "0" ] && [ "$PLATFORM" != "macos" ] && ! $OPT_DRY_RUN; then
        die "Lance le script avec sudo (création de dossiers et droits sur les fichiers)." "$E_PARAMS"
    fi

    if $OPT_DRY_RUN; then
        # Tout est écrit dans un dossier jetable : aucun effet sur la machine.
        ROOT_PREFIX="$(mktemp -d)"
        warn "Mode --dry-run : fichiers générés sous ${ROOT_PREFIX}, rien n'est démarré"
    else
        check_deps
    fi

    choose_paths
    choose_apps
    if $INTERACTIVE && ! ask_yn "Lancer l'installation ?" "o"; then die "Annulé" "$E_GENERIC"; fi

    $OPT_DRY_RUN || check_ports
    create_tree
    seed_configs
    write_compose
    write_credentials   # écrit dès maintenant : un arrêt en cours de démarrage garde les accès

    if $OPT_DRY_RUN; then
        title "Aperçu (dry-run)"
        cat "$(fs "${STACK_DIR}/docker-compose.yml")"
        exit 0
    fi
    start_stack
    setup_jellyfin
    write_credentials   # complété avec le compte Jellyfin
    write_stack_json    # idem : ArrMada l'affiche à l'admin dans son assistant
    summary
}

main "$@"

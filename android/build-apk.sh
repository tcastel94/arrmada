#!/bin/bash
#===============================================================================
# @name        : build-apk.sh
# @description : Compile l'APK Android d'ArrMada (téléphone, tablette, Android TV),
#                lance les tests, et peut l'installer directement sur un appareil.
# @author      : ArrMada
# @version     : 1.0.0
# @date        : 2026-10-18
# @usage       : ./build-apk.sh [--release|--debug] [--install <ip[:port]>]
#                ./build-apk.sh --init-keystore
#===============================================================================
#
# Prérequis :
#   - JDK 17 ou plus récent (java -version)
#   - SDK Android : variable ANDROID_HOME (ou ANDROID_SDK_ROOT), avec
#     « platforms;android-35 », « build-tools;35.0.0 » et « platform-tools » (adb)
#   - Pour --release : une clé de signature (voir --init-keystore)
#
# Variables d'environnement (jamais de mot de passe dans le dépôt) :
#   ARRMADA_KEYSTORE           Chemin de la clé (défaut : ~/.arrmada/arrmada-release.jks)
#   ARRMADA_KEYSTORE_PASSWORD  Mot de passe de la clé (demandé si absent et terminal interactif)
#   ARRMADA_KEY_ALIAS          Alias dans la clé (défaut : arrmada)
#   ARRMADA_KEY_PASSWORD       Mot de passe de l'alias (défaut : celui de la clé)
#
# Codes retour :
#   0 succès | 1 erreur générique | 2 configuration | 3 dépendance manquante
#   4 paramètres | 5 échec du build ou des tests | 6 échec de l'installation
#===============================================================================

set -euo pipefail

#===============================================================================
# CONFIGURATION
#===============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly DIST_DIR="${SCRIPT_DIR}/dist"
readonly DEFAULT_KEYSTORE="${HOME}/.arrmada/arrmada-release.jks"
readonly KEY_ALIAS_DEFAULT="arrmada"
readonly MIN_JAVA_MAJOR=17
readonly ADB_DEFAULT_PORT=5555

readonly E_GENERIC=1
readonly E_CONFIG=2
readonly E_DEPS=3
readonly E_ARGS=4
readonly E_BUILD=5
readonly E_INSTALL=6

BUILD_TYPE="release"
INSTALL_TARGET=""
INIT_KEYSTORE=false
APK_PATH=""

#===============================================================================
# FONCTIONS UTILITAIRES
#===============================================================================

log_info()  { printf '%s [INFO ] %s\n' "$(date '+%F %T')" "$*"; }
log_warn()  { printf '%s [WARN ] %s\n' "$(date '+%F %T')" "$*" >&2; }
log_error() { printf '%s [ERROR] %s\n' "$(date '+%F %T')" "$*" >&2; }

# die <message> [code] : erreur fatale
die() {
    log_error "$1"
    exit "${2:-$E_GENERIC}"
}

usage() {
    cat <<EOF
Usage: $0 [options]

Compile l'APK Android d'ArrMada et lance les tests unitaires.

Options:
    --release               APK signé avec la clé de release (défaut)
    --debug                 APK de test (clé de debug, s'installe À CÔTÉ de la version normale)
    --install <ip[:port]>   Installe l'APK sur l'appareil après le build (adb, port ${ADB_DEFAULT_PORT} par défaut)
    --init-keystore         Crée la clé de signature dans ${DEFAULT_KEYSTORE} puis s'arrête
    -h, --help              Affiche cette aide

Exemples:
    $0 --init-keystore                       # une seule fois, à conserver précieusement
    $0                                       # APK release dans dist/
    $0 --debug --install 192.168.1.50        # APK de test installé sur la Shield
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --release) BUILD_TYPE="release"; shift ;;
            --debug)   BUILD_TYPE="debug"; shift ;;
            --install)
                [[ $# -ge 2 && -n "$2" ]] || die "--install attend une adresse (ex. 192.168.1.50)" "$E_ARGS"
                INSTALL_TARGET="$2"
                shift 2
                ;;
            --init-keystore) INIT_KEYSTORE=true; shift ;;
            -h|--help) usage; exit 0 ;;
            *) usage >&2; die "Option inconnue : $1" "$E_ARGS" ;;
        esac
    done
}

#===============================================================================
# VÉRIFICATIONS
#===============================================================================

check_java() {
    command -v java >/dev/null 2>&1 || die "java introuvable : installe un JDK ${MIN_JAVA_MAJOR}+ (ex. dnf install java-17-openjdk-devel)" "$E_DEPS"
    local version major
    # « openjdk version "21.0.4" » → 21 ; « "1.8.0_402" » → 1 (donc trop ancien)
    # (awk lit tout sans « exit » : sinon java peut recevoir SIGPIPE et, avec
    # pipefail, faire échouer le script sans message)
    version="$(java -version 2>&1 | awk -F'"' '/version/ && !v {v = $2} END {print v}')"
    major="${version%%.*}"
    [[ "$major" =~ ^[0-9]+$ ]] || die "Version de java illisible : ${version:-?}" "$E_DEPS"
    (( major >= MIN_JAVA_MAJOR )) || die "Java ${version} trop ancien : ${MIN_JAVA_MAJOR} minimum" "$E_DEPS"
    log_info "Java ${version}"
}

check_sdk() {
    # Gradle accepte ANDROID_HOME, ANDROID_SDK_ROOT ou sdk.dir dans local.properties.
    if [[ -z "${ANDROID_HOME:-}" && -n "${ANDROID_SDK_ROOT:-}" ]]; then
        export ANDROID_HOME="$ANDROID_SDK_ROOT"
    fi
    if [[ -n "${ANDROID_HOME:-}" ]]; then
        [[ -d "$ANDROID_HOME" ]] || die "ANDROID_HOME pointe sur un dossier absent : $ANDROID_HOME" "$E_CONFIG"
        log_info "SDK Android : ${ANDROID_HOME}"
    elif grep -qs '^sdk.dir=' "${SCRIPT_DIR}/local.properties"; then
        log_info "SDK Android : $(grep '^sdk.dir=' "${SCRIPT_DIR}/local.properties" | cut -d= -f2-)"
    else
        die "SDK Android introuvable : définis ANDROID_HOME (voir android/README.md, « Compiler sur ta machine »)" "$E_DEPS"
    fi
}

# Prépare les variables de signature pour Gradle (app/build.gradle.kts les lit).
prepare_signing() {
    export ARRMADA_KEYSTORE="${ARRMADA_KEYSTORE:-$DEFAULT_KEYSTORE}"
    [[ -f "$ARRMADA_KEYSTORE" ]] || die "Clé de signature absente : ${ARRMADA_KEYSTORE}. Crée-la avec --init-keystore, ou compile un APK de test avec --debug" "$E_CONFIG"

    if [[ -z "${ARRMADA_KEYSTORE_PASSWORD:-}" ]]; then
        [[ -t 0 ]] || die "ARRMADA_KEYSTORE_PASSWORD non défini (mode non interactif)" "$E_CONFIG"
        read -r -s -p "Mot de passe de la clé de signature : " ARRMADA_KEYSTORE_PASSWORD
        echo
        export ARRMADA_KEYSTORE_PASSWORD
    fi
    export ARRMADA_KEY_ALIAS="${ARRMADA_KEY_ALIAS:-$KEY_ALIAS_DEFAULT}"
    log_info "Signature : ${ARRMADA_KEYSTORE} (alias ${ARRMADA_KEY_ALIAS})"
}

#===============================================================================
# ACTIONS
#===============================================================================

# Crée la clé de signature release (une seule fois dans la vie de l'appli).
init_keystore() {
    command -v keytool >/dev/null 2>&1 || die "keytool introuvable (fourni avec le JDK)" "$E_DEPS"
    local keystore="${ARRMADA_KEYSTORE:-$DEFAULT_KEYSTORE}"
    [[ ! -e "$keystore" ]] || die "La clé existe déjà : ${keystore}. Ne la remplace pas : les appareils refuseraient les mises à jour" "$E_CONFIG"

    local password="${ARRMADA_KEYSTORE_PASSWORD:-}"
    if [[ -z "$password" ]]; then
        local confirm
        read -r -s -p "Nouveau mot de passe de la clé (6 caractères min.) : " password; echo
        read -r -s -p "Confirmation : " confirm; echo
        [[ "$password" == "$confirm" ]] || die "Les deux mots de passe diffèrent" "$E_ARGS"
    fi
    (( ${#password} >= 6 )) || die "Mot de passe trop court (6 caractères minimum, exigence de keytool)" "$E_ARGS"

    mkdir -p "$(dirname "$keystore")"
    chmod 700 "$(dirname "$keystore")"
    # PKCS12 : format standard ; le mot de passe de l'alias est celui de la clé.
    keytool -genkeypair -noprompt \
        -keystore "$keystore" -storetype PKCS12 \
        -alias "$KEY_ALIAS_DEFAULT" -keyalg RSA -keysize 4096 -validity 10000 \
        -dname "CN=ArrMada, O=ArrMada" \
        -storepass "$password" -keypass "$password" >/dev/null
    chmod 600 "$keystore"

    log_info "Clé créée : ${keystore}"
    cat <<EOF

  ⚠️  SAUVEGARDE cette clé et son mot de passe (gestionnaire de mots de passe, NAS).
      Si elle est perdue, les appareils refuseront toute mise à jour de l'appli :
      il faudra la désinstaller partout (et perdre la connexion enregistrée).

  Pour que GitHub Actions signe aussi les APK, crée ces secrets dans le dépôt
  (Settings > Secrets and variables > Actions) :
      ARRMADA_KEYSTORE_BASE64    sortie de : base64 -w0 ${keystore}
      ARRMADA_KEYSTORE_PASSWORD  le mot de passe saisi
      ARRMADA_KEY_ALIAS          ${KEY_ALIAS_DEFAULT}

EOF
}

# Numéro de version interne : nombre de commits git (toujours croissant).
compute_version_code() {
    local count
    if count="$(git -C "$SCRIPT_DIR" rev-list --count HEAD 2>/dev/null)" && [[ "$count" =~ ^[0-9]+$ ]]; then
        if [[ "$(git -C "$SCRIPT_DIR" rev-parse --is-shallow-repository 2>/dev/null)" == "true" ]]; then
            log_warn "Clone git partiel : versionCode=${count} sous-évalué (en CI, utiliser fetch-depth: 0)"
        fi
        echo "$count"
    else
        log_warn "Pas de dépôt git : versionCode=1 (une mise à jour par-dessus une version plus récente sera refusée)"
        echo 1
    fi
}

build_apk() {
    local version_code task_suffix version_name
    version_code="$(compute_version_code)"
    task_suffix="$(tr '[:lower:]' '[:upper:]' <<< "${BUILD_TYPE:0:1}")${BUILD_TYPE:1}" # release → Release
    version_name="$(awk -F= '/^arrmada.versionName=/ {print $2}' "${SCRIPT_DIR}/gradle.properties")"

    log_info "Build ${BUILD_TYPE} : version ${version_name:-?} (${version_code})"
    # Tests unitaires puis APK, en une seule commande Gradle.
    if ! (cd "$SCRIPT_DIR" && ./gradlew --console=plain \
            "-Parrmada.versionCode=${version_code}" \
            "test${task_suffix}UnitTest" "assemble${task_suffix}"); then
        die "Échec du build ou des tests (voir les messages de Gradle ci-dessus)" "$E_BUILD"
    fi

    local source="${SCRIPT_DIR}/app/build/outputs/apk/${BUILD_TYPE}/app-${BUILD_TYPE}.apk"
    [[ -f "$source" ]] || die "APK introuvable après le build : ${source}" "$E_BUILD"

    mkdir -p "$DIST_DIR"
    APK_PATH="${DIST_DIR}/arrmada-${version_name:-dev}-${version_code}-${BUILD_TYPE}.apk"
    cp "$source" "$APK_PATH"
    (cd "$DIST_DIR" && sha256sum "$(basename "$APK_PATH")" > "$(basename "$APK_PATH").sha256")
    verify_signature "$APK_PATH"
    log_info "APK prêt : ${APK_PATH} ($(du -h "$APK_PATH" | cut -f1))"
}

# Vérifie la signature avec apksigner (fourni par les build-tools), si présent.
verify_signature() {
    local apk="$1" apksigner=""
    if [[ -n "${ANDROID_HOME:-}" && -d "${ANDROID_HOME}/build-tools" ]]; then
        apksigner="$(find "${ANDROID_HOME}/build-tools" -maxdepth 2 -name apksigner -type f 2>/dev/null | sort -V | tail -n 1)"
    fi
    if [[ -z "$apksigner" ]]; then
        log_warn "apksigner introuvable : signature non vérifiée"
        return 0
    fi
    "$apksigner" verify "$apk" || die "APK mal signé : ${apk}" "$E_BUILD"
    log_info "Signature vérifiée (apksigner)"
}

# Installe l'APK par le réseau (Shield, téléphone avec débogage sans fil).
install_apk() {
    local target="$INSTALL_TARGET"
    command -v adb >/dev/null 2>&1 || die "adb introuvable (paquet platform-tools du SDK, ou dnf install android-tools)" "$E_DEPS"
    [[ "$target" == *:* ]] || target="${target}:${ADB_DEFAULT_PORT}"

    log_info "Connexion adb à ${target} (accepte la demande sur l'écran de l'appareil la 1re fois)"
    adb connect "$target" >/dev/null || die "adb connect ${target} a échoué : débogage réseau activé sur l'appareil ?" "$E_INSTALL"

    local output
    # -r : remplace l'appli en gardant ses données (adresse du serveur, session)
    if ! output="$(adb -s "$target" install -r "$APK_PATH" 2>&1)"; then
        log_error "$output"
        if [[ "$output" == *INSTALL_FAILED_UPDATE_INCOMPATIBLE* ]]; then
            die "L'appli installée est signée par une autre clé : désinstalle-la (adb -s ${target} uninstall fr.arrmada.app) puis relance" "$E_INSTALL"
        fi
        if [[ "$output" == *INSTALL_FAILED_VERSION_DOWNGRADE* ]]; then
            die "Version plus ancienne que celle installée (versionCode) : désinstalle d'abord, ou compile depuis un clone complet" "$E_INSTALL"
        fi
        die "Installation refusée par l'appareil" "$E_INSTALL"
    fi
    log_info "Installé sur ${target}"
}

#===============================================================================
# MAIN
#===============================================================================

main() {
    parse_args "$@"

    if [[ "$INIT_KEYSTORE" == true ]]; then
        check_java
        init_keystore
        return 0
    fi

    log_info "=== ArrMada Android : build ${BUILD_TYPE} ==="
    check_java
    check_sdk
    if [[ "$BUILD_TYPE" == "release" ]]; then
        prepare_signing
    fi
    build_apk
    if [[ -n "$INSTALL_TARGET" ]]; then
        install_apk
    fi
    log_info "=== Terminé ==="
}

main "$@"

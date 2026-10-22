#!/usr/bin/env bash
# =============================================================================
# remux-avi-mkv.sh — Convertit les .avi d'un dossier en .mkv, SANS réencodage
# -----------------------------------------------------------------------------
# Pourquoi : le lecteur de l'appli ArrMada (Media3 / ExoPlayer) gère mal le
# conteneur AVI (index en fin de fichier, « packed B-frames » des XviD, MP3
# découpé) → ERROR_CODE_IO_UNSPECIFIED ou DECODING_FAILED sur la Shield.
# Le MKV, lui, est parfaitement géré. On change seulement « l'emballage » :
# image et son sont copiés bit à bit (-c copy), aucune perte, ~5 s par épisode.
#
# Où tourne ffmpeg : dans un conteneur jetable lancé depuis l'image de ton
# conteneur Jellyfin (jellyfin-ffmpeg y est déjà) : rien à installer sur
# l'Unraid, et aucune correspondance de chemins à gérer (le dossier traité
# est monté sur /work).
#
# Ce que fait le script, pour chaque .avi du dossier (et sous-dossiers) :
#   1. saute l'épisode si le .mkv existe déjà (relance sans risque) ;
#   2. remuxe vers « <nom>.mkv.part », puis renomme en .mkv une fois fini ;
#   3. vérifie que la durée du .mkv = durée du .avi (± 2 s), sinon l'efface ;
#   4. range l'.avi d'origine dans « .avi-originaux/ » du même dossier
#      (dossier caché : ni l'écran Vidéos ni les séries maison ne le
#      montrent → pas d'épisode en double). --garder : laisse l'.avi en place.
#
# ⚠️ Piège torrent : si ce dossier est celui où qBittorrent partage encore
#    (downloads/completed), déplacer l'.avi casse le partage. Dans ce cas :
#    --garder, ou traite plutôt la copie / le lien physique rangé ailleurs.
#
# Usage :
#   ./remux-avi-mkv.sh [--dry-run] [--garder] [--conteneur NOM] DOSSIER
#
# Exemples :
#   ./remux-avi-mkv.sh --dry-run "/mnt/user/medias/mangas/series/Naruto Shippuden Kai Intégrale VOSTFR"
#   ./remux-avi-mkv.sh "/mnt/user/medias/mangas/series/Naruto Shippuden Kai Intégrale VOSTFR"
#
# Retour arrière : les .avi sont dans « .avi-originaux/ » ; il suffit de les
# remettre à leur place et de supprimer les .mkv.
#
# Codes retour : 0 = tout est bon, 1 = au moins un fichier en échec,
#                2 = mauvais usage / prérequis manquant.
# =============================================================================

set -Eeuo pipefail

# ── Paramètres par défaut ─────────────────────────────────────────────────────
JELLYFIN_CONTAINER="binhex-jellyfin-1"         # conteneur dont on emprunte l'image
FFMPEG="/usr/lib/jellyfin-ffmpeg/ffmpeg"       # chemin dans l'image Jellyfin
FFPROBE="/usr/lib/jellyfin-ffmpeg/ffprobe"
ORIG_DIR_NAME=".avi-originaux"                 # caché pour ArrMada (commence par « . »)
DURATION_TOLERANCE=2                           # écart de durée accepté (secondes)
UNRAID_OWNER="99:100"                          # nobody:users, propriétaire habituel sur Unraid

DRY_RUN=0
KEEP_AVI=0
TARGET_DIR=""

# ── Journalisation ────────────────────────────────────────────────────────────
log()  { printf '%s [%s] %s\n' "$(date '+%F %T')" "$1" "$2"; }
info() { log "INFO" "$*"; }
warn() { log "WARN" "$*" >&2; }
err()  { log "ERREUR" "$*" >&2; }

usage() {
    sed -n '/^# Usage :/,/^# Retour arrière/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
    exit 2
}

# ── Lecture des options ───────────────────────────────────────────────────────
while (( $# > 0 )); do
    case "$1" in
        --dry-run)    DRY_RUN=1 ;;
        --garder)     KEEP_AVI=1 ;;
        --conteneur)  shift; JELLYFIN_CONTAINER="${1:-}" ;;
        -h|--help)    usage ;;
        -*)           err "Option inconnue : $1"; usage ;;
        *)            TARGET_DIR="$1" ;;
    esac
    shift
done

[[ -n "$TARGET_DIR" ]] || { err "Dossier à traiter manquant"; usage; }
[[ -d "$TARGET_DIR" ]] || { err "Dossier introuvable : $TARGET_DIR"; exit 2; }
TARGET_DIR="$(realpath "$TARGET_DIR")"

# ── Prérequis : docker et l'image du conteneur Jellyfin ───────────────────────
command -v docker >/dev/null || { err "docker introuvable"; exit 2; }
IMAGE="$(docker inspect --format '{{.Config.Image}}' "$JELLYFIN_CONTAINER" 2>/dev/null)" || {
    err "Conteneur « $JELLYFIN_CONTAINER » introuvable (option --conteneur NOM)"
    exit 2
}
info "ffmpeg emprunté à l'image : $IMAGE"

# Lance un outil de jellyfin-ffmpeg dans un conteneur jetable, le dossier
# traité monté sur /work. --entrypoint remplace le démarrage de Jellyfin.
run_tool() {
    local tool="$1"; shift
    docker run --rm --entrypoint "$tool" -v "$TARGET_DIR:/work" "$IMAGE" "$@"
}

# Durée (secondes, entière) d'un fichier, chemin relatif au dossier traité
duration_of() {
    run_tool "$FFPROBE" -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "/work/$1" 2>/dev/null | cut -d. -f1
}

# Codec de la première piste vidéo (« mpeg4 » = XviD / DivX)
video_codec_of() {
    run_tool "$FFPROBE" -v error -select_streams v:0 -show_entries stream=codec_name \
        -of default=noprint_wrappers=1:nokey=1 "/work/$1" 2>/dev/null | head -1
}

# ── Traitement d'un fichier (chemin relatif au dossier traité) ───────────────
remux_one() {
    local rel_avi="$1"
    local rel_mkv="${rel_avi%.*}.mkv"
    local abs_avi="$TARGET_DIR/$rel_avi"
    local abs_mkv="$TARGET_DIR/$rel_mkv"

    if [[ -e "$abs_mkv" ]]; then
        info "Déjà fait, ignoré : $rel_mkv"
        return 0
    fi

    # XviD / DivX : « packed B-frames » à déplier, sinon le MKV saccade
    local codec bsf=()
    codec="$(video_codec_of "$rel_avi")"
    [[ "$codec" == "mpeg4" ]] && bsf=(-bsf:v mpeg4_unpack_bframes)

    if (( DRY_RUN )); then
        info "[simulation] $rel_avi → $rel_mkv (vidéo : ${codec:-?}${bsf:+, packed B-frames dépliées})"
        return 0
    fi

    info "Remux : $rel_avi (vidéo : ${codec:-?})"
    # -fflags +genpts : l'AVI n'a pas d'horodatage par image, ffmpeg les recrée
    # -map 0 -c copy  : toutes les pistes, copiées sans réencodage
    # .part           : un fichier interrompu n'est jamais pris pour un épisode
    if ! run_tool "$FFMPEG" -nostdin -hide_banner -loglevel error -y \
            -fflags +genpts -i "/work/$rel_avi" \
            -map 0 -c copy "${bsf[@]}" \
            -f matroska "/work/$rel_mkv.part"; then
        err "Échec ffmpeg : $rel_avi"
        rm -f "$abs_mkv.part"
        return 1
    fi
    mv -f "$abs_mkv.part" "$abs_mkv"

    # Contrôle : même durée que l'original
    local d_avi d_mkv
    d_avi="$(duration_of "$rel_avi")"
    d_mkv="$(duration_of "$rel_mkv")"
    if [[ -z "$d_avi" || -z "$d_mkv" ]] || (( ${d_avi:-0} - ${d_mkv:-0} > DURATION_TOLERANCE || ${d_mkv:-0} - ${d_avi:-0} > DURATION_TOLERANCE )); then
        err "Durées différentes (avi ${d_avi:-?} s / mkv ${d_mkv:-?} s) : MKV supprimé, AVI conservé"
        rm -f "$abs_mkv"
        return 1
    fi

    # Le conteneur tourne en root : on rend le fichier au propriétaire Unraid
    chown "$UNRAID_OWNER" "$abs_mkv" 2>/dev/null || true
    chmod 666 "$abs_mkv" 2>/dev/null || true

    if (( KEEP_AVI )); then
        info "OK ($d_mkv s), AVI laissé en place : $rel_mkv"
    else
        local orig_dir
        orig_dir="$(dirname "$abs_avi")/$ORIG_DIR_NAME"
        mkdir -p "$orig_dir"
        chown "$UNRAID_OWNER" "$orig_dir" 2>/dev/null || true
        mv -n "$abs_avi" "$orig_dir/"
        info "OK ($d_mkv s), AVI rangé dans $ORIG_DIR_NAME/ : $rel_mkv"
    fi
}

# ── Boucle principale ─────────────────────────────────────────────────────────
total=0; failed=0
# -print0 / read -d '' : noms avec espaces, apostrophes, accents sans souci.
# Les .avi déjà rangés dans .avi-originaux/ ne sont pas retraités.
while IFS= read -r -d '' file; do
    rel="${file#"$TARGET_DIR"/}"
    total=$((total + 1))
    remux_one "$rel" || failed=$((failed + 1))
done < <(find "$TARGET_DIR" -type d -name "$ORIG_DIR_NAME" -prune -o \
              -type f -iname '*.avi' -print0 | sort -z)

if (( total == 0 )); then
    info "Aucun .avi dans $TARGET_DIR"
    exit 0
fi
info "Terminé : $total fichier(s), $failed échec(s)$( (( DRY_RUN )) && echo ' (simulation)')"
(( failed == 0 )) || exit 1

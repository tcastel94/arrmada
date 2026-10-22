#!/usr/bin/env bash
# =============================================================================
# remux-avi-mkv.sh — Rend les vieux .avi (XviD + MP3) lisibles par l'appli
# -----------------------------------------------------------------------------
# Pourquoi : le lecteur de l'appli ArrMada (Media3 / ExoPlayer) gère mal :
#   - le conteneur AVI (index en fin de fichier, « packed B-frames » des XviD)
#     → ERROR_CODE_IO_UNSPECIFIED ;
#   - le son MP3 de ces AVI, découpé en blocs qui ne tombent pas sur les
#     trames MP3 → DECODING_FAILED, ou vidéo SANS SON une fois en MKV.
# Kodi s'en sortait car ffmpeg recolle tout ; le décodeur d'Android, non.
#
# Remède :
#   - conteneur → MKV, image copiée bit à bit (aucune perte, aucun calcul) ;
#   - son MP3 / MP2 → AAC 192 kb/s (lu partout ; perte imperceptible pour ces
#     sources) ; tout autre son (AC3, AAC, DTS…) est copié tel quel.
#
# Où tourne ffmpeg : dans un conteneur jetable lancé depuis l'image de ton
# conteneur Jellyfin (jellyfin-ffmpeg y est déjà) : rien à installer sur
# l'Unraid. Le dossier traité est monté sur /work.
#
# Deux usages :
#   1. (défaut) chaque .avi du dossier → .mkv ; l'.avi est rangé dans
#      « .avi-originaux/ » (dossier caché : ni l'écran Vidéos ni les séries
#      maison ne le montrent → pas d'épisode en double). --garder : laisse
#      l'.avi en place.
#   2. --reparer-son : chaque .mkv dont le son est en MP3 / MP2 (fichiers déjà
#      remuxés par l'ancienne version de ce script, ou MKV d'origine) voit
#      son son converti en AAC. L'ancien .mkv est supprimé si son .avi
#      d'origine est dans .avi-originaux/, sinon rangé dans « .mkv-originaux/ ».
#
# Sécurités : fichier écrit en « .part » puis renommé ; durée du résultat
# comparée à l'original (± 2 s), sinon résultat supprimé et original gardé ;
# relance sans risque (ce qui est déjà fait est ignoré) ; Ctrl+C arrête
# proprement (fichier en cours supprimé, originaux intacts).
#
# Journal : les messages de ffmpeg (des centaines de « Header missing » sur
# ces MP3 abîmés : NORMAL, les trames cassées sont sautées) vont dans
# /tmp/remux-avi-mkv-<date>.log ; l'écran n'affiche qu'une ligne par épisode.
#
# ⚠️ Piège torrent : si le dossier est celui où le client torrent partage
#    encore (downloads/completed), déplacer l'original casse le partage :
#    --garder, ou traite la copie rangée ailleurs.
#
# Usage :
#   ./remux-avi-mkv.sh [--dry-run] [--garder] [--reparer-son] [--conteneur NOM] DOSSIER
#
# Exemples :
#   ./remux-avi-mkv.sh --dry-run "/mnt/user/medias/mangas/series/Naruto Shippuden Kai Intégrale VOSTFR"
#   ./remux-avi-mkv.sh "/mnt/user/medias/mangas/series/Naruto Shippuden Kai Intégrale VOSTFR"
#   ./remux-avi-mkv.sh --reparer-son "/mnt/user/medias/mangas/series/Naruto Shippuden Kai Intégrale VOSTFR"
#
# Retour arrière : les originaux sont dans « .avi-originaux/ » ou
# « .mkv-originaux/ » ; il suffit de les remettre à leur place.
#
# Codes retour : 0 = tout est bon, 1 = au moins un fichier en échec,
#                2 = mauvais usage / prérequis manquant.
# =============================================================================

set -Eeuo pipefail

# ── Paramètres par défaut ─────────────────────────────────────────────────────
JELLYFIN_CONTAINER="binhex-jellyfin-1"         # conteneur dont on emprunte l'image
FFMPEG="/usr/lib/jellyfin-ffmpeg/ffmpeg"       # chemin dans l'image Jellyfin
FFPROBE="/usr/lib/jellyfin-ffmpeg/ffprobe"
AVI_ORIG=".avi-originaux"                      # cachés pour ArrMada (commencent par « . »)
MKV_ORIG=".mkv-originaux"
DURATION_TOLERANCE=2                           # écart de durée accepté (secondes)
AAC_BITRATE="192k"                             # débit du son AAC (stéréo)
UNRAID_OWNER="99:100"                          # nobody:users, propriétaire habituel sur Unraid

LOG_FILE="/tmp/remux-avi-mkv-$(date '+%Y%m%d-%H%M%S').log"
CURRENT_PART=""                                # fichier en cours d'écriture (Ctrl+C)

DRY_RUN=0
KEEP_ORIG=0
FIX_AUDIO=0
TARGET_DIR=""

# ── Journalisation ────────────────────────────────────────────────────────────
log()  { printf '%s [%s] %s\n' "$(date '+%F %T')" "$1" "$2"; }
info() { log "INFO" "$*"; }
err()  { log "ERREUR" "$*" >&2; }

usage() {
    sed -n '/^# Usage :/,/^# Retour arrière/p' "$0" | sed 's/^# \{0,1\}//' | head -n -1
    exit 2
}

# ── Lecture des options ───────────────────────────────────────────────────────
while (( $# > 0 )); do
    case "$1" in
        --dry-run)      DRY_RUN=1 ;;
        --garder)       KEEP_ORIG=1 ;;
        --reparer-son)  FIX_AUDIO=1 ;;
        --conteneur)    shift; JELLYFIN_CONTAINER="${1:-}" ;;
        -h|--help)      usage ;;
        -*)             err "Option inconnue : $1"; usage ;;
        *)              TARGET_DIR="$1" ;;
    esac
    shift
done

# Un seul lancement à la fois : deux scripts sur les mêmes fichiers
# écriraient le même « .part » en même temps et l'abîmeraient
exec 9>/tmp/remux-avi-mkv.lock
flock -n 9 || { err "Le script tourne déjà (autre terminal ?) : attends la fin"; exit 2; }

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
info "Journal détaillé de ffmpeg : $LOG_FILE"

# Ctrl+C / arrêt : on supprime le fichier à moitié écrit et on s'arrête là
# (docker transmet le signal à ffmpeg, le conteneur jetable disparaît)
on_interrupt() {
    [[ -n "$CURRENT_PART" ]] && rm -f "$TARGET_DIR/$CURRENT_PART"
    err "Interrompu : originaux intacts, relance le script pour reprendre"
    exit 130
}
trap on_interrupt INT TERM

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

# Codec de la première piste d'un type (v = vidéo, a = son) : « mpeg4 », « mp3 »…
codec_of() {
    run_tool "$FFPROBE" -v error -select_streams "$2:0" -show_entries stream=codec_name \
        -of default=noprint_wrappers=1:nokey=1 "/work/$1" 2>/dev/null | head -1
}

# Son à convertir en AAC ? (MP3 / MP2 : le décodeur d'Android s'y casse les dents)
needs_aac() { [[ "$1" == "mp3" || "$1" == "mp2" ]]; }

# Durées comparables à DURATION_TOLERANCE près ?
same_duration() {
    local a="$1" b="$2"
    [[ -n "$a" && -n "$b" ]] && (( a - b <= DURATION_TOLERANCE && b - a <= DURATION_TOLERANCE ))
}

# Rend un fichier au propriétaire Unraid (le conteneur tourne en root)
give_back() {
    chown "$UNRAID_OWNER" "$1" 2>/dev/null || true
    chmod 666 "$1" 2>/dev/null || true
}

# Range un original dans un dossier caché à côté de lui
stash() {
    local file="$1" dir_name="$2" dir
    dir="$(dirname "$file")/$dir_name"
    mkdir -p "$dir"
    chown "$UNRAID_OWNER" "$dir" 2>/dev/null || true
    mv -n "$file" "$dir/"
}

# Écrit <sortie>.part avec ffmpeg, contrôle la durée, puis renomme.
#   $1 = entrée (relative), $2 = sortie (relative), $3… = options d'encodage
# Retour 0 si la sortie est en place et valide.
transcode() {
    local rel_in="$1" rel_out="$2"; shift 2
    local started=$SECONDS before after
    CURRENT_PART="$rel_out.part"
    printf '\n===== %s =====\n' "$rel_in" >> "$LOG_FILE"
    before=$(wc -l < "$LOG_FILE")
    # -fflags +genpts : l'AVI n'a pas d'horodatage par image, ffmpeg les recrée
    # -map 0          : toutes les pistes (vidéo, son, sous-titres)
    if ! run_tool "$FFMPEG" -nostdin -hide_banner -loglevel error -y \
            -fflags +genpts -i "/work/$rel_in" -map 0 "$@" \
            -f matroska "/work/$rel_out.part" 2>> "$LOG_FILE"; then
        err "Échec ffmpeg : $rel_in (fin du journal ci-dessous)"
        tail -n 5 "$LOG_FILE" >&2
        rm -f "$TARGET_DIR/$rel_out.part"
        CURRENT_PART=""
        return 1
    fi
    after=$(wc -l < "$LOG_FILE")
    # Trames abîmées sautées par ffmpeg : information, pas une erreur
    (( after - before > 0 )) && info "  $((after - before)) avertissement(s) ffmpeg (trames abîmées sautées, normal), détail dans le journal"
    info "  calcul terminé en $((SECONDS - started)) s, contrôle de la durée…"
    local d_in d_out
    d_in="$(duration_of "$rel_in")"
    d_out="$(duration_of "$rel_out.part")"
    if ! same_duration "$d_in" "$d_out"; then
        err "Durées différentes (original ${d_in:-?} s / résultat ${d_out:-?} s) : fichier abîmé ? Résultat supprimé, original gardé : $rel_in"
        rm -f "$TARGET_DIR/$rel_out.part"
        CURRENT_PART=""
        return 1
    fi
    mv -f "$TARGET_DIR/$rel_out.part" "$TARGET_DIR/$rel_out"
    CURRENT_PART=""
    give_back "$TARGET_DIR/$rel_out"
    LAST_DURATION="$d_out"
}

# Options d'encodage : image copiée (XviD : B-frames dépliées), son AAC si MP3
encode_options() {
    local vcodec="$1" acodec="$2"
    local -a opts=(-c copy)
    [[ "$vcodec" == "mpeg4" ]] && opts+=(-bsf:v mpeg4_unpack_bframes)
    # aresample=async=1 : comble les trous laissés par les trames MP3 abîmées
    # (sinon le son se décale peu à peu de l'image)
    needs_aac "$acodec" && opts+=(-c:a aac -b:a "$AAC_BITRATE" -af aresample=async=1)
    printf '%s\0' "${opts[@]}"
}

# ── Usage 1 : .avi → .mkv ─────────────────────────────────────────────────────
convert_avi() {
    local rel_avi="$1"
    local rel_mkv="${rel_avi%.*}.mkv"
    if [[ -e "$TARGET_DIR/$rel_mkv" ]]; then
        info "Déjà fait, ignoré : $rel_mkv"
        return 0
    fi
    local vcodec acodec
    vcodec="$(codec_of "$rel_avi" v)"
    acodec="$(codec_of "$rel_avi" a)"
    local what="image ${vcodec:-?} copiée, son ${acodec:-?}"
    if needs_aac "$acodec"; then what+=" → AAC"; else what+=" copié"; fi
    if (( DRY_RUN )); then
        info "[simulation] $rel_avi → $rel_mkv ($what)"
        return 0
    fi
    info "Remux : $rel_avi ($what)"
    local -a opts
    mapfile -d '' -t opts < <(encode_options "$vcodec" "$acodec")
    transcode "$rel_avi" "$rel_mkv" "${opts[@]}" || return 1
    if (( KEEP_ORIG )); then
        info "OK (${LAST_DURATION} s), AVI laissé en place : $rel_mkv"
    else
        stash "$TARGET_DIR/$rel_avi" "$AVI_ORIG"
        info "OK (${LAST_DURATION} s), AVI rangé dans $AVI_ORIG/ : $rel_mkv"
    fi
}

# ── Usage 2 : .mkv au son MP3 → son AAC ──────────────────────────────────────
fix_mkv_audio() {
    local rel_mkv="$1"
    local vcodec acodec
    acodec="$(codec_of "$rel_mkv" a)"
    if ! needs_aac "$acodec"; then
        info "Son ${acodec:-absent} : rien à faire : $rel_mkv"
        return 0
    fi
    vcodec="$(codec_of "$rel_mkv" v)"
    if (( DRY_RUN )); then
        info "[simulation] son $acodec → AAC : $rel_mkv"
        return 0
    fi
    info "Son $acodec → AAC : $rel_mkv (1 à 3 min par épisode)"
    local tmp="${rel_mkv%.*}.aac-tmp.mkv"
    local -a opts
    mapfile -d '' -t opts < <(encode_options "$vcodec" "$acodec")
    transcode "$rel_mkv" "$tmp" "${opts[@]}" || return 1

    # L'ancien .mkv : inutile si l'.avi d'origine est déjà de côté
    local base avi_kept
    base="$(basename "${rel_mkv%.*}")"
    avi_kept="$TARGET_DIR/$(dirname "$rel_mkv")/$AVI_ORIG/$base.avi"
    if [[ -e "$avi_kept" ]]; then
        rm -f "$TARGET_DIR/$rel_mkv"
    elif (( KEEP_ORIG )); then
        mv -f "$TARGET_DIR/$rel_mkv" "$TARGET_DIR/${rel_mkv%.*}.mp3-original.mkv.bak"
    else
        stash "$TARGET_DIR/$rel_mkv" "$MKV_ORIG"
    fi
    mv -f "$TARGET_DIR/$tmp" "$TARGET_DIR/$rel_mkv"
    info "OK (${LAST_DURATION} s) : $rel_mkv"
}

# ── Boucle principale ─────────────────────────────────────────────────────────
total=0; failed=0; LAST_DURATION=""
if (( FIX_AUDIO )); then
    pattern='*.mkv'; action=fix_mkv_audio
else
    pattern='*.avi'; action=convert_avi
fi
# -print0 / read -d '' : noms avec espaces, apostrophes, accents sans souci.
# Les originaux rangés et les fichiers temporaires ne sont jamais retraités.
while IFS= read -r -d '' file; do
    rel="${file#"$TARGET_DIR"/}"
    total=$((total + 1))
    "$action" "$rel" || failed=$((failed + 1))
done < <(find "$TARGET_DIR" -type d \( -name "$AVI_ORIG" -o -name "$MKV_ORIG" \) -prune -o \
              -type f -iname "$pattern" ! -name '*.aac-tmp.mkv' -print0 | sort -z)

if (( total == 0 )); then
    info "Aucun fichier ${pattern#\*} dans $TARGET_DIR"
    exit 0
fi
info "Terminé : $total fichier(s), $failed échec(s)$( (( DRY_RUN )) && echo ' (simulation)')"
(( DRY_RUN )) || info "Journal : $LOG_FILE"
(( failed == 0 )) || exit 1

#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Banc de test des écrans Kodi d'ArrMada : un vrai Kodi sous écran virtuel.
#
# Ce que fait le script :
#   1. lance un FAUX backend ArrMada (mock_server.py : données + affiches) ;
#   2. lance Kodi sous Xvfb (écran virtuel 1920×1080, sans carte graphique),
#      avec un profil jetable, l'add-on du dépôt et un add-on « harnais » qui
#      pilote la télécommande et prend des captures ;
#   3. donne au skin Estuary les noms et tailles de polices d'Aeon Nox SiLVO
#      10.0.4 (copie locale du skin dans le profil, rien n'est modifié dans le
#      Kodi du système) pour un rendu proche de celui de la Shield.
#
# Prérequis (Ubuntu/Debian) :
#   sudo apt install kodi xvfb python3-pil curl
#
# Usage :
#   kodi-addon/bench/run.sh            # captures dans $BENCH_DIR/shots
#   RECORD=1 kodi-addon/bench/run.sh   # + vidéo $BENCH_DIR/demo.mp4 (ffmpeg requis)
#   BENCH_DIR=/tmp/bench kodi-addon/bench/run.sh
#
# Variables : RECORD=1 (vidéo), RES=1280x720 (taille de l'écran virtuel en
# mode vidéo : plus petit = plus fluide en rendu logiciel), PACE=1.5 (ralentit
# le parcours du harnais pour mieux voir les animations).
#
# Sortie : $BENCH_DIR/shots/*.png + extrait de kodi.log ([ArrMada] / [HARNESS]).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
ulimit -c 0  # pas de vidage mémoire (« core ») quand timeout coupe Kodi

BENCH_SRC="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$BENCH_SRC/../.." && pwd)"
BENCH_DIR="${BENCH_DIR:-/tmp/arrmada-kodi-bench}"
SILVO_RAW="https://raw.githubusercontent.com/MikeSiLVO/skin.aeon.nox.silvo/omega"

# L'add-on remplace « localhost » / « 127.0.0.1 » par l'IP du serveur de prod :
# le faux backend doit donc être joint par une vraie IP de la machine.
MOCK_IP="${MOCK_IP:-$(hostname -I | awk '{print $1}')}"
export MOCK_URL="http://${MOCK_IP}:8420"
export SHOT_DIR="$BENCH_DIR/shots"
export HOME="$BENCH_DIR/home"          # profil Kodi jetable (~/.kodi)
export KODI_AE_SINK=NULL               # pas de carte son
export PACE="${PACE:-1}"               # lu par le harnais (multiplie les pauses)
RECORD="${RECORD:-0}"
RES="${RES:-1280x720}"
KODI_DIR="$HOME/.kodi"
ESTUARY_SYS=/usr/share/kodi/addons/skin.estuary

for cmd in kodi xvfb-run python3 curl; do
  command -v "$cmd" >/dev/null || { echo "Manquant : $cmd (voir Prérequis)" >&2; exit 1; }
done
if [[ "$RECORD" == "1" ]]; then
  command -v ffmpeg >/dev/null || { echo "Manquant : ffmpeg (sudo apt install ffmpeg)" >&2; exit 1; }
fi

mkdir -p "$BENCH_DIR/assets" "$SHOT_DIR" "$KODI_DIR/addons" "$KODI_DIR/media/Fonts" \
         "$KODI_DIR/userdata/addon_data/script.arrmada"
cd "$BENCH_DIR"
rm -f "$SHOT_DIR"/*.png
# Chaque passage repart sans cache ni miniatures (on teste aussi le 1er affichage).
rm -rf "$KODI_DIR/userdata/addon_data/script.arrmada/cache" \
       "$KODI_DIR/userdata/Thumbnails" "$KODI_DIR/userdata/Database/Textures13.db"

# ── 1. Polices de SiLVO (téléchargées une fois) ──────────────────────────────
[[ -s assets/Font.xml ]] || curl -fsS -o assets/Font.xml "$SILVO_RAW/16x9/Font.xml"
[[ -s assets/RobotoCondensed-Regular.ttf ]] || \
  curl -fsS -o assets/RobotoCondensed-Regular.ttf "$SILVO_RAW/fonts/RobotoCondensed-Regular.ttf"
cp assets/RobotoCondensed-Regular.ttf "$KODI_DIR/media/Fonts/"

# Copie d'Estuary dans le profil (prioritaire sur celle du système), puis on
# remplace ses polices homonymes par celles de SiLVO et on ajoute les autres.
rm -rf "$KODI_DIR/addons/skin.estuary"
cp -r "$ESTUARY_SYS" "$KODI_DIR/addons/skin.estuary"
python3 - "$ESTUARY_SYS/xml/Font.xml" "$KODI_DIR/addons/skin.estuary/xml/Font.xml" assets/Font.xml <<'PY'
import sys
import xml.etree.ElementTree as ET

src, dst, silvo = sys.argv[1:]
estuary = ET.parse(src)
silvo_default = ET.parse(silvo).getroot().findall("fontset")[0]
names = {f.findtext("name") for f in silvo_default.findall("font")}
for fontset in estuary.getroot().findall("fontset"):
    for font in list(fontset.findall("font")):
        if font.findtext("name") in names:
            fontset.remove(font)
    for font in silvo_default.findall("font"):
        fontset.append(font)
estuary.write(dst, encoding="utf-8", xml_declaration=True)
PY

# ── 2. Add-ons : version de travail du dépôt + harnais ───────────────────────
rm -rf "$KODI_DIR/addons/script.arrmada" "$KODI_DIR/addons/service.arrmada.harness"
cp -r "$REPO/kodi-addon/script.arrmada" "$KODI_DIR/addons/"
cp -r "$BENCH_SRC/harness/service.arrmada.harness" "$KODI_DIR/addons/"
cat > "$KODI_DIR/userdata/addon_data/script.arrmada/settings.xml" <<EOF
<settings version="2">
    <setting id="server_url">$MOCK_URL</setting>
    <setting id="api_key">banc-de-test</setting>
    <setting id="enable_notifications">false</setting>
    <setting id="enable_scrobble">false</setting>
</settings>
EOF

# ── 3. Faux backend ──────────────────────────────────────────────────────────
python3 "$BENCH_SRC/mock_server.py" --base-url "$MOCK_URL" \
  --font assets/RobotoCondensed-Regular.ttf --images "$BENCH_DIR/img" > mock.log 2>&1 &
MOCK_PID=$!
trap 'kill "$MOCK_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do curl -fsS -o /dev/null "$MOCK_URL/api/kodi/addon-status" && break; sleep 0.5; done

# ── 4. Activation des add-ons copiés à la main (Kodi les désactive par défaut)
DB="$KODI_DIR/userdata/Database/Addons33.db"
if [[ ! -f "$DB" ]]; then
  echo "== Premier lancement : création de la base des add-ons"
  timeout 40 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone -fs > kodi-first.log 2>&1 || true
fi
python3 - "$DB" <<'PY'
import sqlite3
import sys

with sqlite3.connect(sys.argv[1]) as db:
    db.execute(
        "UPDATE installed SET enabled=1 "
        "WHERE addonID IN ('script.arrmada', 'service.arrmada.harness')"
    )
PY

# ── 5. Passage instrumenté (le harnais quitte Kodi à la fin) ─────────────────
if [[ "$RECORD" != "1" ]]; then
  echo "== Kodi + harnais (≈ 90 s)"
  timeout 240 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone -fs > kodi.log 2>&1 || true
else
  # Mode vidéo : on lance l'écran virtuel nous-mêmes pour pouvoir le filmer.
  echo "== Kodi + harnais, enregistrement vidéo ($RES)"
  DISP=":97"
  Xvfb "$DISP" -screen 0 "${RES}x24" -nolisten tcp > xvfb.log 2>&1 &
  XVFB_PID=$!
  sleep 1
  DISPLAY="$DISP" kodi --standalone -fs > kodi.log 2>&1 &
  KODI_PID=$!
  ffmpeg -loglevel error -y -f x11grab -framerate 30 -video_size "$RES" -i "$DISP" \
    -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p demo-raw.mp4 &
  FFMPEG_PID=$!
  timeout 300 tail --pid="$KODI_PID" -f /dev/null || kill "$KODI_PID" 2>/dev/null || true
  kill -INT "$FFMPEG_PID" 2>/dev/null || true
  wait "$FFMPEG_PID" 2>/dev/null || true
  kill "$XVFB_PID" 2>/dev/null || true
  # Recompression compacte (lecture web / téléphone) : ~1 Mo par 10 s.
  ffmpeg -loglevel error -y -i demo-raw.mp4 -c:v libx264 -preset slow -crf 24 \
    -pix_fmt yuv420p -movflags +faststart demo.mp4 && rm -f demo-raw.mp4
  echo "== Vidéo : $BENCH_DIR/demo.mp4"
fi

echo "== Journal"
grep -E "\[ArrMada\] Accueil|\[HARNESS\]|Traceback" "$KODI_DIR/temp/kodi.log" || true
echo "== Captures : $SHOT_DIR"
ls -1 "$SHOT_DIR"

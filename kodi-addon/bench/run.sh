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
#   sudo apt install kodi-pvr-iptvsimple   # TV en direct de test (phase 4.3)
#
# Usage :
#   kodi-addon/bench/run.sh            # captures dans $BENCH_DIR/shots
#   RECORD=1 kodi-addon/bench/run.sh   # + vidéo $BENCH_DIR/demo.mp4 (ffmpeg requis)
#   BENCH_DIR=/tmp/bench kodi-addon/bench/run.sh
#
# BENCH_ONLY=download : seulement la feuille « Télécharger » (ADR-005), ~1 min.
# BENCH_ONLY=board    : seulement l'écran Téléchargements (ADR-005, lot 3), ~1 min.
# BENCH_ONLY=ready    : seulement la pop-up « Prêt à regarder » (lot 4), ~1 min.
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
# Chaque passage repart sans cache, sans miniatures et NON appairé (on teste
# aussi le 1er affichage et le passage du mot de passe admin au jeton).
rm -rf "$KODI_DIR/userdata/addon_data/script.arrmada/cache" \
       "$KODI_DIR/userdata/addon_data/script.arrmada/device.json" \
       "$KODI_DIR/userdata/addon_data/script.arrmada/service-state.json" \
       "$KODI_DIR/userdata/Thumbnails" "$KODI_DIR/userdata/Database/Textures13.db"

# ── 1. Polices de SiLVO (téléchargées une fois) ──────────────────────────────
[[ -s assets/Font.xml ]] || curl -fsS -o assets/Font.xml "$SILVO_RAW/16x9/Font.xml"
[[ -s assets/RobotoCondensed-Regular.ttf ]] || \
  curl -fsS -o assets/RobotoCondensed-Regular.ttf "$SILVO_RAW/fonts/RobotoCondensed-Regular.ttf"
cp assets/RobotoCondensed-Regular.ttf "$KODI_DIR/media/Fonts/"

# Petite vidéo de test (mire) pour l'écran Salon « Lecture en cours ».
# SANS piste son : Xvfb n'a pas de carte son, Kodi chercherait une sortie
# audio pendant ~10 s avec sa fenêtre « occupé » ouverte, et refuserait
# d'ouvrir toute autre fenêtre pendant ce temps (dont l'écran Salon).
if command -v ffmpeg >/dev/null && [[ ! -s assets/demo-video-muette.mp4 ]]; then
  ffmpeg -loglevel error -y -f lavfi -i testsrc2=size=1280x720:rate=25 \
    -t 40 -an -c:v libx264 -pix_fmt yuv420p assets/demo-video-muette.mp4 || true
fi
export DEMO_VIDEO="$BENCH_DIR/assets/demo-video-muette.mp4"

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

# ── 1b. Médiathèque Kodi de test (ADR-004, phase 4.1) ────────────────────────
# Une série et un film avec fiches .nfo (make_media.py), déclarés comme sources
# vidéo ; leur contenu est réglé dans la base de Kodi à l'étape 4.
MEDIA="$BENCH_DIR/media"
if command -v ffmpeg >/dev/null && [[ ! -s assets/clip-90s.mp4 ]]; then
  ffmpeg -loglevel error -y -f lavfi -i testsrc2=size=640x360:rate=25 -t 90 -an \
    -c:v libx264 -preset ultrafast -pix_fmt yuv420p assets/clip-90s.mp4 || true
fi
python3 "$BENCH_SRC/make_media.py" "$MEDIA" assets/clip-90s.mp4
# 1.17 : S02E04 devient un épisode « réel » en MKV : piste audio anglaise,
# aucun sous-titre, chapitres nommés (Previously on, Opening, Episode, End
# Credits) → bouton « Passer l'intro », encart dès le générique, sous-titres
# FR auto. MKV car l'add-on lit les chapitres dans le fichier (Kodi 20 ne met
# pas à jour le chapitre en cours pendant la lecture).
INTRO="$BENCH_DIR/assets/intro-120s.mkv"
if command -v ffmpeg >/dev/null && [[ ! -s "$INTRO" ]]; then
  cat > assets/intro-chapters.txt <<'EOF'
;FFMETADATA1
[CHAPTER]
TIMEBASE=1/1000
START=0
END=10000
title=Previously on
[CHAPTER]
TIMEBASE=1/1000
START=10000
END=30000
title=Opening
[CHAPTER]
TIMEBASE=1/1000
START=30000
END=70000
title=Episode
[CHAPTER]
TIMEBASE=1/1000
START=70000
END=120000
title=End Credits
EOF
  ffmpeg -loglevel error -y -f lavfi -i testsrc2=size=640x360:rate=25 \
    -f lavfi -i "sine=frequency=330:sample_rate=48000" -i assets/intro-chapters.txt \
    -map 0:v -map 1:a -map_metadata 2 -map_chapters 2 -t 120 \
    -c:v libx264 -preset ultrafast -crf 35 -pix_fmt yuv420p \
    -c:a aac -ac 2 -metadata:s:a:0 language=eng "$INTRO" || true
fi
EPISODE_24="$MEDIA/tv/Severance (2022)/Season 02/Severance - S02E04.mkv"
if [[ -s "$INTRO" ]]; then
  # Remplace le .mp4 posé par make_media.py (même nom : la fiche .nfo suit)
  rm -f "${EPISODE_24%.mkv}.mp4" "$EPISODE_24" && ln "$INTRO" "$EPISODE_24"
fi
export BENCH_INTRO_EPISODE="$EPISODE_24"

cat > "$KODI_DIR/userdata/sources.xml" <<EOF
<sources>
  <video>
    <default pathversion="1"></default>
    <source><name>Séries (banc)</name><path pathversion="1">$MEDIA/tv/</path><allowsharing>true</allowsharing></source>
    <source><name>Films (banc)</name><path pathversion="1">$MEDIA/movies/</path><allowsharing>true</allowsharing></source>
    <source><name>Vidéos perso (banc)</name><path pathversion="1">$BENCH_DIR/apps/perso/</path><allowsharing>true</allowsharing></source>
  </video>
</sources>
EOF

# ── 1c. Vidéo du panneau pendant la lecture (ADR-004, phase 4.5) ────────────
# 2 pistes audio (anglais 5.1 AC3, français stéréo « VFF »), 2 pistes de
# sous-titres (anglais, français forcés) et 3 chapitres. Le harnais y dépose
# ensuite « Panneau.fr.srt » comme le ferait Bazarr : on l'efface à chaque
# passage pour que le panneau le voie apparaître.
PANEL_DIR="$BENCH_DIR/panel"
mkdir -p "$PANEL_DIR"
rm -f "$PANEL_DIR"/*.srt
if command -v ffmpeg >/dev/null && [[ ! -s "$PANEL_DIR/Panneau.mkv" ]]; then
  printf '1\n00:00:00,000 --> 00:03:00,000\nEnglish subtitles (bench)\n' > assets/panel-en.srt
  printf '1\n00:00:00,000 --> 00:03:00,000\nSous-titres forcés (banc)\n' > assets/panel-fr.srt
  cat > assets/panel-chapters.txt <<'EOF'
;FFMETADATA1
[CHAPTER]
TIMEBASE=1/1000
START=0
END=40000
title=Ouverture
[CHAPTER]
TIMEBASE=1/1000
START=40000
END=80000
title=Milieu
[CHAPTER]
TIMEBASE=1/1000
START=80000
END=120000
title=Fin
EOF
  ffmpeg -loglevel error -y -f lavfi -i testsrc2=size=640x360:rate=25 \
    -f lavfi -i "sine=frequency=440:sample_rate=48000" \
    -f lavfi -i "sine=frequency=660:sample_rate=48000" \
    -i assets/panel-en.srt -i assets/panel-fr.srt -i assets/panel-chapters.txt \
    -map 0:v -map 1:a -map 2:a -map 3:s -map 4:s -map_metadata 5 -map_chapters 5 -t 120 \
    -c:v libx264 -preset ultrafast -crf 35 -pix_fmt yuv420p \
    -c:a:0 ac3 -ac:a:0 6 -c:a:1 aac -ac:a:1 2 -c:s srt \
    -metadata:s:a:0 language=eng -metadata:s:a:1 language=fre -metadata:s:a:1 title=VFF \
    -metadata:s:s:0 language=eng -metadata:s:s:1 language=fre -disposition:s:1 forced \
    "$PANEL_DIR/Panneau.mkv" || true
fi
export BENCH_PANEL="$PANEL_DIR/Panneau.mkv"

# ── 2. Add-ons : version de travail du dépôt + harnais ───────────────────────
rm -rf "$KODI_DIR/addons/script.arrmada" "$KODI_DIR/addons/service.arrmada.harness" \
       "$KODI_DIR/addons/plugin.video.arrmadabanc"
cp -r "$REPO/kodi-addon/script.arrmada" "$KODI_DIR/addons/"
cp -r "$BENCH_SRC/harness/service.arrmada.harness" "$KODI_DIR/addons/"
cp -r "$BENCH_SRC/harness/plugin.video.arrmadabanc" "$KODI_DIR/addons/"

# ── 2b. Applis & sources (ADR-004, phase 4.3) ────────────────────────────────
# Faux add-on vidéo (à la place de YouTube), TV en direct IPTV Simple avec 3
# chaînes locales et leur guide, dossier « vidéos perso », favoris Kodi.
# Prérequis : sudo apt install kodi-pvr-iptvsimple (sinon : pas d'onglet TV).
APPS="$BENCH_DIR/apps"
export BENCH_APPS="$APPS" BENCH_CLIP="$BENCH_DIR/assets/clip-90s.mp4"
python3 "$BENCH_SRC/make_apps.py" "$APPS" assets/clip-90s.mp4 "$KODI_DIR/addons/plugin.video.arrmadabanc"
mkdir -p "$KODI_DIR/userdata/addon_data/pvr.iptvsimple"
cat > "$KODI_DIR/userdata/addon_data/pvr.iptvsimple/instance-settings-1.xml" <<EOF
<settings version="2">
    <setting id="kodi_addon_instance_name">Banc</setting>
    <setting id="kodi_addon_instance_enabled">true</setting>
    <setting id="m3uPathType">0</setting>
    <setting id="m3uPath">$APPS/iptv/banc.m3u</setting>
    <setting id="epgPathType">0</setting>
    <setting id="epgPath">$APPS/iptv/banc.xml</setting>
</settings>
EOF
# Favoris : l'add-on (RunAddon), un dossier (ActivateWindow), une fenêtre de
# Kodi ; le harnais y ajoute ensuite les raccourcis ArrMada (masqués à l'écran).
cat > "$KODI_DIR/userdata/favourites.xml" <<EOF
<favourites>
    <favourite name="Banc TV" thumb="$KODI_DIR/addons/plugin.video.arrmadabanc/icon.png">RunAddon(plugin.video.arrmadabanc)</favourite>
    <favourite name="Vidéos perso" thumb="DefaultFolder.png">ActivateWindow(10025,&quot;$APPS/perso/&quot;,return)</favourite>
    <favourite name="Guide TV" thumb="DefaultAddonPVRClient.png">ActivateWindow(TVGuide)</favourite>
</favourites>
EOF
cat > "$KODI_DIR/userdata/addon_data/script.arrmada/settings.xml" <<EOF
<settings version="2">
    <setting id="server_url">$MOCK_URL</setting>
    <setting id="api_key">banc-de-test</setting>
    <setting id="enable_notifications">true</setting>
    <setting id="enable_scrobble">true</setting>
    <setting id="shell_mode">true</setting>
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

# Add-ons copiés à la main + TV en direct (IPTV Simple et ses lecteurs de flux).
# Une ligne absente serait créée par Kodi au démarrage, mais DÉSACTIVÉE.
ADDONS = (
    "script.arrmada", "service.arrmada.harness", "plugin.video.arrmadabanc",
    "pvr.iptvsimple", "inputstream.ffmpegdirect", "inputstream.adaptive", "inputstream.rtmp",
)
with sqlite3.connect(sys.argv[1]) as db:
    for addon in ADDONS:
        db.execute(
            "INSERT OR IGNORE INTO installed (addonID, enabled, installDate) "
            "VALUES (?, 1, datetime('now'))",
            (addon,),
        )
        db.execute("UPDATE installed SET enabled=1, disabledReason=0 WHERE addonID=?", (addon,))
PY
# Contenu des sources (Séries / Films, scraper « Informations locales ») : ce
# que fait « Définir le contenu » dans Kodi. La médiathèque est vidée à chaque
# passage ; le harnais la rescanne : résultats reproductibles.
python3 - "$KODI_DIR/userdata/Database" "$MEDIA" <<'PY'
import glob
import sqlite3
import sys

folder, media = sys.argv[1:]
for path in glob.glob(f"{folder}/MyVideos*.db"):
    with sqlite3.connect(path) as db:
        for table in ("episode", "seasons", "tvshow", "movie", "files", "bookmark", "path",
                      "tvshowlinkpath", "art", "uniqueid", "streamdetails"):
            db.execute(f"DELETE FROM {table}")
        for sub, content, recursive, folder_names in (("tv", "tvshows", 0, 0),
                                                      ("movies", "movies", 2147483647, 1)):
            db.execute(
                "INSERT INTO path (strPath, strContent, strScraper, scanRecursive, "
                "useFolderNames, strSettings, noUpdate, exclude, allAudio) "
                "VALUES (?, ?, 'metadata.local', ?, ?, '', 0, 0, 0)",
                (f"{media}/{sub}/", content, recursive, folder_names),
            )
PY

# ── 5. Passage instrumenté (le harnais quitte Kodi à la fin) ─────────────────
if [[ "$RECORD" != "1" ]]; then
  echo "== Kodi + harnais (≈ 11 min)"
  timeout 900 xvfb-run -a -s "-screen 0 1920x1080x24" kodi --standalone -fs > kodi.log 2>&1 || true
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
  timeout 960 tail --pid="$KODI_PID" -f /dev/null || kill "$KODI_PID" 2>/dev/null || true
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
echo "== Suivi de lecture reçu par le faux serveur"
grep -F "[mock] lecture" mock.log || true
echo "== Captures : $SHOT_DIR"
ls -1 "$SHOT_DIR"

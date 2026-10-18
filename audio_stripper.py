import os
import subprocess
import json
import logging
from pathlib import Path

# Config
MEDIA_DIRS = ["/mnt/user/data/media/movies", "/mnt/user/data/media/tv"]
ALLOWED_LANGUAGES = ["fre", "fra", "fr", "eng", "en"]
LOG_FILE = "/mnt/user/appdata/arrmada/audio_stripper.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)

def get_mkv_info(filepath):
    """Utilise mkvmerge pour lister les pistes d'un fichier MKV."""
    try:
        result = subprocess.run(
            ["mkvmerge", "-J", filepath],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except FileNotFoundError:
        logging.error("mkvmerge n'est pas installé. Veuillez installer mkvtoolnix.")
        return None
    except Exception as e:
        logging.error(f"Erreur lors de la lecture de {filepath}: {e}")
        return None

def process_file(filepath):
    info = get_mkv_info(filepath)
    if not info or "tracks" not in info:
        return

    audio_tracks_to_keep = []
    audio_tracks_to_remove = []
    has_unwanted = False

    for track in info["tracks"]:
        if track["type"] == "audio":
            lang = track.get("properties", {}).get("language", "und")
            if lang.lower() in ALLOWED_LANGUAGES:
                audio_tracks_to_keep.append(str(track["id"]))
            else:
                audio_tracks_to_remove.append(str(track["id"]))
                has_unwanted = True

    if not has_unwanted:
        # Fichier déjà propre
        return

    if not audio_tracks_to_keep:
        logging.warning(f"Attention: Aucune piste audio FR/EN trouvée dans {filepath}. Fichier ignoré.")
        return

    logging.info(f"Nettoyage de {filepath}")
    logging.info(f"  Pistes conservées : {','.join(audio_tracks_to_keep)}")
    logging.info(f"  Pistes supprimées : {','.join(audio_tracks_to_remove)}")

    # Construction de la commande mkvmerge
    # On garde la video, les sous-titres, et uniquement les pistes audio voulues
    temp_file = f"{filepath}.tmp.mkv"
    cmd = [
        "mkvmerge",
        "-o", temp_file,
        "--audio-tracks", ",".join(audio_tracks_to_keep),
        filepath
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        # Remplacement de l'ancien fichier
        os.replace(temp_file, filepath)
        logging.info(f"  -> Succès: {filepath} a été nettoyé.")
    except Exception as e:
        logging.error(f"  -> Erreur lors du nettoyage de {filepath}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

def main():
    for d in MEDIA_DIRS:
        path = Path(d)
        if not path.exists():
            continue
        for mkv_file in path.rglob("*.mkv"):
            process_file(str(mkv_file))

if __name__ == "__main__":
    main()

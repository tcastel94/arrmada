# -*- coding: utf-8 -*-
"""Panneau ArrMada pendant le film : logique pure, sans Kodi (testée en CI).

ADR-004, phase 4.5. Un appui long sur OK pendant la lecture ouvre un panneau
par-dessus la vidéo (qui continue) : à gauche les sections, à droite leurs
choix.

  - Audio       : pistes du fichier (« Français · TrueHD 7.1 »), une coche
                  sur celle en cours ;
  - Sous-titres : Désactivés, pistes du fichier, puis « Chercher avec
                  Bazarr » et « Synchroniser avec l'audio » ;
  - Ampli       : volume −/+, muet, préréglages des pièces (Yamaha) ;
  - Lecture     : épisode suivant, s'arrêter après celui-ci, chapitres,
                  reprendre depuis le début.

C'est la dernière chose qu'on allait chercher dans la barre de lecture de
SiLVO au quotidien. La barre de Kodi reste là pour avancer / reculer (OK
court), le panneau ne la remplace pas.

Le raccourci est un « fichier de touches » de Kodi (keymap) posé par le
service dans le profil (userdata/keymaps/arrmada.xml) : comme un fichier
d'override dans /etc/*.d/, il ajoute une règle sans toucher aux fichiers
de Kodi, et on le retire en décochant le réglage.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

ACTION = "player"  # plugin://script.arrmada/?action=player
POPUP_PROP = "arrmada.player_open"  # « 1 » tant que le panneau est ouvert
KEYMAP_FILE = "arrmada.xml"
SUBTITLE_EXTENSIONS = (".srt", ".ass", ".ssa", ".sub", ".vtt", ".smi")
SUBTITLE_WAIT = 90  # s d'attente du fichier téléchargé par Bazarr
VOLUME_STEP = 4  # pas de l'ampli par appui (Yamaha : 0,5 dB par unité)

SECTIONS = (
    ("audio", "Audio"),
    ("subtitles", "Sous-titres"),
    ("amp", "Ampli"),
    ("playback", "Lecture"),
)

# Codes de langue ISO 639-1 / 639-2 (B et T) → nom affiché
LANGUAGES = {
    "fr": "Français", "fre": "Français", "fra": "Français",
    "en": "Anglais", "eng": "Anglais",
    "de": "Allemand", "ger": "Allemand", "deu": "Allemand",
    "es": "Espagnol", "spa": "Espagnol",
    "it": "Italien", "ita": "Italien",
    "pt": "Portugais", "por": "Portugais",
    "nl": "Néerlandais", "dut": "Néerlandais", "nld": "Néerlandais",
    "ja": "Japonais", "jpn": "Japonais",
    "ko": "Coréen", "kor": "Coréen",
    "zh": "Chinois", "chi": "Chinois", "zho": "Chinois",
    "ru": "Russe", "rus": "Russe",
    "ar": "Arabe", "ara": "Arabe",
    "sv": "Suédois", "swe": "Suédois",
    "da": "Danois", "dan": "Danois",
    "no": "Norvégien", "nor": "Norvégien",
    "fi": "Finnois", "fin": "Finnois",
    "pl": "Polonais", "pol": "Polonais",
    "tr": "Turc", "tur": "Turc",
    "hi": "Hindi", "hin": "Hindi",
}  # fmt: skip

# Codecs audio tels que Kodi les nomme → nom commercial
CODECS = {
    "truehd": "Dolby TrueHD",
    "eac3": "Dolby Digital Plus",
    "ac3": "Dolby Digital",
    "dts": "DTS",
    "dca": "DTS",
    "dtshd_ma": "DTS-HD MA",
    "dtshd_hra": "DTS-HD HRA",
    "dts_x": "DTS:X",
    "aac": "AAC",
    "flac": "FLAC",
    "opus": "Opus",
    "mp3": "MP3",
    "vorbis": "Vorbis",
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def language_name(code: Any) -> str:
    """« fre » → « Français » ; un code inconnu est rendu tel quel, en majuscules."""
    text = str(code or "").strip()
    if not text or text.lower() in ("und", "unk", "mis", "zxx"):
        return "Langue inconnue"
    return LANGUAGES.get(text.lower(), text.upper())


def codec_label(codec: Any) -> str:
    text = str(codec or "").strip().lower()
    if text.startswith("pcm"):
        return "PCM"
    return CODECS.get(text, text.upper())


def channels_label(channels: Any) -> str:
    """6 → « 5.1 », 8 → « 7.1 », 2 → « Stéréo », 1 → « Mono »."""
    count = _int(channels)
    if count <= 0:
        return ""
    return {1: "Mono", 2: "Stéréo", 6: "5.1", 7: "6.1", 8: "7.1"}.get(count, f"{count} canaux")


VIDEO_EXTENSIONS = (".mkv", ".mp4", ".m4v", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".webm")


def clean_title(title: Any) -> str:
    """Fichier hors médiathèque : « Concert.Zenith.2025.mkv » → « Concert Zenith 2025 »."""
    text = str(title or "").strip()
    if text.lower().endswith(VIDEO_EXTENSIONS):
        text = text.rsplit(".", 1)[0].replace(".", " ").replace("_", " ").strip()
    return text


def _join(*parts: Any) -> str:
    return " · ".join(str(p) for p in parts if p)


def _option(label: str, label2: str, op: str, value: Any = None, selected: bool = False) -> Dict:
    """Une ligne de la colonne de droite."""
    return {"label": label, "label2": label2, "op": op, "value": value, "selected": selected}


# ─────────────────────────────────────────────────────────────────────────────
# Pistes audio et sous-titres (réponse de Player.GetProperties)
# ─────────────────────────────────────────────────────────────────────────────


def audio_label(stream: Mapping[str, Any]) -> Dict[str, str]:
    """{"label": « Français », "label2": « Dolby TrueHD 7.1 · Audiodescription »}."""
    sound = " ".join(
        p for p in (codec_label(stream.get("codec")), channels_label(stream.get("channels"))) if p
    )
    extra = []
    if stream.get("isimpaired"):
        extra.append("Audiodescription")
    if stream.get("isoriginal"):
        extra.append("VO")
    name = str(stream.get("name") or "").strip()
    language = language_name(stream.get("language"))
    if name and name.lower() not in language.lower() and len(name) <= 40:
        extra.append(name)
    return {"label": language, "label2": _join(sound, *extra)}


def audio_options(
    streams: Iterable[Mapping[str, Any]], current: Optional[int]
) -> List[Dict[str, Any]]:
    out = []
    for stream in streams or []:
        index = _int(stream.get("index"), -1)
        if index < 0:
            continue
        texts = audio_label(stream)
        out.append(dict(texts, op="audio", value=index, selected=index == current))
    return out


def subtitle_label(stream: Mapping[str, Any]) -> Dict[str, str]:
    extra = []
    if stream.get("isforced"):
        extra.append("Forcés")
    if stream.get("isimpaired"):
        extra.append("Malentendants")
    name = str(stream.get("name") or "").strip()
    language = language_name(stream.get("language"))
    if name.strip("()").lower() == "external":
        name = "Fichier externe"  # sous-titres posés à côté de la vidéo (Bazarr…)
    if name and name.lower() not in language.lower() and len(name) <= 40:
        extra.append(name)
    return {"label": language, "label2": _join(*extra)}


def subtitle_options(
    streams: Iterable[Mapping[str, Any]],
    current: Optional[int],
    enabled: bool,
    language: str = "fr",
) -> List[Dict[str, Any]]:
    """Désactivés, pistes du fichier, puis les actions Bazarr."""
    out: List[Dict[str, Any]] = [_option("Désactivés", "", "subtitle_off", None, not enabled)]
    for stream in streams or []:
        index = _int(stream.get("index"), -1)
        if index < 0:
            continue
        texts = subtitle_label(stream)
        out.append(dict(texts, op="subtitle", value=index, selected=enabled and index == current))
    name = language_name(language)
    out.append(
        _option(
            f"Chercher en {name.lower()} avec Bazarr",
            "Téléchargés puis chargés sans relancer le film",
            "bazarr_search",
        )
    )
    out.append(
        _option("Synchroniser avec l'audio", "Bazarr recale les sous-titres décalés", "bazarr_sync")
    )
    return out


def current_audio_summary(options: List[Mapping[str, Any]]) -> str:
    chosen = next((o for o in options if o.get("selected")), None)
    if chosen is None:
        return ""
    return _join(chosen["label"], chosen.get("label2", "").split(" · ")[0])


def current_subtitle_summary(options: List[Mapping[str, Any]]) -> str:
    chosen = next((o for o in options if o.get("selected")), None)
    if chosen is None or chosen["op"] == "subtitle_off":
        return "Désactivés"
    return _join(chosen["label"], chosen.get("label2", ""))


# ─────────────────────────────────────────────────────────────────────────────
# Ampli et lecture
# ─────────────────────────────────────────────────────────────────────────────


def amp_options(model: Mapping[str, Any], room: str = "") -> List[Dict[str, Any]]:
    """Volume, muet, préréglages ; vide si aucun ampli n'est joignable.

    `model` : screens_data.build_salon (état de l'ampli de la pièce de la TV).
    """
    if not model.get("configured") or not model.get("online"):
        return []
    volume = _join(model.get("volume"), model.get("db"))
    muted = bool(model.get("mute"))
    out: List[Dict[str, Any]] = [
        _option("Volume −", volume, "volume", -VOLUME_STEP),
        _option("Volume +", volume, "volume", VOLUME_STEP),
        _option(
            "Rétablir le son" if muted else "Couper le son", "Muet" if muted else "", "mute",
            not muted, muted,
        ),
    ]  # fmt: skip
    for preset in model.get("presets") or []:
        out.append(
            _option(
                f"Préréglage « {preset['name']} »",
                "Cette pièce" if preset.get("room") == room else "",
                "preset",
                preset.get("room"),
            )
        )
    return out


def episode_line(item: Mapping[str, Any]) -> str:
    """Élément de la liste de lecture → « S01E06 · Titre »."""
    season, episode = _int(item.get("season"), -1), _int(item.get("episode"), -1)
    code = f"S{season:02d}E{episode:02d}" if season >= 0 and episode > 0 else ""
    return _join(code, str(item.get("title") or item.get("label") or "").strip())


def playback_options(
    next_item: Optional[Mapping[str, Any]], queued_after: int, chapters: int, position: float
) -> List[Dict[str, Any]]:
    """Épisode suivant, s'arrêter après celui-ci, chapitres, depuis le début."""
    out: List[Dict[str, Any]] = []
    if next_item:
        out.append(_option("Épisode suivant", episode_line(next_item), "next"))
    if queued_after > 0:
        later = f"{queued_after} épisode{'s' if queued_after > 1 else ''} en file"
        out.append(_option("S'arrêter après celui-ci", later, "stop_after"))
    if chapters > 1:
        out.append(_option("Chapitre suivant", f"{chapters} chapitres", "chapter", 1))
        out.append(_option("Chapitre précédent", "", "chapter", -1))
    if position >= 60:
        out.append(_option("Reprendre depuis le début", "", "restart"))
    return out


def sections(
    audio: List[Mapping[str, Any]],
    subtitles: List[Mapping[str, Any]],
    amp: List[Mapping[str, Any]],
    playback: List[Mapping[str, Any]],
    amp_summary: str = "",
) -> List[Dict[str, str]]:
    """Colonne de gauche : sections non vides, avec un résumé de l'état."""
    summaries = {
        "audio": current_audio_summary(audio) if audio else "",
        "subtitles": current_subtitle_summary(subtitles),
        "amp": amp_summary,
        "playback": "",
    }
    present = {"audio": audio, "subtitles": subtitles, "amp": amp, "playback": playback}
    return [
        {"key": key, "label": label, "label2": summaries[key]}
        for key, label in SECTIONS
        if present[key]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Sous-titres téléchargés par Bazarr : retrouver le nouveau fichier
# ─────────────────────────────────────────────────────────────────────────────


def split_path(path: str) -> tuple:
    """« smb://nas/films/Dune/Dune.mkv » → (« smb://nas/films/Dune/ », « Dune »)."""
    text = str(path or "")
    cut = max(text.rfind("/"), text.rfind("\\"))
    folder, name = text[: cut + 1], text[cut + 1 :]
    base = name.rsplit(".", 1)[0] if "." in name else name
    return folder, base


def subtitle_files(files: Iterable[str], base: str) -> List[str]:
    """Fichiers de sous-titres de cette vidéo (« Dune.fr.srt », « Dune.fr.forced.srt »)."""
    prefix = f"{base}.".lower()
    return sorted(
        f for f in files or []
        if f.lower().startswith(prefix) and f.lower().endswith(SUBTITLE_EXTENSIONS)
    )  # fmt: skip


def new_subtitle(before: Iterable[str], after: Iterable[str], language: str = "fr") -> str:
    """Le fichier apparu depuis la recherche (de préférence dans la langue voulue)."""
    fresh = [f for f in after if f not in set(before)]
    if not fresh:
        return ""
    tag = f".{language.lower()}."
    in_language = [f for f in fresh if tag in f.lower()]
    # Les sous-titres « forcés » ne traduisent que les passages en langue étrangère
    full = [f for f in (in_language or fresh) if ".forced." not in f.lower()]
    return (full or in_language or fresh)[0]


def language_subtitle(files: Iterable[str], language: str = "fr") -> str:
    """Fichier complet dans la langue voulue (pour le recharger après synchronisation)."""
    tag = f".{language.lower()}."
    candidates = [f for f in files if tag in f.lower() and ".forced." not in f.lower()]
    return candidates[0] if candidates else ""


# ─────────────────────────────────────────────────────────────────────────────
# Raccourci : fichier de touches de Kodi
# ─────────────────────────────────────────────────────────────────────────────


def keymap_xml() -> str:
    """Appui long sur OK pendant une vidéo → panneau ArrMada.

    Clavier (`return` / `enter` : télécommande de la Shield, TV en CEC) et
    télécommandes infrarouges (`select`). Un appui court garde son rôle
    (barre de lecture de Kodi).
    """
    command = f"RunPlugin(plugin://script.arrmada/?action={ACTION})"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Posé par ArrMada (réglage « Panneau pendant la lecture ») ;"
        " retiré si on décoche le réglage. -->\n"
        "<keymap>\n"
        "  <FullscreenVideo>\n"
        "    <keyboard>\n"
        f'      <return mod="longpress">{command}</return>\n'
        f'      <enter mod="longpress">{command}</enter>\n'
        "    </keyboard>\n"
        "    <remote>\n"
        f'      <select mod="longpress">{command}</select>\n'
        "    </remote>\n"
        "  </FullscreenVideo>\n"
        "</keymap>\n"
    )


def keymap_change(enabled: bool, current: Optional[str]) -> str:
    """« write », « remove » ou "" (rien à faire) selon le réglage et le fichier en place."""
    if enabled:
        return "" if current == keymap_xml() else "write"
    return "remove" if current is not None else ""

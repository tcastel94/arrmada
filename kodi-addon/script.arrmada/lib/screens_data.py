# -*- coding: utf-8 -*-
"""Données des écrans de la phase 2 : Fiche média, Téléchargements, Salon.

Comme home_data.py, ce module ne dépend PAS de Kodi : il transforme les
réponses JSON du backend en « modèles d'affichage » prêts à poser dans les
fenêtres. Testé par pytest en CI (kodi-addon/tests/test_screens_data.py).

Routes du backend utilisées :
  GET /api/media/{movie|series}/{id}  → fiche (Radarr/Sonarr + Bazarr)
  GET /api/downloads                  → file de téléchargement complète
  GET /api/yamaha/state, /profiles    → ampli et préréglages des pièces
"""

from __future__ import annotations

import re
from typing import Any

from home_data import audio_badge, fmt_timeleft, hdr_badge, human_bytes, resolution_badge

# ─────────────────────────────────────────────────────────────────────────────
# Mise en forme commune
# ─────────────────────────────────────────────────────────────────────────────

# Genres *arr (anglais) → français, même table que la web app
# (frontend/src/components/analytics/genres.ts).
GENRES_FR = {
    "action": "Action",
    "action & adventure": "Action & aventure",
    "adventure": "Aventure",
    "animation": "Animation",
    "anime": "Anime",
    "biography": "Biographie",
    "children": "Enfants",
    "comedy": "Comédie",
    "crime": "Policier",
    "documentary": "Documentaire",
    "drama": "Drame",
    "family": "Famille",
    "fantasy": "Fantastique",
    "game show": "Jeu télévisé",
    "history": "Histoire",
    "horror": "Horreur",
    "kids": "Enfants",
    "martial arts": "Arts martiaux",
    "mini-series": "Mini-série",
    "music": "Musique",
    "musical": "Comédie musicale",
    "mystery": "Mystère",
    "news": "Actualités",
    "reality": "Téléréalité",
    "romance": "Romance",
    "sci-fi & fantasy": "SF & fantastique",
    "science fiction": "Science-fiction",
    "science-fiction": "Science-fiction",
    "soap": "Feuilleton",
    "sport": "Sport",
    "suspense": "Suspense",
    "talk": "Talk-show",
    "talk show": "Talk-show",
    "thriller": "Thriller",
    "tv movie": "Téléfilm",
    "war": "Guerre",
    "war & politics": "Guerre & politique",
    "western": "Western",
}

BAR_STEP = 2  # barres de progression pré-rendues tous les 2 % (bar-000 … bar-100)


def genre_fr(name: str) -> str:
    return GENRES_FR.get(str(name or "").strip().lower(), str(name or "").strip())


def fmt_runtime(minutes: Any) -> str:
    """166 → « 2 h 46 » ; 48 → « 48 min » ; 0/None → « »."""
    try:
        total = int(minutes or 0)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    hours, mins = divmod(total, 60)
    return f"{hours} h {mins:02d}" if hours else f"{mins} min"


def fmt_rating(value: Any) -> str:
    """8.234 → « 8,2 » ; absent → « »."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.1f}".replace(".", ",") if number > 0 else ""


def bar_texture(pct: Any) -> str:
    """Nom de la barre pré-rendue la plus proche : 61.7 → « bar-062 »."""
    try:
        value = float(pct)
    except (TypeError, ValueError):
        value = 0.0
    step = int(round(max(0.0, min(100.0, value)) / BAR_STEP)) * BAR_STEP
    return f"bar-{step:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Fiche média
# ─────────────────────────────────────────────────────────────────────────────


def source_badge(quality: str) -> str:
    """« Remux », « Blu-ray », « WEB-DL »… d'après le nom de qualité *arr."""
    q = str(quality or "").lower()
    if "remux" in q:
        return "Remux"
    if re.search(r"blu-?ray|bdrip|brrip", q):
        return "Blu-ray"
    if re.search(r"web-?dl", q):
        return "WEB-DL"
    if "webrip" in q:
        return "WEBRip"
    if "hdtv" in q:
        return "HDTV"
    if "dvd" in q:
        return "DVD"
    return ""


def _channels(value: Any) -> str:
    try:
        ch = float(value or 0)
    except (TypeError, ValueError):
        return ""
    if ch >= 7:
        return "7.1"
    if ch >= 5:
        return "5.1"
    if ch >= 2:
        return "Stéréo"
    return ""


def _crew_line(crew: list[dict]) -> str:
    """« Réalisation : Denis Villeneuve · Musique : Hans Zimmer »."""
    roles = (
        ("Director", "Réalisation"),
        ("Screenplay", "Scénario"),
        ("Writer", "Scénario"),
        ("Original Music Composer", "Musique"),
    )
    parts: list[str] = []
    used: set[str] = set()
    for job, label in roles:
        if label in used:
            continue
        names = [p.get("name", "") for p in crew if p.get("job") == job and p.get("name")]
        if names:
            parts.append(f"{label} : {', '.join(names[:2])}")
            used.add(label)
    return " · ".join(parts)


# Statut de diffusion Sonarr → libellé affiché sur la fiche série
SERIES_STATUS = {
    "continuing": "Série en cours de diffusion",
    "ended": "Série terminée",
    "upcoming": "Série à venir",
    "deleted": "Série retirée",
}


def _latest_episode_file(detail: dict) -> tuple[str, dict]:
    """Dernier épisode téléchargé d'une série : (« S02E06 », infos fichier).

    Sonarr ne donne pas de « fichier » pour une série entière : on décrit le
    plus récent (plus haute saison, plus haut épisode), c'est en général la
    qualité actuelle de la série et celle qui sert au préréglage de l'ampli.
    """
    for season in sorted(
        detail.get("seasons") or [], key=lambda s: int(s.get("season_number") or 0), reverse=True
    ):
        for episode in sorted(
            season.get("episodes") or [],
            key=lambda e: int(e.get("episode_number") or 0),
            reverse=True,
        ):
            if episode.get("has_file") and episode.get("file"):
                code = "S{:02d}E{:02d}".format(
                    int(season.get("season_number") or 0), int(episode.get("episode_number") or 0)
                )
                return code, episode["file"]
    return "", {}


def build_detail(detail: dict, kind: str) -> dict[str, Any]:
    """Modèle de la fiche à partir de /api/media/{movie|series}/{id}."""
    is_movie = kind == "movie"
    images = detail.get("images") or {}
    ratings = detail.get("ratings") or {}
    if is_movie:
        episode_code, file = "", detail.get("file") or {}
    else:
        episode_code, file = _latest_episode_file(detail)

    genres = [genre_fr(g) for g in (detail.get("genres") or [])][:3]
    meta = [str(detail["year"])] if detail.get("year") else []
    runtime = fmt_runtime(detail.get("runtime"))
    if runtime:
        meta.append(runtime)
    if detail.get("certification"):
        meta.append(str(detail["certification"]))
    if not is_movie and detail.get("network"):
        meta.append(str(detail["network"]))
    if genres:
        meta.append(", ".join(genres))

    notes = []
    if is_movie:
        for key, label in (("tmdb", "TMDB"), ("imdb", "IMDb")):
            value = fmt_rating(ratings.get(key))
            if value:
                notes.append(f"{label} {value}")
        if ratings.get("rotten_tomatoes"):
            notes.append(f"Rotten Tomatoes {int(ratings['rotten_tomatoes'])} %")
    else:
        if fmt_rating(ratings.get("value")):
            notes.append(f"Note {fmt_rating(ratings.get('value'))}")
        # Statut de diffusion : sur la ligne des notes (qui a de la place),
        # pas dans le bloc « Fichier » de la colonne de droite (5 lignes max).
        if SERIES_STATUS.get(str(detail.get("status") or "").lower()):
            notes.append(SERIES_STATUS[str(detail["status"]).lower()])

    tech = {
        "resolution": file.get("resolution"),
        "quality": file.get("quality"),
        "video_dynamic_range": file.get("video_dynamic_range"),
        "video_dynamic_range_type": file.get("video_dynamic_range_type"),
        "audio_codec": file.get("audio_codec"),
        "audio_channels": file.get("audio_channels"),
    }
    badges = [
        b
        for b in (
            resolution_badge(tech),
            hdr_badge(tech),
            audio_badge(tech),
            source_badge(file.get("quality", "")),
        )
        if b
    ]

    file_lines: list[str] = []
    if not is_movie:
        # Résumé de la série d'abord : épisodes présents, place sur le NAS, diffusion
        have = int(detail.get("episodes_have") or 0)
        summary = [f"{have} épisode{'s' if have > 1 else ''} sur le NAS"] if have else []
        if detail.get("size_on_disk"):
            summary.append(human_bytes(detail["size_on_disk"]))
        if summary:
            file_lines.append(" · ".join(summary))
    if file:
        size = human_bytes(file.get("size_bytes") or 0) if file.get("size_bytes") else ""
        first = [f"Dernier : {episode_code}"] if episode_code else []
        file_lines.append(" · ".join(x for x in (*first, file.get("quality"), size) if x))
        video = " · ".join(
            x
            for x in (
                file.get("video_codec"),
                file.get("video_dynamic_range_type") or file.get("video_dynamic_range"),
            )
            if x
        )
        if video:
            file_lines.append(f"Vidéo : {video}")
        audio = " ".join(
            x for x in (file.get("audio_codec"), _channels(file.get("audio_channels"))) if x
        )
        if file.get("audio_languages"):
            audio += f" · {file['audio_languages']}"
        if audio.strip():
            file_lines.append(f"Audio : {audio.strip()}")
        if is_movie and file.get("release_group"):
            # (séries : ligne omise, le bloc compte déjà 5 lignes)
            file_lines.append(f"Release : {file['release_group']}")

    subs = sorted(
        {
            str(s.get("language", "")).strip()
            for s in (detail.get("subtitles") or [])
            if s.get("language")
        }
    )
    if not subs and file.get("subtitle_languages"):
        subs = [s.strip() for s in str(file["subtitle_languages"]).split("/") if s.strip()]
    subtitles = ", ".join(subs) if subs else "aucun"

    if is_movie:
        status = "Disponible" if detail.get("has_file") else "Manquant"
    else:
        have, total = int(detail.get("episodes_have") or 0), int(detail.get("total_episodes") or 0)
        status = f"{have}/{total} épisodes" if total else ""

    cast = [
        {"name": p.get("name", ""), "role": p.get("character", ""), "photo": p.get("photo") or ""}
        for p in (detail.get("cast") or [])[:16]
        if p.get("name")
    ]
    seasons = []
    for season in detail.get("seasons") or []:
        number = int(season.get("season_number") or 0)
        count = int(season.get("episode_count") or 0)
        have = int(season.get("episodes_have") or 0)
        seasons.append(
            {
                "label": "Épisodes spéciaux" if number == 0 else f"Saison {number}",
                "progress": f"{have}/{count} épisodes",
                "pct": round(have * 100 / count) if count else 0,
                "bar": bar_texture(have * 100 / count if count else 0),
            }
        )

    return {
        "kind": "movie" if is_movie else "tvshow",
        "title": detail.get("title") or "",
        "meta": " · ".join(meta),
        "notes": "   ".join(notes),
        "overview": detail.get("overview") or "Aucun synopsis.",
        "badges": badges,
        "status": status,
        "file_lines": file_lines,
        "subtitles": subtitles,
        "crew": _crew_line(detail.get("crew") or []),
        "cast": cast,
        "seasons": seasons,
        "poster": images.get("poster") or "",
        "fanart": images.get("fanart") or "",
        "clearlogo": images.get("clearlogo") or images.get("logo") or "",
        "trailer": detail.get("youtube_trailer_id") or "",
        "tmdb_id": str(detail.get("tmdb_id") or "") if is_movie else "",
        "tvdb_id": "" if is_movie else str(detail.get("tvdb_id") or ""),
        "year": int(detail.get("year") or 0),
        "audio_codec": file.get("audio_codec") or "",
        "audio_channels": file.get("audio_channels") or 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Téléchargements
# ─────────────────────────────────────────────────────────────────────────────

# (libellé, famille de couleur) selon l'état *arr de l'élément de file.
_STATUS = {
    "downloading": ("En cours", "active"),
    "paused": ("En pause", "paused"),
    "queued": ("En attente", "queued"),
    "delay": ("En attente", "queued"),
    "importpending": ("Import en attente", "import"),
    "importing": ("Import…", "import"),
    "importblocked": ("Import bloqué", "error"),
    "failed": ("Échec", "error"),
    "failedpending": ("Échec", "error"),
    "warning": ("Attention", "error"),
    "completed": ("Terminé", "done"),
}


# États de suivi *arr qui priment sur l'état du client de téléchargement
_TRACKED_FIRST = {"importpending", "importing", "importblocked", "failedpending", "failed"}


def download_status(item: dict) -> tuple[str, str]:
    """(libellé, famille) d'un élément de la file.

    Radarr/Sonarr donnent deux champs : `tracked_state` (où en est *arr :
    téléchargement, import…) et `status` (ce que dit SABnzbd/qBittorrent).
    Pendant un téléchargement, `tracked_state` reste « downloading » même si
    SABnzbd est en pause : c'est alors `status` (« paused ») qui dit vrai.
    Une fois le téléchargement fini, c'est l'étape d'import qui compte.
    """
    if item.get("error"):
        return "Erreur", "error"
    tracked = str(item.get("tracked_state") or "").lower()
    status = str(item.get("status") or "").lower()
    order = (tracked, status) if tracked in _TRACKED_FIRST else (status, tracked)
    for key in order:
        if key in _STATUS:
            return _STATUS[key]
    return "En cours", "active"


def fmt_speed(bytes_per_s: float) -> str:
    """Débit lisible : 4 400 000 → « 4,2 Mo/s » ; 0 → « »."""
    if bytes_per_s <= 0:
        return ""
    return f"{human_bytes(bytes_per_s)}/s"


def build_downloads(
    items: list[dict], previous: dict[str, tuple[float, float]], now: float
) -> tuple[dict[str, Any], dict[str, tuple[float, float]]]:
    """Lignes de la file + débits estimés.

    *arr ne donne pas le débit : on l'estime en comparant le « reste à
    télécharger » d'un rafraîchissement à l'autre (comme `iftop` déduit un
    débit de compteurs d'octets). `previous` = {id: (horodatage, octets
    restants)} du passage précédent ; la fonction renvoie le nouvel état.
    """
    rows: list[dict[str, Any]] = []
    state: dict[str, tuple[float, float]] = {}
    total_speed = 0.0
    for item in items:
        key = f"{item.get('service_type', '')}:{item.get('id', '')}"
        size = float(item.get("size_bytes") or 0)
        left = float(item.get("size_left_bytes") or 0)
        pct = float(item.get("progress") or 0)
        speed = 0.0
        if key in previous:
            then, then_left = previous[key]
            elapsed = now - then
            if elapsed > 0 and then_left > left:
                speed = (then_left - left) / elapsed
        state[key] = (now, left)
        total_speed += speed
        label, family = download_status(item)
        meta = [
            str(item.get("service_type") or "").capitalize(),
            item.get("download_client") or "",
            item.get("quality") or "",
            item.get("indexer") or "",
        ]
        sizes = f"{human_bytes(size - left)} / {human_bytes(size)}" if size else ""
        rows.append(
            {
                "key": key,
                "id": item.get("id"),
                "service": item.get("service_type") or "",
                "title": item.get("title") or "Téléchargement",
                "meta": " · ".join(m for m in meta if m),
                "pct": f"{round(pct)} %",
                "bar": bar_texture(pct),
                "sizes": sizes,
                "eta": fmt_timeleft(item.get("time_left") or ""),
                "speed": fmt_speed(speed),
                "status": label,
                "family": family,
                "detail": item.get("error") or item.get("detail") or "",
                # Pour ouvrir la fiche du titre téléchargé (OK sur la ligne)
                "kind": "tvshow" if item.get("service_type") == "sonarr" else "movie",
                "arr_id": item.get("series_id")
                if item.get("service_type") == "sonarr"
                else item.get("movie_id"),
            }
        )
    active = sum(1 for r in rows if r["family"] == "active")
    paused = sum(1 for r in rows if r["family"] == "paused")
    summary = [f"{len(rows)} dans la file"] if rows else ["File vide"]
    if active:
        summary.append(f"{active} en cours")
    if paused:
        summary.append(f"{paused} en pause")
    if total_speed > 0:
        summary.append(fmt_speed(total_speed))
    return {"rows": rows, "summary": " · ".join(summary)}, state


# ─────────────────────────────────────────────────────────────────────────────
# Salon (ampli Yamaha)
# ─────────────────────────────────────────────────────────────────────────────

SOUND_PROGRAMS = {
    "straight": "Straight",
    "surr_decoder": "Surround Decoder",
    "7ch_stereo": "7ch Stereo",
    "all_ch_stereo": "All-Ch Stereo",
    "2ch_stereo": "2ch Stereo",
    "standard": "Standard",
    "spectacle": "Spectacle",
    "sci-fi": "Sci-Fi",
    "adventure": "Adventure",
    "drama": "Drama",
    "enhanced": "Enhanced",
    "music_video": "Music Video",
    "game": "Game",
}


def fmt_input(value: str) -> str:
    """« hdmi1 » → « HDMI 1 », « av_on » → « Av On »."""
    match = re.match(r"^([a-z_]+?)(\d+)$", str(value or ""))
    if match and match.group(1) in ("hdmi", "av", "audio", "optical", "coaxial"):
        return f"{match.group(1).upper()} {match.group(2)}"
    return str(value or "").replace("_", " ").title()


def build_salon(state: dict, profiles: dict) -> dict[str, Any]:
    """Ampli (1er appareil configuré) + préréglages des pièces."""
    devices = state.get("devices") or []
    device = devices[0] if devices else {}
    online = bool(device.get("online"))
    pct = int(device.get("volume_pct") or 0)
    db = device.get("actual_db")
    presets = [
        {"room": room, "name": (profiles.get(room) or {}).get("name") or room.capitalize()}
        for room in ("salon", "cinema")
        if room in profiles
    ]
    return {
        "configured": bool(device),
        "online": online,
        "name": device.get("name") or "Ampli Yamaha",
        "power": "Allumé"
        if device.get("power") == "on"
        else ("En veille" if online else "Hors ligne"),
        "is_on": device.get("power") == "on",
        "volume": f"{pct} %",
        "volume_bar": bar_texture(pct),
        "db": (f"{float(db):.1f} dB".replace(".", ",").replace("-", "−")) if db is not None else "",
        "mute": bool(device.get("mute")),
        "input": fmt_input(device.get("input") or ""),
        "program": SOUND_PROGRAMS.get(
            str(device.get("sound_program") or ""), str(device.get("sound_program") or "")
        ),
        "presets": presets,
    }

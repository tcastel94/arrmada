"""Lecture dans l'appli Android native (ADR-007).

L'appli lit le fichier d'origine stocké dans Jellyfin, sans transcodage
(« direct play »). La clé d'API Jellyfin est une clé administrateur : elle
ne quitte jamais le serveur. Le flux vidéo et les vignettes de chapitres
passent donc par ArrMada, qui relaie la requête en ajoutant la clé, comme
un reverse proxy :

    TV ──(jeton d'appareil)──▶ ArrMada ──(clé Jellyfin)──▶ Jellyfin

Ce module rassemble ce que la TV doit savoir avant de lancer la lecture
(identifiant Jellyfin, durée, chapitres, marqueurs, reprise) et ouvre le
flux relayé.

Deux façons de lire :

  - **direct** : le fichier tel quel (Range pour l'avance rapide). Le cas
    normal : MKV, MP4, TS… que le lecteur de la TV (ExoPlayer) sait ouvrir ;
  - **remux** : pour les formats qu'ExoPlayer ne sait pas ouvrir (.m2ts de
    Blu-ray, image .iso, dossier BDMV…), Jellyfin change le conteneur à la
    volée sans réencoder l'image (HLS, morceaux fMP4). Le son peut être
    converti en Dolby Digital Plus si le conteneur n'accepte pas l'original.
    La TV bascule aussi d'elle-même en remux si le direct échoue ;
  - **sdr** : pour le Dolby Vision « profil 5 » (aucune image de secours
    HDR10), sur un écran qui ne gère pas le Dolby Vision. Décodé comme du
    HEVC ordinaire, ce format donne une image violette et verte : Jellyfin
    le convertit alors en H.264 SDR 1080p avec « mappage tonal » (les
    couleurs Dolby Vision ramenées dans l'espace d'une TV ordinaire).
    C'est la TV qui décide (elle seule sait si son écran gère le DV).
    Le même flux sert de « qualité réduite » (1080p, 20 Mb/s) quand le
    réseau de la TV ne suit pas le fichier d'origine (ADR-012) : la TV
    compare le débit moyen du fichier (`bitrate`) aux coupures constatées.

Pas de flux 1080p qui garderait le HDR (ADR-012) : vérifié sur Jellyfin
12.3, tout réencodage d'une image HDR passe par le mappage tonal (sortie
BT.709) et le HEVC réencodé est forcé en Main 8 bits ; « hevc-rangetype=HDR10 »
ne sert qu'à décider de la copie de l'image, pas de l'encodage.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import jellyfin, watch_sync
from app.services.family_profiles import profiled_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Identifiant d'élément Jellyfin : 32 caractères hexadécimaux (un GUID sans
# tirets). Tout le reste est refusé avant d'appeler Jellyfin : la TV ne peut
# pas glisser un autre chemin dans l'adresse relayée.
ITEM_ID = re.compile(r"^[0-9a-f]{32}$")

# En-têtes recopiés de Jellyfin vers la TV : ceux qu'un lecteur vidéo utilise
# pour l'avance rapide (Range) et la taille du fichier.
_FORWARDED = (
    "content-type",
    "content-length",
    "content-range",
    "accept-ranges",
    "last-modified",
    "etag",
)

# Champs demandés à Jellyfin pour un élément
# (Trickplay : vignettes de la barre de lecture, Jellyfin 10.9+)
_FIELDS = "Chapters,Overview,MediaSources,ProviderIds,Path,Trickplay"

# Extensions que le lecteur de la TV (ExoPlayer) ouvre directement. Les
# autres (.m2ts, .mts, .iso, .vob, .img…) passent par le remux de Jellyfin.
DIRECT_EXTENSIONS = {"mkv", "mk3d", "webm", "mp4", "m4v", "mov", "ts", "avi", "ogv"}

# Morceaux du remux HLS que la TV peut demander : la liste de lecture
# principale, celle des morceaux, et les morceaux eux-mêmes. Rien d'autre
# n'est relayé vers Jellyfin.
HLS_PATH = re.compile(r"^(master|main|sdr)\.m3u8$|^hls1/[A-Za-z0-9_]+/-?\d+\.(mp4|m4s|ts)$")

# Identifiants de la session de remux chez Jellyfin (pour l'arrêter ensuite)
HLS_DEVICE = "arrmada-tv"

# Clé d'API glissée par Jellyfin dans les adresses de ses listes HLS : retirée
# avant d'envoyer la liste à la TV (la clé ne sort jamais du serveur).
_KEY_IN_URL = re.compile(r"(?i)([?&])(api_?key)=[^&\s\"]*(&?)")


def stream_path(item_id: str) -> str:
    return f"/api/tv/stream/{item_id}"


def chapter_image_path(item_id: str, index: int) -> str:
    return f"/api/tv/chapter-image/{item_id}/{index}"


def trickplay_path(item_id: str, width: int) -> str:
    """Planches de vignettes : la TV ajoute « /<n° de planche> »."""
    return f"/api/tv/trickplay/{item_id}/{width}"


def item_image_path(item_id: str) -> str:
    return f"/api/tv/item-image/{item_id}"


def hls_path(item_id: str) -> str:
    return f"/api/tv/hls/{item_id}/master.m3u8"


def sdr_path(item_id: str) -> str:
    """Conversion SDR (mappage tonal) : Dolby Vision profil 5 sur un écran sans DV."""
    return f"/api/tv/hls/{item_id}/sdr.m3u8"


def video_range(details: dict[str, Any]) -> dict[str, Any]:
    """Plage dynamique de l'image : « SDR », « HDR10 », « DOVI »… (VideoRangeType
    de Jellyfin 10.9+) et Dolby Vision sans image de secours (profil 5).

    Profil 5 : l'image de base est codée dans un espace de couleurs propre à
    Dolby (IPT), lisible seulement par une puce Dolby Vision. Les profils 7 et
    8 portent une image HDR10 de secours, lisible partout : pas de souci.
    Jellyfin plus ancien (sans VideoRangeType) : on lit DvProfile et
    DvBlSignalCompatibilityId (0 = aucune image de secours).
    """
    sources = details.get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    video = next(
        (
            s
            for s in source.get("MediaStreams") or []
            if isinstance(s, dict) and s.get("Type") == "Video"
        ),
        {},
    )
    range_type = str(video.get("VideoRangeType") or video.get("VideoRange") or "")
    profile = video.get("DvProfile")
    compat = video.get("DvBlSignalCompatibilityId")
    dovi_only = (
        range_type == "DOVI"
        or profile == 5
        or (isinstance(profile, int) and profile > 0 and compat == 0)
    )
    return {"video_range": range_type, "dovi_only": dovi_only}


# Sous-titres externes que la TV sait afficher : format demandé à Jellyfin
# (qui convertit au besoin, en UTF-8) et type MIME pour le lecteur. Les
# sous-titres « image » (PGS, VobSub) ne se convertissent pas en texte.
_SUB_FORMATS = {
    "subrip": ("srt", "application/x-subrip"),
    "srt": ("srt", "application/x-subrip"),
    "ass": ("ass", "text/x-ssa"),
    "ssa": ("ass", "text/x-ssa"),
    "webvtt": ("vtt", "text/vtt"),
    "vtt": ("vtt", "text/vtt"),
}
SUB_MIME = dict(_SUB_FORMATS.values())

# Langues ISO 639-2 de Jellyfin → code court et nom affiché
_LANGS = {
    "fre": ("fr", "Français"), "fra": ("fr", "Français"), "fr": ("fr", "Français"),
    "eng": ("en", "Anglais"), "en": ("en", "Anglais"),
    "spa": ("es", "Espagnol"), "ger": ("de", "Allemand"), "deu": ("de", "Allemand"),
    "ita": ("it", "Italien"), "jpn": ("ja", "Japonais"), "por": ("pt", "Portugais"),
}  # fmt: skip


def subtitle_path(item_id: str, index: int, ext: str) -> str:
    return f"/api/tv/subtitle/{item_id}/{index}.{ext}"


def external_subtitles(item_id: str, details: dict[str, Any]) -> list[dict[str, str]]:
    """Sous-titres externes connus de Jellyfin → [{url, label, language, mime}].

    Même format que les sous-titres de l'écran Vidéos : le lecteur les ajoute
    aux pistes du fichier (onglet Sous-titres du menu pause).
    """
    sources = details.get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    found = []
    for stream in source.get("MediaStreams") or []:
        if not isinstance(stream, dict) or stream.get("Type") != "Subtitle":
            continue
        if not stream.get("IsExternal") or not isinstance(stream.get("Index"), int):
            continue
        fmt = _SUB_FORMATS.get(str(stream.get("Codec") or "").lower())
        if fmt is None:
            continue
        code, name = _LANGS.get(str(stream.get("Language") or "").lower(), ("", ""))
        label = name or str(stream.get("DisplayTitle") or stream.get("Title") or "Externe")
        if stream.get("IsForced"):
            label += " (forcés)"
        elif stream.get("IsHearingImpaired"):
            label += " (SDH)"
        found.append({
            "url": subtitle_path(item_id, stream["Index"], fmt[0]),
            "label": f"{label} · fichier",
            "language": code,
            "mime": fmt[1],
        })  # fmt: skip
    return found


def embedded_subtitles(item_id: str, details: dict[str, Any]) -> list[dict[str, str]]:
    """Sous-titres texte INTÉGRÉS au fichier (MKV), même format qu'externes.

    Le lecteur les lit déjà dans le fichier ; cette liste ne sert qu'au
    décalage du menu pause : Jellyfin extrait la piste en .srt, le serveur
    la décale, la TV l'ajoute à côté (« Français (décalé +1,5 s) »).
    """
    sources = details.get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    found = []
    for stream in source.get("MediaStreams") or []:
        if not isinstance(stream, dict) or stream.get("Type") != "Subtitle":
            continue
        if stream.get("IsExternal") or not isinstance(stream.get("Index"), int):
            continue
        fmt = _SUB_FORMATS.get(str(stream.get("Codec") or "").lower())
        if fmt is None:
            continue
        code, name = _LANGS.get(str(stream.get("Language") or "").lower(), ("", ""))
        label = name or str(stream.get("DisplayTitle") or stream.get("Title") or "Intégré")
        if stream.get("IsForced"):
            label += " (forcés)"
        found.append({
            "url": subtitle_path(item_id, stream["Index"], fmt[0]),
            "label": label,
            "language": code,
            "mime": fmt[1],
        })  # fmt: skip
    return found


def source_bitrate(details: dict[str, Any]) -> int | None:
    """Débit moyen du fichier en bit/s (MediaSources[0].Bitrate de Jellyfin),
    image et son compris ; None s'il est inconnu.

    Un remux 4K tourne autour de 60 à 100 Mb/s : la TV s'en sert pour
    proposer la qualité réduite quand sa connexion ne suit pas (ADR-012).
    """
    sources = details.get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    bitrate = source.get("Bitrate")
    # bool est un int en Python : écarté, comme un débit nul ou négatif
    if isinstance(bitrate, bool) or not isinstance(bitrate, int) or bitrate <= 0:
        return None
    return bitrate


def source_info(details: dict[str, Any]) -> dict[str, Any]:
    """Extension du fichier et mode de lecture conseillé (direct ou remux).

    Un élément qui n'est pas un simple fichier vidéo (VideoType « Iso »,
    « BluRay », « Dvd ») ou dont l'extension n'est pas lue par la TV passe
    par le remux.
    """
    sources = details.get("MediaSources") or [{}]
    source = sources[0] if isinstance(sources[0], dict) else {}
    path = str(source.get("Path") or details.get("Path") or "")
    ext = path.rsplit(".", 1)[-1].lower() if "." in path.rsplit("/", 1)[-1] else ""
    video_type = str(details.get("VideoType") or source.get("VideoType") or "VideoFile")
    direct = video_type == "VideoFile" and (ext in DIRECT_EXTENSIONS or not ext)
    return {
        "container": ext or str(source.get("Container") or ""),
        "mode": "direct" if direct else "remux",
    }


def strip_api_key(playlist: str) -> str:
    """Retire « ApiKey=… » / « api_key=… » des adresses d'une liste HLS."""

    def repl(m: re.Match[str]) -> str:
        # « ?ApiKey=x&a=1 » → « ?a=1 » ; « a=1&ApiKey=x&b=2 » → « a=1&b=2 » ;
        # en fin d'adresse (« ?ApiKey=x », « &ApiKey=x ») → rien
        sep, amp = m.group(1), m.group(3)
        return sep if amp else ""

    return _KEY_IN_URL.sub(repl, playlist)


def parse_chapters(item_id: str, raw: Any) -> list[dict[str, Any]]:
    """Chapitres Jellyfin → [{index, name, start, image}] (début en secondes).

    image : adresse relayée de la vignette, ou None si Jellyfin n'en a pas
    extrait (option « Extraire les images des chapitres » de la bibliothèque).
    """
    chapters = []
    for index, chapter in enumerate(raw or []):
        if not isinstance(chapter, dict):
            continue
        try:
            start = int(chapter.get("StartPositionTicks") or 0) / jellyfin.TICKS_PER_SECOND
        except (TypeError, ValueError):
            continue
        chapters.append({
            "index": index,
            "name": str(chapter.get("Name") or f"Chapitre {index + 1}"),
            "start": round(start, 3),
            "image": chapter_image_path(item_id, index) if chapter.get("ImageTag") else None,
        })  # fmt: skip
    return chapters


TRICKPLAY_WIDTH = 320  # largeur de vignette préférée (lisible au-dessus de la barre)


def parse_trickplay(item_id: str, raw: Any) -> dict[str, Any] | None:
    """Vignettes de la barre de lecture (« trickplay » de Jellyfin 10.9+) → format de la TV.

    Jellyfin range une vignette toutes les `Interval` ms, assemblées en
    planches de TileWidth × TileHeight (une image JPEG = jusqu'à 100
    vignettes) : la TV télécharge une planche et y découpe la vignette de
    l'instant visé. None si Jellyfin ne les a pas générées (option
    « Activer l'extraction des images trickplay » de la bibliothèque).
    """
    if not isinstance(raw, dict) or not raw:
        return None
    # Une entrée par version du fichier (MediaSourceId) : celle de l'élément, sinon la première
    per_source = raw.get(item_id) or next(iter(raw.values()))
    if not isinstance(per_source, dict):
        return None
    options = []
    for width_key, info in per_source.items():
        try:
            width = int(width_key)
            entry = {
                "width": int(info.get("Width") or width),
                "height": int(info.get("Height") or 0),
                "tile_width": int(info.get("TileWidth") or 0),
                "tile_height": int(info.get("TileHeight") or 0),
                "count": int(info.get("ThumbnailCount") or 0),
                "interval": int(info.get("Interval") or 0) / 1000,
            }
        except (AttributeError, TypeError, ValueError):
            continue
        if min(entry.values()) <= 0:
            continue
        options.append((width, entry))
    if not options:
        return None
    # La plus proche de 320 px (Jellyfin en propose souvent 320, parfois 480…)
    width, entry = min(options, key=lambda pair: abs(pair[0] - TRICKPLAY_WIDTH))
    return {**entry, "url": trickplay_path(item_id, width)}


def duration_seconds(item: dict[str, Any]) -> int:
    try:
        return int(int(item.get("RunTimeTicks") or 0) / jellyfin.TICKS_PER_SECOND)
    except (TypeError, ValueError):
        return 0


async def _item_details(base: str, key: str, item_id: str) -> dict[str, Any] | None:
    params = {jellyfin.KEY_PARAM: key, "ids": item_id, "fields": _FIELDS}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{base}/Items?{urlencode(params)}")
        r.raise_for_status()
        items = r.json().get("Items") or []
    return items[0] if items else None


async def _resume(db: AsyncSession, key: str) -> dict[str, Any]:
    """Reprise et « vu » partagés (les mêmes que les TV sous Kodi)."""
    from app.models.watch_state import WatchState

    row = (await db.execute(select(WatchState).where(WatchState.key == key))).scalars().first()
    if row is None:
        return {"position": 0, "watched": False}
    return {"position": int(row.position or 0), "watched": bool(row.watched)}


def _found(item_id: str, details: dict[str, Any] | None, resume: dict[str, Any]) -> dict[str, Any]:
    details = details or {}
    source = source_info(details)
    image = video_range(details)
    return {
        "status": "ok",
        "item_id": item_id,
        "title": details.get("Name"),
        "overview": details.get("Overview"),
        "duration": duration_seconds(details),
        # Flux conseillé, et le remux en secours (la TV y bascule si le direct échoue)
        "mode": source["mode"],
        "container": source["container"],
        "stream": stream_path(item_id) if source["mode"] == "direct" else hls_path(item_id),
        "remux_stream": hls_path(item_id),
        # Dolby Vision sans secours HDR10 : la TV sans DV lit plutôt sdr_stream.
        # Proposé pour tout élément : la TV y bascule aussi si elle découvre
        # elle-même un profil 5 que Jellyfin n'a pas signalé.
        "video_range": image["video_range"],
        "dovi_only": image["dovi_only"],
        "sdr_stream": sdr_path(item_id),
        # Débit moyen du fichier (bit/s, None : inconnu) : la TV propose le
        # 1080p (sdr_stream) quand il coupe sur un réseau trop lent
        "bitrate": source_bitrate(details),
        "chapters": parse_chapters(item_id, details.get("Chapters")),
        # Aperçu en image quand on avance / recule (None : pas généré par Jellyfin)
        "trickplay": parse_trickplay(item_id, details.get("Trickplay")),
        "resume": resume,
        # Sous-titres posés à côté du fichier (.fr.srt de Bazarr…) : le lecteur
        # ne voit que les pistes du MKV, on les lui ajoute
        "subtitles": external_subtitles(item_id, details),
        # Pistes intégrées, extraites par Jellyfin seulement pour être décalées
        "embedded_subtitles": embedded_subtitles(item_id, details),
    }


async def movie(db: AsyncSession, tmdb_id: int, profile_id: int | None = None) -> dict[str, Any]:
    """Tout ce qu'il faut pour lancer un film (TMDB)."""
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "reason": "Jellyfin non configuré"}
    base, key = cfg
    item = await jellyfin.find_movie_item(db, tmdb_id)
    if item is None:
        return {"status": "not_found", "reason": "Film absent de Jellyfin"}
    details = await _item_details(base, key, item["id"])
    resume = await _resume(
        db, profiled_key(watch_sync.state_key("movie", "tmdb", str(tmdb_id)), profile_id)
    )
    return _found(item["id"], details, resume)


async def movie_trailer(db: AsyncSession, tmdb_id: int) -> dict[str, Any]:
    """Bande-annonce locale d'un film (fichier « -trailer » rangé par Radarr,
    connu de Jellyfin), lue en fond sur la fiche par la TV.

    TMDB ne donne que des liens YouTube, que la TV ne peut pas lire en fond :
    seules les bandes-annonces présentes sur le NAS servent ici.
    """
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "none"}
    base, key = cfg
    item = await jellyfin.find_movie_item(db, tmdb_id)
    if item is None:
        return {"status": "none"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{base}/Items/{item['id']}/LocalTrailers?{urlencode({jellyfin.KEY_PARAM: key})}"
            )
            r.raise_for_status()
            trailers = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.debug("Bandes-annonces locales de %s : %s", item["id"], exc)
        return {"status": "none"}
    if isinstance(trailers, dict):  # certaines versions emballent la liste
        trailers = trailers.get("Items") or []
    for trailer in trailers if isinstance(trailers, list) else []:
        trailer_id = str(trailer.get("Id") or "")
        if ITEM_ID.match(trailer_id):
            return {
                "status": "ok",
                "item_id": trailer_id,
                "stream": stream_path(trailer_id),
                "duration": duration_seconds(trailer),
            }
    return {"status": "none"}


async def episode(
    db: AsyncSession, tvdb_id: int, season: int, number: int, profile_id: int | None = None
) -> dict[str, Any]:
    """Tout ce qu'il faut pour lancer un épisode (TVDB de la série + numéros)."""
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "reason": "Jellyfin non configuré"}
    base, key = cfg
    item = await jellyfin.find_episode_item(db, tvdb_id, season, number)
    if item is None:
        return {"status": "not_found", "reason": "Épisode absent de Jellyfin"}
    details = await _item_details(base, key, item["id"])
    resume = await _resume(
        db,
        profiled_key(
            watch_sync.state_key("episode", "tvdb", str(tvdb_id), season, number), profile_id
        ),
    )
    result = _found(item["id"], details, resume)
    segments = await jellyfin.episode_segments(db, tvdb_id, season, number)
    result["segments"] = segments.get("segments") or []
    return result


# ── Épisodes d'une saison (écran Série) ─────────────────────────────────────


def parse_episodes(items: Any) -> list[dict[str, Any]]:
    """Épisodes Jellyfin → [{season, episode, episode_end, item_id, title,
    overview, runtime, image}] triés ; image = vignette relayée ou None."""
    episodes = []
    for it in items or []:
        if not isinstance(it, dict) or not isinstance(it.get("IndexNumber"), int):
            continue
        item_id = str(it.get("Id") or "")
        if not ITEM_ID.match(item_id):
            continue
        has_image = bool((it.get("ImageTags") or {}).get("Primary"))
        end = it.get("IndexNumberEnd")
        episodes.append({
            "season": it.get("ParentIndexNumber"),
            "episode": it["IndexNumber"],
            "episode_end": end if isinstance(end, int) else None,
            "item_id": item_id,
            "title": it.get("Name"),
            "overview": it.get("Overview"),
            "runtime": duration_seconds(it),
            "image": item_image_path(item_id) if has_image else None,
        })  # fmt: skip
    return sorted(episodes, key=lambda e: e["episode"])


async def season_episodes(db: AsyncSession, tvdb_id: int, season: int) -> dict[str, Any]:
    """Épisodes présents dans Jellyfin pour une saison : vignettes, résumés, durées.

    L'écran Série croise cette liste avec Sonarr (épisodes manquants, à
    venir) et les états vu / reprise partagés.
    """
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "unavailable", "episodes": []}
    base, key = cfg
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            index = await jellyfin._series_index(client, base, key)
            series_id = index.get(str(tvdb_id))
            if series_id is None:
                index = await jellyfin._series_index(client, base, key, refresh=True)
                series_id = index.get(str(tvdb_id))
            if series_id is None:
                return {"status": "ok", "found": False, "episodes": []}
            params = {
                jellyfin.KEY_PARAM: key,
                "season": season,
                "fields": "Overview",
                "enableImageTypes": "Primary",
            }
            r = await client.get(f"{base}/Shows/{series_id}/Episodes?{urlencode(params)}")
            r.raise_for_status()
            items = r.json().get("Items")
    except httpx.HTTPError as exc:
        logger.debug("Épisodes Jellyfin TVDB %s S%s : %s", tvdb_id, season, exc)
        return {"status": "error", "episodes": []}
    episodes = [e for e in parse_episodes(items) if e["season"] == season]
    return {"status": "ok", "found": True, "episodes": episodes}


# ── Relais du flux vidéo ─────────────────────────────────────────────────────


class UpstreamError(Exception):
    """Jellyfin a refusé ou n'a pas répondu (code HTTP à renvoyer à la TV)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def _relay(
    url: str, range_header: str | None, label: str
) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
    """Ouvre une adresse Jellyfin et la relaie morceau par morceau.

    Rend (code HTTP, en-têtes à recopier, flux d'octets). Le « Range » de la
    TV est transmis tel quel : Jellyfin répond 206 avec le morceau demandé,
    c'est ce qui rend l'avance rapide instantanée.
    """
    headers = {"Range": range_header} if range_header else {}
    # Pas de délai de lecture : un film en pause peut laisser la connexion
    # inactive longtemps (et un remux met quelques secondes à démarrer).
    # Délai de connexion court : Jellyfin est sur le LAN.
    client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None))
    try:
        upstream = await client.send(client.build_request("GET", url, headers=headers), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.warning("Relais vidéo %s : Jellyfin injoignable (%s)", label, type(exc).__name__)
        raise UpstreamError(502, "Jellyfin injoignable") from exc

    if upstream.status_code >= 400:
        status_code = upstream.status_code
        await upstream.aclose()
        await client.aclose()
        raise UpstreamError(404 if status_code == 404 else 502, f"Jellyfin a répondu {status_code}")

    forwarded = {k: v for k, v in upstream.headers.items() if k.lower() in _FORWARDED}

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            # TV qui saute ailleurs dans le film ou s'arrête : on referme
            # aussitôt la connexion vers Jellyfin.
            await upstream.aclose()
            await client.aclose()

    return upstream.status_code, forwarded, body()


async def open_stream(
    db: AsyncSession, item_id: str, range_header: str | None
) -> tuple[int, dict[str, str], AsyncIterator[bytes]]:
    """Fichier d'origine (lecture directe), relayé depuis Jellyfin."""
    if not ITEM_ID.match(item_id):
        raise UpstreamError(404, "Élément inconnu")
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    url = f"{base}/Videos/{item_id}/stream?{urlencode({jellyfin.KEY_PARAM: key, 'static': 'true'})}"
    return await _relay(url, range_header, item_id)


# ── Remux HLS (formats que la TV ne lit pas directement) ─────────────────────


def hls_master_params(item_id: str) -> dict[str, str]:
    """Paramètres du remux : image copiée telle quelle (HEVC, HDR, Dolby
    Vision gardés), son copié s'il tient dans le conteneur, sinon converti en
    Dolby Digital Plus (jusqu'en 7.1)."""
    return {
        "MediaSourceId": item_id,
        "DeviceId": HLS_DEVICE,
        "PlaySessionId": f"arrmada-{item_id}",
        "VideoCodec": "hevc,h264,av1,vp9",
        "AudioCodec": "eac3,ac3,aac,flac,mp3,opus",
        "AllowVideoStreamCopy": "true",
        "AllowAudioStreamCopy": "true",
        "EnableAutoStreamCopy": "true",
        "RequireAvc": "false",
        "SegmentContainer": "mp4",
        "BreakOnNonKeyFrames": "true",
        "TranscodingMaxAudioChannels": "8",
        "MaxStreamingBitrate": "250000000",
    }


def hls_sdr_params(item_id: str) -> dict[str, str]:
    """Paramètres de la conversion SDR : image réencodée en H.264 SDR 1080p.

    Le H.264 n'existe qu'en SDR : Jellyfin applique donc son mappage tonal
    (Tableau de bord › Lecture › Transcodage › « Activer le mappage tonal »).
    Pour le Dolby Vision profil 5, ce mappage demande l'accélération
    matérielle (Intel QSV / VAAPI, NVIDIA…) : sans elle, l'image resterait
    violette. 1080p : quatre fois moins de calcul que la 4K, conversion
    tenable en temps réel. Le son est copié tel quel quand c'est possible.

    Sert aussi de qualité réduite choisie à la TV (menu pause › Qualité,
    ADR-012) : 20 Mb/s passent sur un lien à 100 Mb/s ou en Wi-Fi.
    """
    return {
        **hls_master_params(item_id),
        "VideoCodec": "h264",
        "AllowVideoStreamCopy": "false",
        "h264-rangetype": "SDR",
        "h264-profile": "high",
        "h264-level": "51",
        "MaxWidth": "1920",
        "MaxHeight": "1080",
        "VideoBitrate": "20000000",
        "MaxStreamingBitrate": "30000000",
    }


async def open_hls(
    db: AsyncSession, item_id: str, path: str, query: str, range_header: str | None
) -> tuple[int, dict[str, str], AsyncIterator[bytes] | bytes]:
    """Relaie une liste HLS (clé retirée) ou un morceau du remux Jellyfin.

    [query] : paramètres tels que la TV les a reçus dans les listes de
    Jellyfin (sans la clé) ; la clé est ajoutée ici.
    """
    if not ITEM_ID.match(item_id) or not HLS_PATH.match(path):
        raise UpstreamError(404, "Élément inconnu")
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    if path in ("master.m3u8", "sdr.m3u8"):
        # Liste principale : paramètres décidés ici, jamais par la TV.
        # « sdr.m3u8 » n'existe pas chez Jellyfin : c'est sa master.m3u8,
        # demandée avec les paramètres de la conversion SDR.
        chosen = hls_sdr_params(item_id) if path == "sdr.m3u8" else hls_master_params(item_id)
        params = urlencode({**chosen, jellyfin.KEY_PARAM: key})
        path = "master.m3u8"
    else:
        clean = strip_api_key("?" + query).lstrip("?&") if query else ""
        params = "&".join(p for p in (clean, urlencode({jellyfin.KEY_PARAM: key})) if p)
    url = f"{base}/Videos/{item_id}/{path}?{params}"

    if path.endswith(".m3u8"):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.get(url)
        except httpx.HTTPError as exc:
            raise UpstreamError(502, "Jellyfin injoignable") from exc
        if r.status_code >= 400:
            raise UpstreamError(
                404 if r.status_code == 404 else 502, f"Jellyfin a répondu {r.status_code}"
            )
        playlist = strip_api_key(r.text).encode()
        return 200, {"content-type": "application/vnd.apple.mpegurl"}, playlist
    return await _relay(url, range_header, f"{item_id}/{path}")


async def stop_hls(db: AsyncSession, item_id: str) -> None:
    """Arrête le remux en cours chez Jellyfin (la TV a quitté la lecture)."""
    if not ITEM_ID.match(item_id):
        return
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return
    base, key = cfg
    params = {
        jellyfin.KEY_PARAM: key,
        "DeviceId": HLS_DEVICE,
        "PlaySessionId": f"arrmada-{item_id}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(f"{base}/Videos/ActiveEncodings?{urlencode(params)}")
    except httpx.HTTPError as exc:
        logger.debug("Arrêt du remux %s : %s", item_id, exc)


# ── Sous-titres externes (relais, téléchargement par Bazarr) ────────────────


async def open_subtitle(
    db: AsyncSession, item_id: str, index: int, ext: str, shift_ms: int = 0
) -> tuple[bytes, str]:
    """Sous-titre (externe, ou intégré au fichier) converti par Jellyfin en
    UTF-8, relayé à la TV ; [shift_ms] : copie décalée (réglage du menu pause)."""
    from app.services import subtitle_shift

    if not ITEM_ID.match(item_id) or ext not in SUB_MIME or not 0 <= index <= 999:
        raise UpstreamError(404, "Sous-titre inconnu")
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    url = f"{base}/Videos/{item_id}/{item_id}/Subtitles/{index}/0/Stream.{ext}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{url}?{urlencode({jellyfin.KEY_PARAM: key})}")
    except httpx.HTTPError as exc:
        raise UpstreamError(502, "Jellyfin injoignable") from exc
    if r.status_code >= 400:
        raise UpstreamError(404, "Sous-titre absent")
    content = r.content
    if shift_ms:
        text = subtitle_shift.shift(content.decode("utf-8-sig", errors="replace"), ext, shift_ms)
        content = text.encode("utf-8")
    return content, f"{SUB_MIME[ext]}; charset=utf-8"


async def _refresh_item(base: str, key: str, item_id: str) -> None:
    """Demande à Jellyfin de relire le dossier de l'élément (nouveaux .srt)."""
    params = {
        jellyfin.KEY_PARAM: key,
        "MetadataRefreshMode": "Default",
        "ImageRefreshMode": "None",
        "ReplaceAllMetadata": "false",
        "ReplaceAllImages": "false",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{base}/Items/{item_id}/Refresh?{urlencode(params)}")


# Recherches Bazarr qui continuent après la réponse à la TV (gardées ici pour
# qu'elles ne soient pas interrompues en route)
_PENDING: set[asyncio.Task[Any]] = set()

# Budget d'une demande de la TV (elle attend 45 s au plus) : recherche Bazarr,
# puis relecture du dossier par Jellyfin
BAZARR_WAIT = 25.0
JELLYFIN_WAIT = 12.0
POLL_EVERY = 2.0


async def download_subtitles(
    db: AsyncSession, item_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Menu pause → « Sous-titres français » : Bazarr cherche et télécharge,
    Jellyfin relit le dossier, la TV reçoit la liste des sous-titres externes.

    [data] : {media_type: movie|episode, tmdb_id | tvdb_id, season, episode,
    language}. Statuts : ok (nouveau sous-titre), none (rien trouvé),
    pending (Bazarr cherche encore : réessayer dans une minute), error.
    """
    from app.services import kodi

    if not ITEM_ID.match(item_id):
        return {"status": "error", "message": "Élément inconnu", "subtitles": []}
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "error", "message": "Jellyfin non configuré", "subtitles": []}
    base, key = cfg
    language = str(data.get("language") or "fr").lower()[:3]

    before = external_subtitles(item_id, await _item_details(base, key, item_id) or {})
    known = {s["url"] for s in before}

    # Bazarr peut chercher longtemps (plusieurs fournisseurs) : on l'attend un
    # temps raisonnable, il finit seul au-delà
    task = asyncio.create_task(
        kodi.handle_addon_subtitles(db, {**data, "language": language, "origin": "android"})
    )
    _PENDING.add(task)
    task.add_done_callback(_PENDING.discard)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), BAZARR_WAIT)
    except TimeoutError:
        result = {"status": "pending"}
    if result.get("status") == "error":
        return {"status": "error", "message": result.get("message"), "subtitles": before}

    # Jellyfin relit le dossier : le nouveau .srt devient un sous-titre externe
    after = before
    try:
        await _refresh_item(base, key, item_id)
        waited = 0.0
        while waited < JELLYFIN_WAIT:
            await asyncio.sleep(POLL_EVERY)
            waited += POLL_EVERY
            after = external_subtitles(item_id, await _item_details(base, key, item_id) or {})
            if any(s["url"] not in known for s in after):
                break
    except httpx.HTTPError as exc:
        logger.debug("Relecture Jellyfin de %s : %s", item_id, exc)

    added = [s for s in after if s["url"] not in known]
    if added:
        names = ", ".join(s["label"].removesuffix(" · fichier") for s in added)
        return {"status": "ok", "message": f"Sous-titres ajoutés : {names}", "subtitles": after}
    if result.get("status") == "pending":
        message = "Bazarr cherche encore : réessaie dans une minute"
        return {"status": "pending", "message": message, "subtitles": after}
    return {
        "status": "none",
        "message": f"Aucun nouveau sous-titre {language.upper()} trouvé par Bazarr",
        "subtitles": after,
    }


# Resynchronisation par Bazarr (ffsubsync, calée sur le son) : 30 s à 2 min
# pour un film. La TV attend 45 s au plus ; au-delà, Bazarr finit seul.
SYNC_WAIT = 35.0


async def sync_subtitles(db: AsyncSession, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Menu pause → « Resynchro auto » : Bazarr recale le sous-titre externe
    (français par défaut) sur la piste son, puis la TV le recharge.

    ffsubsync corrige un décalage constant ou une dérive régulière ; un
    décalage qui apparaît d'un coup en plein film (sous-titre d'une autre
    version) se règle à la main (−/+ 0,5 s). Statuts : ok, pending, error.
    """
    from app.services import kodi

    if not ITEM_ID.match(item_id):
        return {"status": "error", "message": "Élément inconnu", "subtitles": []}
    cfg = await jellyfin.get_config(db)
    if not cfg:
        return {"status": "error", "message": "Jellyfin non configuré", "subtitles": []}
    base, key = cfg
    language = str(data.get("language") or "fr").lower()[:3]
    task = asyncio.create_task(
        kodi.handle_addon_sync_subtitles(db, {**data, "language": language, "origin": "android"})
    )
    _PENDING.add(task)
    task.add_done_callback(_PENDING.discard)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), SYNC_WAIT)
    except TimeoutError:
        result = {"status": "pending"}
    subtitles = external_subtitles(item_id, await _item_details(base, key, item_id) or {})
    if result.get("status") == "error":
        return {"status": "error", "message": result.get("message"), "subtitles": subtitles}
    if result.get("status") == "pending":
        message = "Resynchro en cours (Bazarr) : relance dans une minute pour la voir"
        return {"status": "pending", "message": message, "subtitles": subtitles}
    return {
        "status": "ok",
        "message": "Sous-titres resynchronisés sur le son",
        "subtitles": subtitles,
    }


async def _image(db: AsyncSession, path: str, resize: bool = True) -> tuple[bytes, str]:
    """Image relayée depuis Jellyfin ; `resize` : réduite à 480 px (pas une planche trickplay)."""
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    params: dict[str, Any] = {jellyfin.KEY_PARAM: key}
    if resize:
        params.update({"maxWidth": 480, "quality": 85})
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base}{path}?{urlencode(params)}")
    except httpx.HTTPError as exc:
        raise UpstreamError(502, "Jellyfin injoignable") from exc
    if r.status_code >= 400:
        raise UpstreamError(404, "Vignette absente")
    return r.content, r.headers.get("content-type", "image/jpeg")


async def chapter_image(db: AsyncSession, item_id: str, index: int) -> tuple[bytes, str]:
    """Vignette d'un chapitre (JPEG), relayée depuis Jellyfin."""
    if not ITEM_ID.match(item_id) or not 0 <= index <= 999:
        raise UpstreamError(404, "Vignette inconnue")
    return await _image(db, f"/Items/{item_id}/Images/Chapter/{index}")


async def trickplay_tile(
    db: AsyncSession, item_id: str, width: int, index: int
) -> tuple[bytes, str]:
    """Planche de vignettes trickplay (JPEG), relayée telle quelle (la TV la découpe)."""
    if not ITEM_ID.match(item_id) or not 1 <= width <= 1920 or not 0 <= index <= 9999:
        raise UpstreamError(404, "Planche inconnue")
    return await _image(db, f"/Videos/{item_id}/Trickplay/{width}/{index}.jpg", resize=False)


async def item_image(db: AsyncSession, item_id: str) -> tuple[bytes, str]:
    """Image principale d'un élément (vignette d'un épisode), relayée depuis Jellyfin."""
    if not ITEM_ID.match(item_id):
        raise UpstreamError(404, "Vignette inconnue")
    return await _image(db, f"/Items/{item_id}/Images/Primary")

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
"""

from __future__ import annotations

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
_FIELDS = "Chapters,Overview,MediaSources,ProviderIds,Path"

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
        "chapters": parse_chapters(item_id, details.get("Chapters")),
        "resume": resume,
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


async def _image(db: AsyncSession, path: str) -> tuple[bytes, str]:
    cfg = await jellyfin.get_config(db)
    if not cfg:
        raise UpstreamError(503, "Jellyfin non configuré")
    base, key = cfg
    params = {jellyfin.KEY_PARAM: key, "maxWidth": 480, "quality": 85}
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


async def item_image(db: AsyncSession, item_id: str) -> tuple[bytes, str]:
    """Image principale d'un élément (vignette d'un épisode), relayée depuis Jellyfin."""
    if not ITEM_ID.match(item_id):
        raise UpstreamError(404, "Vignette inconnue")
    return await _image(db, f"/Items/{item_id}/Images/Primary")

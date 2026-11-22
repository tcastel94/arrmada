"""Apple TV comme cible d'envoi : le serveur fait ouvrir le film par VLC.

Pourquoi pas un flux AirPlay, comme pour un Chromecast ? Sous tvOS 27,
l'Apple TV accepte la commande « /play » de pyatv mais ne va jamais
chercher la vidéo (essayé avec un flux Jellyfin et avec la vidéo d'exemple
d'Apple). À la place, le serveur lui demande d'ouvrir un lien
`vlc-x-callback://…` : VLC (gratuit, à installer sur l'Apple TV) lit alors
le fichier d'origine, sans transcodage. Analogie : au lieu de pousser le
film dans le téléviseur, on lui tend l'adresse et il va le chercher.

Deux appairages par code à 4 chiffres, une fois pour toutes :
  - « companion » : lancer une appli avec un lien, lister les applis ;
  - « airplay »   : lire ce qui joue (titre, position), pause / lecture.

Pièges :
  - srptools 2.x casse l'appairage (épinglé à 1.0.1 dans requirements.txt) ;
  - l'Apple TV doit pouvoir joindre le serveur ArrMada : l'adresse du lien
    vient de PUBLIC_WEB_URL, sinon de l'adresse utilisée par le client ;
  - chaque commande ouvre une connexion courte (2 à 3 s) : pas de connexion
    gardée ouverte qui se périmerait quand l'Apple TV se met en veille.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import re
import time
import unicodedata
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from app.services import auth_store
from app.services.encryption import decrypt_api_key, encrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

# tvOS 27 envoie des trames « Companion » d'un type que pyatv 0.18 ne sait pas
# décoder : il écrit alors une pile d'appels entière dans les journaux à chaque
# connexion, sans conséquence (la commande aboutit). On ne garde que le critique.
logging.getLogger("pyatv.protocols.companion.protocol").setLevel(logging.CRITICAL)

KIND = "appletv"
AIRPLAY_PORT = 7000  # ouvert sur toute Apple TV : sert à les repérer sur le réseau
VLC_BUNDLE = "org.videolan.vlc-ios"
PROTOCOLS = ("airplay", "companion")  # ordre des deux appairages

# « Sur la TV » du téléphone (GET /api/tv/targets) n'a qu'un numéro par
# cible : les Apple TV y portent ce décalage pour ne jamais se confondre
# avec une TV appairée (table `devices`).
TARGET_OFFSET = 1_000_000

LINK_TTL = 18 * 3600  # s : durée de validité d'un lien de lecture signé
START_TIMEOUT = 20  # s : délai laissé à VLC pour démarrer la lecture
TRACK_EVERY = 30  # s : relevé de la position pendant la lecture
WATCHED_AT = 0.9  # « vu » à 90 %, comme l'appli Android

_ITEM_ID = re.compile(r"^[0-9a-f]{32}$")


# ── Numéros de cible, liens signés (fonctions pures) ─────────────────────────


def target_id(cast_device_id: int) -> int:
    """Numéro de l'Apple TV dans la liste « Sur la TV »."""
    return TARGET_OFFSET + cast_device_id


def from_target_id(value: int) -> int | None:
    """Numéro de cible → id de `cast_devices`, None si c'est une TV appairée."""
    return value - TARGET_OFFSET if value > TARGET_OFFSET else None


def file_name(title: str | None, suffix: str = ".mkv") -> str:
    """Nom de fichier lisible mis dans le lien : c'est le titre affiché par VLC."""
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9 ()._-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .") or "video"
    suffix = suffix.lower() if re.fullmatch(r"\.[A-Za-z0-9]{2,5}", suffix or "") else ".mkv"
    return f"{text[:80]}{suffix}"


def sign(item_id: str, expires: int) -> str:
    """Signature d'un lien de lecture (HMAC-SHA256 avec le secret du serveur)."""
    secret = auth_store.jwt_secret().encode()
    return hmac.new(secret, f"cast:{item_id}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]


def file_path(
    item_id: str, title: str | None, suffix: str = ".mkv", now: float | None = None
) -> str:
    """Chemin signé du fichier d'origine, lisible sans session (VLC n'en a pas).

    Comme une URL pré-signée S3 : seul un lien fabriqué par le serveur est
    servi, et il expire. La clé Jellyfin ne quitte jamais le serveur.
    """
    expires = int(now if now is not None else time.time()) + LINK_TTL
    return f"/api/cast/file/{expires}/{sign(item_id, expires)}/{item_id}/{quote(file_name(title, suffix))}"


def check_link(item_id: str, expires: int, signature: str, now: float | None = None) -> bool:
    """Le lien vient-il du serveur, et est-il encore valable ?"""
    if not _ITEM_ID.match(item_id or ""):
        return False
    if expires < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(sign(item_id, expires), signature or "")


def subtitle_path(item_id: str, index: int, ext: str, now: float | None = None) -> str:
    """Chemin signé d'un sous-titre posé à côté du fichier (même signature que la vidéo)."""
    expires = int(now if now is not None else time.time()) + LINK_TTL
    return f"/api/cast/subtitle/{expires}/{sign(item_id, expires)}/{item_id}/{index}.{ext}"


def hls_path(item_id: str, audio_index: int, title: str | None, now: float | None = None) -> str:
    """Chemin signé du flux remuxé par Jellyfin avec UNE piste audio choisie.

    Le lien VLC ne sait pas désigner une piste : quand celle qu'on veut n'est
    pas la piste par défaut du fichier, on lui donne un flux qui n'a qu'elle
    (image copiée telle quelle). Le nom final est le titre affiché par VLC.
    """
    expires = int(now if now is not None else time.time()) + LINK_TTL
    name = quote(file_name(title, ".m3u8"))
    return f"/api/cast/hls/{expires}/{sign(item_id, expires)}/{item_id}/{audio_index}/{name}"


def hls_upstream_path(path: str) -> str:
    """Chemin demandé par VLC → chemin du remux chez Jellyfin.

    La liste d'entrée porte le titre du film (« 2 Guns.m3u8 ») : c'est la
    « master.m3u8 » de Jellyfin. Le reste (main.m3u8, morceaux) passe tel quel.
    """
    entry = "/" not in path and path.endswith(".m3u8") and path != "main.m3u8"
    return "master.m3u8" if entry else path


def pick_subtitle(
    subtitles: list[dict[str, str]], audio_language: str, house_language: str
) -> dict[str, str] | None:
    """Sous-titre à joindre au lien VLC pour ce son (voir `plan_tracks`).

    Son étranger → sous-titres complets dans la langue de la maison (les SDH
    à défaut) ; son déjà dans cette langue → seulement les « forcés »
    (dialogues étrangers). VLC affiche d'office le sous-titre joint : mieux
    vaut aucun qu'un mauvais.
    """
    ours = [s for s in subtitles if s.get("language") == house_language]
    forced = [s for s in ours if "(forcés)" in s.get("label", "")]
    if audio_language == house_language:
        return forced[0] if forced else None
    full = [s for s in ours if s not in forced]
    full.sort(key=lambda s: "(SDH)" in s.get("label", ""))
    return full[0] if full else None


def plan_tracks(
    audios: list[dict[str, Any]], subtitles: list[dict[str, str]], house_language: str
) -> dict[str, Any]:
    """Piste audio et sous-titre lus d'office, même règle que l'appli Android :

      1. titre étranger dont le fichier a la VO ET des sous-titres complets
         dans la langue de la maison → VO + ces sous-titres ;
      2. sinon, piste dans la langue de la maison (film français, ou VF faute
         de sous-titres) → cette piste + sous-titres « forcés » s'il y en a ;
      3. sinon → la VO (à défaut la piste par défaut) + sous-titres si possible.

    `audios` : [{index, language, default, original}] dans l'ordre du fichier
    (`original` : la VO d'après Jellyfin). Rend {audio, subtitle, remux} ;
    `remux` vrai : la piste choisie n'est pas celle que VLC lirait de
    lui-même, il faut le flux à une seule piste (`hls_path`).
    """
    original = next((a for a in audios if a.get("original")), None)
    ours = next((a for a in audios if a.get("language") == house_language), None)
    played = next((a for a in audios if a.get("default")), audios[0] if audios else None)
    full = pick_subtitle(subtitles, "", house_language)

    if original and original.get("language") != house_language and full:
        audio = original
    elif ours:
        audio = ours
    else:
        audio = original or played
    language = audio.get("language", "") if audio else ""
    return {
        "audio": audio,
        "subtitle": pick_subtitle(subtitles, language, house_language),
        "remux": audio is not None and audio is not played,
    }


def vlc_link(url: str, subtitle_url: str | None = None) -> str:
    """Lien qui fait lire `url` par VLC (même schéma que sur iPhone).

    `subtitle_url` : sous-titre que VLC télécharge et affiche avec la vidéo
    (vérifié sur tvOS 27 : il vient bien le chercher).
    """
    link = "vlc-x-callback://x-callback-url/stream?url=" + quote(url, safe="")
    return link + ("&sub=" + quote(subtitle_url, safe="") if subtitle_url else "")


def player_state(device_state: str) -> str:
    """État pyatv → état au format Chromecast (celui que connaît la web app)."""
    return {
        "Playing": "PLAYING",
        "Paused": "PAUSED",
        "Loading": "BUFFERING",
        "Seeking": "PLAYING",
    }.get(device_state, "IDLE")


def is_watched(position: int, total: int) -> bool:
    return total > 0 and position >= total * WATCHED_AT


# ── Identifiants d'appairage (chiffrés en base) ──────────────────────────────


def load_credentials(stored: str | None) -> dict[str, str]:
    """Identifiants rangés dans `cast_devices.credentials` → {protocole: identifiants}."""
    if not stored:
        return {}
    try:
        data = json.loads(decrypt_api_key(stored))
    except Exception:  # clé de chiffrement changée, valeur abîmée : à ré-appairer
        return {}
    return {p: str(data[p]) for p in PROTOCOLS if isinstance(data, dict) and data.get(p)}


def dump_credentials(credentials: dict[str, str]) -> str | None:
    kept = {p: credentials[p] for p in PROTOCOLS if credentials.get(p)}
    return encrypt_api_key(json.dumps(kept)) if kept else None


def is_paired(stored: str | None) -> bool:
    return len(load_credentials(stored)) == len(PROTOCOLS)


# ── pyatv : recherche, connexion ─────────────────────────────────────────────


def _protocol(name: str):
    from pyatv.const import Protocol

    return {"airplay": Protocol.AirPlay, "companion": Protocol.Companion}[name]


async def _config(ip: str):
    """Fiche pyatv d'une Apple TV, demandée directement à son adresse.

    La recherche « à la cantonade » (mDNS) ne sort pas d'un conteneur en
    réseau bridge ; interroger l'adresse, si.
    """
    import pyatv

    found = await pyatv.scan(asyncio.get_running_loop(), hosts=[ip], timeout=4)
    return found[0] if found else None


def _describe(conf) -> dict[str, Any] | None:
    """Fiche pyatv → ligne `cast_devices` ; None si ce n'est pas une Apple TV."""
    from pyatv.const import OperatingSystem, Protocol

    info = conf.device_info
    if info.operating_system != OperatingSystem.TvOS or not conf.identifier:
        return None
    airplay = conf.get_service(Protocol.AirPlay)
    return {
        "uuid": str(conf.identifier)[:64],
        "name": conf.name or str(conf.address),
        "ip": str(conf.address),
        "port": airplay.port if airplay else AIRPLAY_PORT,
        "model": f"{info.model_str} · tvOS {info.version}" if info.version else info.model_str,
        "video_capable": True,
        "kind": KIND,
    }


async def identify(ips: list[str]) -> list[dict[str, Any]]:
    """Parmi ces adresses (port AirPlay ouvert), lesquelles sont des Apple TV ?"""
    if not ips:
        return []
    import pyatv

    found = await pyatv.scan(asyncio.get_running_loop(), hosts=ips, timeout=5)
    return [d for d in (_describe(conf) for conf in found) if d]


@contextlib.asynccontextmanager
async def _session(ip: str, credentials: dict[str, str]) -> AsyncIterator[Any]:
    """Connexion courte à l'Apple TV, toujours refermée."""
    import pyatv

    conf = await _config(ip)
    if conf is None:
        raise ConnectionError("Apple TV injoignable (éteinte, ou adresse changée ?)")
    for name, value in credentials.items():
        conf.set_credentials(_protocol(name), value)
    atv = await pyatv.connect(conf, asyncio.get_running_loop())
    try:
        yield atv
    finally:
        with contextlib.suppress(Exception):
            pending = atv.close()
            if pending:
                await asyncio.wait(pending, timeout=2)


def _error(exc: Exception) -> str:
    """Message lisible pour l'utilisateur (pas un nom de classe Python)."""
    name = type(exc).__name__
    if isinstance(exc, ConnectionError | asyncio.TimeoutError | OSError):
        return str(exc) or "Apple TV injoignable (éteinte ?)"
    if name in ("AuthenticationError", "NoCredentialsError", "PairingError"):
        return "Appairage refusé par l'Apple TV : refais l'appairage dans Réglages › Cast."
    if name == "NotSupportedError":
        return "Commande non prise en charge par cette Apple TV."
    return f"Apple TV : {name}"


# ── Appairage par code (deux protocoles à la suite) ──────────────────────────

# Appairages en cours : id de l'appareil → {handler, protocol, credentials, at}.
# En mémoire : un appairage dure le temps de lire 4 chiffres sur la TV.
_pairings: dict[int, dict[str, Any]] = {}
PAIRING_TTL = 300  # s


async def _close_pairing(device_id: int) -> None:
    session = _pairings.pop(device_id, None)
    if session:
        with contextlib.suppress(Exception):
            await session["handler"].close()


async def _begin(
    device_id: int, ip: str, protocol: str, credentials: dict[str, str]
) -> dict[str, Any]:
    """Fait afficher un code sur l'Apple TV pour ce protocole."""
    import pyatv

    conf = await _config(ip)
    if conf is None:
        raise ConnectionError("Apple TV injoignable (éteinte, ou adresse changée ?)")
    handler = await pyatv.pair(conf, _protocol(protocol), asyncio.get_running_loop())
    await handler.begin()
    _pairings[device_id] = {
        "handler": handler,
        "protocol": protocol,
        "credentials": dict(credentials),
        "at": time.monotonic(),
    }
    return {
        "status": "pin",
        "protocol": protocol,
        "step": PROTOCOLS.index(protocol) + 1,
        "steps": len(PROTOCOLS),
    }


async def pair_start(device_id: int, ip: str) -> dict[str, Any]:
    """Démarre (ou recommence) l'appairage : premier code à l'écran de la TV."""
    await _close_pairing(device_id)
    try:
        return await _begin(device_id, ip, PROTOCOLS[0], {})
    except Exception as exc:
        logger.warning("Appairage Apple TV %s : %s", ip, type(exc).__name__)
        await _close_pairing(device_id)
        return {"status": "error", "detail": _error(exc)}


async def pair_pin(device_id: int, ip: str, pin: str) -> dict[str, Any]:
    """Valide le code lu sur la TV ; enchaîne sur le protocole suivant.

    Rend {status: "pin", …} (un autre code s'affiche), {status: "paired",
    credentials: {…}} (terminé, à enregistrer) ou {status: "error"}.
    """
    session = _pairings.get(device_id)
    if not session or time.monotonic() - session["at"] > PAIRING_TTL:
        await _close_pairing(device_id)
        return {"status": "error", "detail": "Appairage expiré : relance-le."}
    if not re.fullmatch(r"\d{4}", pin or ""):
        return {"status": "error", "detail": "Le code fait 4 chiffres."}
    handler, protocol = session["handler"], session["protocol"]
    try:
        handler.pin(int(pin))
        await handler.finish()
        if not handler.has_paired:
            raise PermissionError("code refusé")
        credentials = {**session["credentials"], protocol: handler.service.credentials}
    except Exception as exc:
        logger.warning("Appairage Apple TV (%s) refusé : %s", protocol, type(exc).__name__)
        await _close_pairing(device_id)
        return {"status": "error", "detail": "Code refusé par l'Apple TV. Relance l'appairage."}
    await _close_pairing(device_id)

    remaining = [p for p in PROTOCOLS if p not in credentials]
    if not remaining:
        return {"status": "paired", "credentials": credentials}
    try:
        return await _begin(device_id, ip, remaining[0], credentials)
    except Exception as exc:
        await _close_pairing(device_id)
        return {"status": "error", "detail": _error(exc)}


# ── Lecture, commandes, état ─────────────────────────────────────────────────


async def _playing(atv) -> dict[str, Any]:
    playing = await atv.metadata.playing()
    app = atv.metadata.app
    return {
        "app": app.name if app else None,
        "app_id": app.identifier if app else None,
        "player_state": player_state(playing.device_state.name),
        "title": playing.title,
        "current_time": playing.position,
        "duration": playing.total_time,
    }


async def play(
    ip: str, credentials: dict[str, str], url: str, subtitle_url: str | None = None
) -> dict[str, Any]:
    """Fait lire `url` par VLC sur l'Apple TV ; attend que la lecture démarre."""
    try:
        async with _session(ip, credentials) as atv:
            apps = await atv.apps.app_list()
            if not any(app.identifier == VLC_BUNDLE for app in apps):
                return {
                    "status": "error",
                    "detail": "VLC n'est pas installé sur cette Apple TV (gratuit sur l'App Store).",
                }
            await atv.apps.launch_app(vlc_link(url, subtitle_url))
            state: dict[str, Any] = {}
            for _ in range(START_TIMEOUT // 2):
                await asyncio.sleep(2)
                state = await _playing(atv)
                if state["app_id"] == VLC_BUNDLE and state["player_state"] in ("PLAYING", "PAUSED"):
                    return {"status": "casting", "player_state": state["player_state"]}
            opened = state.get("app_id") == VLC_BUNDLE
            return {
                "status": "error",
                "player_state": state.get("player_state"),
                "detail": "VLC s'est ouvert mais la lecture n'a pas démarré : l'Apple TV "
                "joint-elle le serveur ArrMada (PUBLIC_WEB_URL) ?"
                if opened
                else "VLC ne s'est pas ouvert sur l'Apple TV.",
            }
    except Exception as exc:
        logger.error("Lecture sur l'Apple TV %s : %s", ip, exc)
        return {"status": "error", "detail": _error(exc)}


async def control(
    ip: str, credentials: dict[str, str], action: str, value: Any = None
) -> dict[str, Any]:
    """pause | play | stop | quit | volume (0 à 1)."""
    if action == "mute":
        return {"status": "error", "detail": "Le son se coupe sur la TV ou l'ampli."}
    if action not in ("pause", "play", "stop", "quit", "volume"):
        return {"status": "error", "detail": f"action inconnue: {action}"}
    try:
        async with _session(ip, credentials) as atv:
            remote = atv.remote_control
            if action == "pause":
                await remote.pause()
            elif action == "play":
                await remote.play()
            elif action == "volume":
                await atv.audio.set_volume(max(0.0, min(1.0, float(value))) * 100)
            else:  # stop / quit : on arrête puis on rend l'écran d'accueil
                last: dict[str, Any] = {}
                with contextlib.suppress(Exception):
                    last = await _playing(atv)  # position au moment de l'arrêt
                if action == "stop":
                    with contextlib.suppress(Exception):
                        await remote.stop()
                    await asyncio.sleep(0.5)
                await remote.home()
                if last.get("app_id") == VLC_BUNDLE:
                    return {
                        "status": "ok",
                        "action": action,
                        "current_time": last.get("current_time"),
                        "duration": last.get("duration"),
                    }
        return {"status": "ok", "action": action}
    except Exception as exc:
        logger.error("Commande %s sur l'Apple TV %s : %s", action, ip, exc)
        detail = (
            "Le volume se règle sur la TV ou l'ampli."
            if action == "volume" and type(exc).__name__ == "NotSupportedError"
            else _error(exc)
        )
        return {"status": "error", "detail": detail}


async def status(ip: str, credentials: dict[str, str]) -> dict[str, Any]:
    try:
        async with _session(ip, credentials) as atv:
            out = await _playing(atv)
            out.pop("app_id")
            volume = None
            with contextlib.suppress(Exception):
                volume = atv.audio.volume / 100
            return {**out, "volume_level": volume, "volume_muted": None}
    except Exception as exc:
        return {"status": "error", "detail": _error(exc)}


# ── Suivi de la lecture : reprise et « vu » partagés ─────────────────────────

_trackers: dict[int, asyncio.Task[None]] = {}
# Flux remuxé en cours par Apple TV (id Jellyfin) : à arrêter chez Jellyfin
# quand la lecture se termine, sinon ffmpeg continue pour rien.
_remuxes: dict[int, str] = {}

# Avancement d'un flux remuxé, déduit de ce que VLC vient chercher. Pendant un
# tel flux, tvOS 27 cesse au bout d'une quinzaine de secondes de dire ce que VLC
# lit (appli « aucune », état « Idle ») alors que la lecture continue : la
# seule trace fiable est la suite des morceaux demandés au serveur.
# id Jellyfin → {starts: début de chaque morceau (s), total, segment, at}
_progress: dict[str, dict[str, Any]] = {}
BUFFER_AHEAD = 35  # s : avance de VLC sur l'image (mesurée : il charge ~6 morceaux d'avance)
REMUX_IDLE = 90  # s sans morceau demandé : en pause, ou lecture terminée
_SEGMENT = re.compile(r"^hls1/[A-Za-z0-9_]+/(-?\d+)\.(?:mp4|m4s|ts)$")


def note_playlist(item_id: str, playlist: str) -> None:
    """Liste des morceaux relayée à VLC : retient où commence chacun."""
    starts, clock = [], 0.0
    for line in playlist.splitlines():
        if line.startswith("#EXTINF:"):
            starts.append(clock)
            with contextlib.suppress(ValueError):
                clock += float(line[8:].split(",")[0])
    if starts:
        _progress[item_id] = {
            "starts": starts,
            "total": clock,
            "segment": 0,
            "at": time.monotonic(),
        }


def note_segment(item_id: str, path: str) -> None:
    """Morceau demandé par VLC : c'est là qu'en est son chargement."""
    state, match = _progress.get(item_id), _SEGMENT.match(path)
    if state and match:
        index = int(match.group(1))
        if 0 <= index < len(state["starts"]):
            state["segment"], state["at"] = index, time.monotonic()


def remux_position(item_id: str, now: float | None = None) -> tuple[int, int, bool]:
    """(position estimée, durée, lecture en cours ?) d'un flux remuxé.

    Estimation à une trentaine de secondes près : début du dernier morceau
    demandé, moins l'avance que VLC garde en mémoire, plus le temps écoulé
    depuis. Assez pour « reprendre vers 42 min » sur une autre TV.
    """
    state = _progress.get(item_id)
    if not state:
        return 0, 0, False
    idle = (now if now is not None else time.monotonic()) - state["at"]
    position = state["starts"][state["segment"]] - BUFFER_AHEAD + min(idle, REMUX_IDLE)
    total = int(state["total"])
    return max(0, min(int(position), total)), total, idle < REMUX_IDLE


# Titre en cours par Apple TV : (état sans position, nom de l'appareil)
_tracked: dict[int, tuple[dict[str, Any], str]] = {}


def watch_state(media: dict[str, Any], position: int, total: int, now: datetime) -> dict[str, Any]:
    """État vu / reprise au format de `watch_sync.store` (celui des TV)."""
    watched = is_watched(position, total)
    return {
        **media,
        "watched": watched,
        "position": 0 if watched else position,
        "total": total,
        "last_played": now.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
    }


async def _save(media: dict[str, Any], position: int, total: int, device_name: str) -> None:
    from app.database import async_session_factory
    from app.services import watch_sync
    from app.utils.event_bus import event_bus

    async with async_session_factory() as db:
        changed, _ = await watch_sync.store(
            db, [watch_state(media, position, total, datetime.now(UTC))], False, device_name
        )
    if changed:
        await event_bus.publish(
            event_type="watch_state",
            data={
                "changed": len(changed),
                "device": device_name,
                "cursor": changed[-1]["updated_at"].isoformat(),
                "profile_id": None,
            },
        )


async def _track(
    ip: str,
    credentials: dict[str, str],
    media: dict[str, Any],
    device_name: str,
    remux_item: str | None = None,
) -> None:
    """Relève la position toutes les 30 s tant que VLC lit ; s'arrête sinon.

    Fichier d'origine : l'Apple TV dit ce que VLC lit ; deux relevés de suite
    sans lecture (film fini, autre appli, TV éteinte) et le suivi s'arrête.
    Flux remuxé : elle ne le dit plus (voir `_progress`), on suit les morceaux
    demandés ; une pause ressemble alors à un arrêt, d'où dix minutes de
    patience avant de conclure. La dernière position connue reste.
    """
    misses, deadline = 0, time.monotonic() + 8 * 3600
    patience = 20 if remux_item else 2
    while misses < patience and time.monotonic() < deadline:
        await asyncio.sleep(TRACK_EVERY)
        if remux_item:
            position, total, active = remux_position(remux_item)
        else:
            try:
                async with _session(ip, credentials) as atv:
                    state = await _playing(atv)
            except Exception:
                misses += 1
                continue
            active = state["app_id"] == VLC_BUNDLE and state["player_state"] != "IDLE"
            position, total = int(state["current_time"] or 0), int(state["duration"] or 0)
        if not active or total <= 0:
            misses += 1
            continue
        misses = 0
        try:
            await _save(media, position, total, device_name)
        except Exception as exc:  # le suivi ne doit jamais gêner la lecture
            logger.warning("Suivi Apple TV : état non enregistré (%s)", type(exc).__name__)


async def _stop_remux(item_id: str) -> None:
    from app.database import async_session_factory
    from app.services import tv_playback

    with contextlib.suppress(Exception):
        async with async_session_factory() as db:
            await tv_playback.stop_hls(db, item_id)


async def _track_then_clean(
    device_id: int, ip: str, credentials: dict[str, str], media: dict[str, Any], device_name: str
) -> None:
    """Suivi de la lecture, puis arrêt du remux si la lecture s'est finie d'elle-même."""
    await _track(ip, credentials, media, device_name, _remuxes.get(device_id))
    item_id = _remuxes.pop(device_id, None)
    if item_id:
        _progress.pop(item_id, None)
        await _stop_remux(item_id)


def start_tracking(
    device_id: int,
    ip: str,
    credentials: dict[str, str],
    media: dict[str, Any],
    device_name: str,
    remux_item: str | None = None,
) -> None:
    """Lance le suivi d'une lecture (remplace celui en cours sur cette Apple TV).

    `remux_item` : la lecture passe par un flux remuxé de cet élément Jellyfin.
    """
    stop_tracking(device_id)
    if remux_item:
        _remuxes[device_id] = remux_item
    task = asyncio.create_task(_track_then_clean(device_id, ip, credentials, media, device_name))
    _trackers[device_id] = task
    _tracked[device_id] = (media, device_name)

    def _done(finished: asyncio.Task[None]) -> None:
        if _trackers.get(device_id) is finished:
            _trackers.pop(device_id, None)
            _tracked.pop(device_id, None)

    task.add_done_callback(_done)


def stop_tracking(device_id: int) -> None:
    task = _trackers.pop(device_id, None)
    _tracked.pop(device_id, None)
    if task and not task.done():
        task.cancel()


async def finish_tracking(device_id: int, position: Any, total: Any) -> None:
    """Arrêt demandé depuis ArrMada : enregistre la position exacte, puis fin du suivi."""
    tracked = _tracked.get(device_id)
    stop_tracking(device_id)
    item_id = _remuxes.pop(device_id, None)
    if item_id:
        # Flux remuxé : ce que l'Apple TV dit de la position n'est pas fiable
        # (souvent rien ; mesuré une fois : 55 s annoncées pour 2 min de
        # lecture). L'estimation par les morceaux demandés l'emporte.
        estimated, length, _ = remux_position(item_id)
        if length > 0:
            position, total = estimated, length
        _progress.pop(item_id, None)
        await _stop_remux(item_id)
    try:
        position, total = int(position or 0), int(total or 0)
    except (TypeError, ValueError):
        return
    if tracked and position > 0 and total > 0:
        with contextlib.suppress(Exception):
            await _save(tracked[0], position, total, tracked[1])

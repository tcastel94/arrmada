"""Écran d'appoint du salon : tout ce que la tablette affiche, en une requête.

La tablette (Pixel Tablet sous la TV, navigateur Fully Kiosk) affiche la page
`/ecran` de la web app. Elle est appairée comme une TV, avec un jeton
« écran » (deux routes : celle-ci, et la télécommande tactile de la lecture
en cours de SA pièce, `POST /api/ambient/command`). Toutes les 10 s (5 s
pendant une lecture), elle demande :

  - la lecture en cours dans SA pièce (titre, épisode, affiche, position,
    durée, début de la séance), d'après le suivi de lecture des TV ;
  - l'ampli de la pièce (marche, volume, entrée, programme) ;
  - les téléchargements en cours ;
  - ce qui sort ce soir et demain (calendrier) ;
  - quand rien ne passe : « Ce soir » (reprendre, Ma liste, nouveaux films),
    chaque titre se lance sur la TV de la pièce d'un toucher
    (`POST /api/ambient/play`, voir services/ambient_tonight.py).

Chaque bloc est indépendant : un ampli éteint ou un Sonarr en panne ne vide
pas le reste de l'écran. Petits caches (5 s à 5 min) : dix tablettes ne
feraient pas dix fois les appels aux services.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.device import AMP_ROOMS, ROOMS, Device
from app.services import ambient_tonight, watch_summary, watch_sync
from app.services.now_playing import now_playing
from app.services.tv_remote import InvalidCommand, clean_command, remote_queue
from app.utils.cache import cache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ambient", tags=["ambient"])

ROOM_LABELS = {"salon": "Salon", "cinema": "Salle de cinéma", "bureau": "Bureau"}
MAX_DOWNLOADS = 3
MAX_UPCOMING = 4


def web_image(value: Any) -> str:
    """Adresse d'image affichable par un navigateur (http/https), sinon "".

    Kodi peut connaître des images locales (smb://, special://, chemin du
    NAS) : la tablette ne saurait pas les ouvrir, on prend alors celles de la
    médiathèque.
    """
    text = str(value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def playing_view(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """Lecture en cours au format de l'écran (sans les champs internes)."""
    if not state:
        return None
    season, episode = state.get("season"), state.get("episode")
    is_episode = state.get("media_type") == "episode" or (
        isinstance(season, int) and isinstance(episode, int)
    )
    label = ""
    if isinstance(season, int) and isinstance(episode, int):
        label = f"S{season:02d}E{episode:02d}"
    subtitle = " · ".join(
        part for part in (label, str(state.get("episode_title") or "").strip()) if part
    )
    if not is_episode and state.get("year"):
        subtitle = str(state["year"])
    return {
        "title": state.get("title") or "",
        "subtitle": subtitle,
        "kind": "episode" if is_episode else "movie",
        "poster": web_image(state.get("poster")),
        "fanart": web_image(state.get("fanart")),
        "state": state.get("state") or "playing",
        "position": float(state.get("position") or 0),
        "duration": float(state.get("duration") or 0),
        "updated_at": float(state.get("updated_at") or 0),
        "started_at": float(state.get("started_at") or 0),
        "device": state.get("device_name") or "",
        # Appli Android : formats, pistes, chapitre, intro / générique,
        # épisode suivant, fiche, télécommande (absents avec Kodi)
        "video": state.get("video") or "",
        "audio": state.get("audio") or "",
        "subtitle_track": state.get("subtitle_track") or "",
        "chapter": state.get("chapter") or "",
        "next_up": state.get("next_up") or "",
        "credits_at": float(state.get("credits_at") or 0),
        "skips": state.get("skips") or [],
        "overview": state.get("overview") or "",
        "meta_line": state.get("meta_line") or "",
        "cast": [{**c, "photo": web_image(c.get("photo"))} for c in state.get("cast") or []],
        "subtitle_tracks": state.get("subtitle_tracks") or [],
        "audio_tracks": state.get("audio_tracks") or [],
        "remote": bool(state.get("remote")),
        # Outils sous-titres de la tablette (Bazarr, resynchro, décalage)
        "subtitle_tools": bool(state.get("subtitle_tools")),
        "subtitle_busy": bool(state.get("subtitle_busy")),
        "subtitle_note": state.get("subtitle_note") or "",
        "subtitle_shift_ms": int(state.get("subtitle_shift_ms") or 0),
    }


async def _artwork(db: AsyncSession, state: dict[str, Any]) -> dict[str, str]:
    """Affiche et fond depuis la médiathèque, si la TV n'en a pas envoyé.

    Film : identifiant TMDB (fourni par Kodi), sinon le titre ; série : le titre.
    """
    from app.services.media_aggregator import find_artwork

    media_type = "movie" if state.get("media_type") == "movie" else "series"
    if state.get("media_type") not in ("movie", "episode", "series"):
        media_type = None
    ref = state.get("tmdb_id") if media_type == "movie" else None
    return await find_artwork(db, media_type, tmdb_id=ref, title=state.get("title"))


async def _amp(db: AsyncSession, avr_service_id: int | None) -> dict[str, Any] | None:
    from app.services import yamaha as yamaha_service

    async def _fetch():
        return await yamaha_service.get_state(db, avr_service_id)

    try:
        state = await cache.get_or_set(f"ambient:amp:{avr_service_id}", _fetch, ttl_seconds=5)
    except Exception as exc:
        logger.debug("[Ambient] ampli : %s", exc)
        return None
    device = next((d for d in state.get("devices") or [] if d.get("online")), None)
    if device is None:
        return None
    return {
        "name": device.get("name") or "Ampli",
        "power": device.get("power") or "",
        "volume_pct": device.get("volume_pct"),
        "mute": bool(device.get("mute")),
        "input": device.get("input") or "",
        "sound_program": device.get("sound_program") or "",
    }


async def _downloads(db: AsyncSession) -> list[dict[str, Any]]:
    from app.services import media_aggregator

    async def _fetch():
        return await media_aggregator.get_queue_items(db)

    try:
        items = await cache.get_or_set("ambient:queue", _fetch, ttl_seconds=20)
    except Exception as exc:
        logger.debug("[Ambient] file : %s", exc)
        return []
    active = [
        item
        for item in items or []
        if str(item.get("status") or "").lower() in ("downloading", "queued", "delay", "paused")
    ]
    active.sort(key=lambda item: -float(item.get("progress") or 0))
    return [
        {
            "title": item.get("title") or "Téléchargement",
            "progress": round(float(item.get("progress") or 0)),
            "time_left": item.get("time_left") or "",
            "paused": str(item.get("status") or "").lower() == "paused",
        }
        for item in active[:MAX_DOWNLOADS]
    ]


async def _upcoming(db: AsyncSession) -> list[dict[str, Any]]:
    """Sorties d'aujourd'hui et de demain (même cache que la page Calendrier)."""
    from app.api.calendar import _fetch_calendar_data

    today = datetime.now(UTC).date()
    start, end = today.isoformat(), (today + timedelta(days=2)).isoformat()

    async def _fetch():
        return await _fetch_calendar_data(db, start, end, False)

    try:
        items = await cache.get_or_set(f"calendar:{start}:{end}:monitored", _fetch, ttl_seconds=300)
    except Exception as exc:
        logger.debug("[Ambient] calendrier : %s", exc)
        return []
    rows = [item for item in items or [] if item.get("air_date") and not item.get("has_file")]
    rows.sort(key=lambda item: str(item.get("air_date")))
    return [
        {
            "title": item.get("title") or "",
            "label": item.get("label") or "",
            "subtitle": item.get("subtitle") or "",
            "air_date": item.get("air_date"),
            "kind": "episode" if item.get("type") == "episode" else "movie",
            # Films : digital | physical | cinema (sortie numérique, Blu-ray, salle)
            "release_type": item.get("release_type") or "",
        }
        for item in rows[:MAX_UPCOMING]
    ]


async def _tonight(db: AsyncSession) -> dict[str, list[dict[str, Any]]]:
    """« Ce soir » (profil Famille, celui des TV), gardé 60 s pour toutes les tablettes."""
    from app.services import watchlist

    async def _fetch():
        summary = await watch_summary.load_summary(db)
        library = await watchlist._library(db)  # médiathèque en cache, [] si *arr en panne
        items = await watchlist.list_items(db, None)
        return ambient_tonight.build(summary, library, items, datetime.now(UTC))

    try:
        return await cache.get_or_set("ambient:tonight", _fetch, ttl_seconds=60)
    except Exception as exc:
        logger.debug("[Ambient] ce soir : %s", exc)
        return {"resume": [], "watchlist": [], "fresh": []}


@router.get("")
async def ambient(
    room: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Tout l'écran d'appoint. Un écran appairé voit SA pièce ; la web app choisit (`room`)."""
    if user.get("role") == "device":
        room = user.get("room") or "salon"
        avr = user.get("avr_service_id")
    else:
        avr = None
    room = room if room in ROOMS else "salon"
    now = time.time()
    state = now_playing.current(room, now)
    if state and not (web_image(state.get("poster")) and web_image(state.get("fanart"))):
        art = await _artwork(db, state)
        state["poster"] = web_image(state.get("poster")) or art["poster"]
        state["fanart"] = web_image(state.get("fanart")) or art["fanart"]
    return {
        "server_time": now,
        "room": room,
        "room_label": ROOM_LABELS.get(room, room),
        "playing": playing_view(state),
        # Calculé seulement entre deux lectures (inutile pendant un film)
        "tonight": None if state else await _tonight(db),
        # Bureau : pas d'ampli (sinon l'écran montrerait celui du salon)
        "amp": await _amp(db, avr) if room in AMP_ROOMS else None,
        "downloads": await _downloads(db),
        "upcoming": await _upcoming(db),
    }


# Volume de l'ampli depuis la tablette : seules ces deux actions, bornées
# (pas d'entrée, pas de mise en veille, pas de programme sonore)
AMP_ACTIONS = {"volume_step", "mute"}
MAX_VOLUME_STEP = 10  # pas YXC (0 à 161) : ±10 ≈ ±6 % par appui


async def _amp_command(db: AsyncSession, room: str, avr: int | None, data: dict) -> dict[str, Any]:
    """Volume ± / sourdine de l'ampli de la pièce, appliqués par le serveur."""
    from app.services import yamaha

    if room not in AMP_ROOMS:
        raise HTTPException(status_code=409, detail="Pas d'ampli dans cette pièce")
    action, value = data.get("action"), data.get("value")
    if action == "volume_step":
        try:
            step = int(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Pas de volume invalide") from exc
        if step == 0 or abs(step) > MAX_VOLUME_STEP:
            raise HTTPException(status_code=422, detail="Pas de volume hors bornes")
        value = step
    else:
        value = bool(value)
    result = await yamaha.control(db, str(action), value, service_id=avr)
    if result.get("status") != "ok":
        raise HTTPException(status_code=502, detail=result.get("detail") or "Ampli injoignable")
    cache.invalidate(f"ambient:amp:{avr}")  # la tablette voit le nouveau volume au relevé suivant
    return {"status": "ok"}


@router.get("/person/{person_id}")
async def person(person_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Filmographie d'un acteur (fiche du film, tablette) : ses films présents
    dans la médiathèque d'abord (mis en avant), puis les autres (TMDB)."""
    from app.services.people import get_person_filmography

    if not 0 < person_id < 100_000_000:
        raise HTTPException(status_code=404, detail="Acteur inconnu")

    async def _fetch() -> dict[str, Any]:
        return await get_person_filmography(db, person_id)

    # Une heure : la filmographie ne bouge pas pendant une séance
    data = await cache.get_or_set(f"ambient:person:{person_id}", _fetch, ttl_seconds=3600)
    if data.get("person"):
        data = {
            **data,
            "person": {
                **data["person"],
                "biography": (data["person"].get("biography") or "")[:700],
            },
        }
    return data


@router.post("/command")
async def command(
    data: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """Télécommande tactile : pause, ±30 s, passer l'intro, pistes, volume…

    Un écran appairé ne pilote que SA pièce ; la web app (aperçu) choisit
    `room`. Volume et sourdine vont directement à l'ampli de la pièce ; le
    reste va à la TV, et est refusé s'il n'y a rien en lecture ou si la TV ne
    sait pas recevoir de commandes (Kodi) : la tablette n'affiche alors pas
    les boutons.
    """
    if user.get("role") == "device":
        room = user.get("room") or "salon"
        avr = user.get("avr_service_id")
    else:
        room = str((data or {}).get("room") or "salon")
        avr = None
    if room not in ROOMS:
        raise HTTPException(status_code=422, detail="Pièce inconnue")
    if (data or {}).get("action") in AMP_ACTIONS:
        return await _amp_command(db, room, avr, data or {})
    state = now_playing.current(room, time.time())
    if not state or not state.get("remote"):
        raise HTTPException(status_code=409, detail="Aucune lecture pilotable dans cette pièce")
    try:
        cleaned = clean_command((data or {}).get("action"), (data or {}).get("value"))
    except InvalidCommand as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    entry = await remote_queue.push(room, cleaned)
    return {"status": "ok", "id": entry["id"]}


async def _room_tv(db: AsyncSession, room: str) -> Device | None:
    """TV de la pièce : la dernière à s'être manifestée (plusieurs : la plus récente)."""
    rows = (
        (await db.execute(select(Device).where(Device.kind == "tv", Device.room == room)))
        .scalars()
        .all()
    )
    if not rows:
        return None
    epoch = datetime.min.replace(tzinfo=UTC)
    return max(
        rows,
        key=lambda d: watch_sync.as_utc(d.last_seen_at) if d.last_seen_at else epoch,
    )


@router.post("/play")
async def play(
    data: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict[str, Any]:
    """« Ce soir » : lance un titre proposé sur la TV de la pièce de la tablette.

    Garde-fous : la tablette ne peut lancer QUE ce qu'elle affiche (titres de
    « Ce soir », vérifiés côté serveur), sur la TV de SA pièce, et seulement
    quand rien n'y passe déjà. Même mécanisme que « Lire sur la TV » de la web
    app : un événement `play_request` adressé à cette TV.
    """
    payload = data or {}
    if user.get("role") == "device":
        room = user.get("room") or "salon"
    else:
        room = str(payload.get("room") or "salon")
    if room not in ROOMS:
        raise HTTPException(status_code=422, detail="Pièce inconnue")
    if now_playing.current(room, time.time()):
        raise HTTPException(status_code=409, detail="Une lecture est déjà en cours")

    try:
        wanted = ambient_tonight.play_key(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Titre à lire invalide") from exc
    if wanted not in ambient_tonight.offered(await _tonight(db)):
        raise HTTPException(status_code=422, detail="Titre non proposé sur cet écran")

    device = await _room_tv(db, room)
    if device is None:
        raise HTTPException(status_code=409, detail="Aucune TV appairée dans cette pièce")
    now = datetime.now(UTC)
    request = watch_summary.play_request(
        {"id": device.id, "name": device.name, "room": device.room},
        # Seulement les champs connus (pas de « file » : pas de vidéo de dossier ici)
        {k: payload.get(k) for k in ("media_type", "id", "season", "episode", "title", "resume")},
        now,
    )
    if request is None or request["media_type"] not in ("movie", "episode"):
        raise HTTPException(status_code=422, detail="Titre à lire invalide")

    from app.services.activity_log import log_event
    from app.utils.event_bus import event_bus

    await event_bus.publish(event_type="play_request", data=request)
    code = (
        f" S{request['season']:02d}E{request['episode']:02d}"
        if request["media_type"] == "episode"
        else ""
    )
    await log_event(
        category="playback",
        action="play_on_device",
        source="arrmada",
        subtitle="Depuis la tablette",
        media_type=request["media_type"],
        tmdb_id=int(request["id"]) if request["id_type"] == "tmdb" else None,
        title=f"{request['title']}{code}" or None,
        device=device.name,
    )
    return {
        "status": "sent",
        "device": device.name,
        "online": watch_summary.is_online(device.last_seen_at, now),
    }

"""Lecture dans l'appli Android native (ADR-007) : infos de lecture et flux relayé."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import appletv, jellyfin, library_hints, tv_playback, watch_summary
from app.services import cast as cast_service
from app.utils.event_bus import event_bus

router = APIRouter(
    prefix="/api/tv",
    tags=["tv"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/remote")
async def remote(after: int = -1, user: dict = Depends(get_current_user)) -> dict:
    """Commandes de la tablette pour la TV de cette pièce (attente jusqu'à 15 s).

    Appelée en boucle par la TV pendant une lecture ; `after` : dernier
    numéro de commande reçu (−1 au premier appel : juste le curseur).
    """
    from app.services.tv_remote import remote_queue

    return await remote_queue.wait(user.get("room") or "salon", after)


@router.get("/play/movie/{tmdb_id}")
async def play_movie(
    tmdb_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Film à lancer : adresse du flux relayé, durée, chapitres, reprise (du profil)."""
    return await tv_playback.movie(db, tmdb_id, user.get("profile_id"))


@router.get("/trailer/movie/{tmdb_id}")
async def movie_trailer(tmdb_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Bande-annonce locale (NAS) d'un film, lue en fond sur sa fiche."""
    return await tv_playback.movie_trailer(db, tmdb_id)


@router.get("/play/episode/{tvdb_id}/{season}/{episode}")
async def play_episode(
    tvdb_id: int,
    season: int,
    episode: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Épisode à lancer : comme un film, plus les marqueurs intro / récap / générique."""
    return await tv_playback.episode(db, tvdb_id, season, episode, user.get("profile_id"))


@router.get("/track-preference/{scope}")
async def get_track_preference(
    scope: str, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Dernier choix de pistes du profil pour cette série / ce film (« series:tvdb:280619 »)."""
    from app.services import track_preferences

    if not track_preferences.valid_scope(scope):
        raise HTTPException(status_code=400, detail="Titre inconnu")
    return await track_preferences.get(db, user.get("profile_id"), scope)


@router.post("/track-preference/{scope}")
async def set_track_preference(
    scope: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Piste changée dans le menu pause : reprise à l'épisode suivant, pour ce profil."""
    from app.services import track_preferences

    if not track_preferences.valid_scope(scope):
        raise HTTPException(status_code=400, detail="Titre inconnu")
    return await track_preferences.store(db, user.get("profile_id"), scope, body)


# Appli Android sur un téléphone ou une tablette : appairée comme une TV
# (même périmètre de jeton), mais ce n'est pas un écran où envoyer un film.
# Repérée au nom de plateforme qu'elle envoie à l'appairage.
_HANDHELD_MARKS = ("(téléphone)", "(tablette)")


def _is_tv_screen(device) -> bool:
    platform = device.platform or ""
    return device.kind == "tv" and not any(mark in platform for mark in _HANDHELD_MARKS)


@router.get("/targets")
async def play_targets(
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """TV de la maison où envoyer un titre (« Sur la TV » du téléphone), sauf soi-même."""
    from app.models.device import Device

    now = datetime.now(UTC)
    rows = (
        await db.execute(select(Device).where(Device.kind == "tv").order_by(Device.name))
    ).scalars()
    items = [
        {
            "id": d.id,
            "name": d.name,
            "room": d.room,
            "online": watch_summary.is_online(d.last_seen_at, now),
            "kind": "tv",
        }
        for d in rows
        if d.id != user.get("device_id") and _is_tv_screen(d)
    ]
    # Apple TV appairées (lecture par VLC) : numéro décalé pour ne pas se
    # confondre avec une TV ; « online » vrai faute de pouvoir le savoir
    # sans les interroger une à une.
    for apple_tv in await cast_service.list_devices(db):
        if apple_tv["kind"] == appletv.KIND and apple_tv["paired"]:
            items.append(
                {
                    "id": appletv.target_id(apple_tv["id"]),
                    "name": apple_tv["name"],
                    "room": "",
                    "online": True,
                    "kind": appletv.KIND,
                }
            )
    return {"items": items}


@router.post("/targets/{device_id}/play")
async def play_on_target(
    device_id: int,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    """Envoie un film ou un épisode sur une TV (même événement que « Lire sur la TV » de la web app).

    Corps : {media_type, id (TMDB d'un film / TVDB d'une série), season,
    episode, title, resume}. La TV visée le reçoit dans les 5 s.
    """
    from app.models.device import Device

    apple_tv_id = appletv.from_target_id(device_id)
    if apple_tv_id is not None:
        return await _play_on_apple_tv(db, request, apple_tv_id, data or {})
    device = await db.get(Device, device_id)
    if device is None or not _is_tv_screen(device) or device.id == user.get("device_id"):
        raise HTTPException(status_code=404, detail="TV inconnue (appairée ?)")
    now = datetime.now(UTC)
    request = watch_summary.play_request(
        {"id": device.id, "name": device.name, "room": device.room}, data or {}, now
    )
    if request is None:
        raise HTTPException(status_code=422, detail="Titre à lire invalide")
    # Fichier présent sur le NAS ? La TV distingue alors « pas encore
    # téléchargé » de « absent de SA médiathèque Kodi » (source à ajouter)
    request = await library_hints.with_file_status(db, request)
    await event_bus.publish(event_type="play_request", data=request)
    return {
        "status": "ok",
        "online": watch_summary.is_online(device.last_seen_at, now),
        "message": f"Envoyé sur {device.name}",
    }


async def _play_on_apple_tv(db: AsyncSession, request: Request, device_id: int, data: dict) -> dict:
    """« Sur la TV » vers une Apple TV : VLC y ouvre le fichier d'origine.

    Même corps que pour une TV ({media_type, id, season, episode, title}) ;
    `resume` est ignoré : le lien VLC ne sait pas démarrer en cours de film.
    """
    from app.api.cast import send_to_apple_tv
    from app.services import watch_sync

    media = watch_sync.normalize(
        {
            "media_type": data.get("media_type"),
            "id_type": "tmdb" if data.get("media_type") == "movie" else "tvdb",
            "id": data.get("id"),
            "season": data.get("season"),
            "episode": data.get("episode"),
            "title": data.get("title"),
        }
    )
    if media is None or media["media_type"] not in ("movie", "episode"):
        raise HTTPException(status_code=422, detail="Titre à lire invalide")
    try:
        external_id = int(media["external_id"])
    except ValueError:
        raise HTTPException(status_code=422, detail="Titre à lire invalide") from None
    if media["media_type"] == "movie":
        stream = await jellyfin.build_movie_stream(db, external_id)
    else:
        stream = await jellyfin.build_episode_stream(
            db, external_id, media["season"], media["episode"]
        )
    if not stream:
        raise HTTPException(status_code=404, detail="Titre introuvable dans Jellyfin")
    state = {
        "media_type": media["media_type"],
        "id_type": media["id_type"],
        "id": media["external_id"],
        "season": media["season"],
        "episode": media["episode"],
        "title": stream.get("title") or media["title"],
    }
    result = await send_to_apple_tv(db, request, device_id, stream, state)
    if result.get("status") != "casting":
        raise HTTPException(status_code=502, detail=result.get("detail") or "Lecture impossible")
    name = next(
        (d["name"] for d in await cast_service.list_devices(db) if d["id"] == device_id),
        "l'Apple TV",
    )
    return {"status": "ok", "online": True, "message": f"Lecture lancée sur {name} (VLC)"}


@router.get("/series/{tvdb_id}/season/{season}")
async def season(tvdb_id: int, season: int, db: AsyncSession = Depends(get_db)) -> dict:
    """Épisodes d'une saison présents dans Jellyfin (vignette, résumé, durée)."""
    return await tv_playback.season_episodes(db, tvdb_id, season)


@router.get("/subtitle/{item_id}/{index}.{ext}")
async def subtitle(
    item_id: str, index: int, ext: str, shift: int = 0, db: AsyncSession = Depends(get_db)
) -> Response:
    """Sous-titre (externe ou intégré) en UTF-8 ; `shift` : décalé de N ms (±10 min)."""
    try:
        content, media_type = await tv_playback.open_subtitle(db, item_id, index, ext, shift)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(content, headers={"Content-Type": media_type})


@router.post("/subtitles/{item_id}/sync")
async def sync_subtitles(item_id: str, data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    """Menu pause : Bazarr recale le sous-titre sur le son (ffsubsync), 45 s au plus."""
    return await tv_playback.sync_subtitles(db, item_id, data or {})


@router.post("/subtitles/{item_id}")
async def download_subtitles(item_id: str, data: dict, db: AsyncSession = Depends(get_db)) -> dict:
    """Menu pause : Bazarr cherche des sous-titres (français par défaut), la
    TV reçoit la liste à jour des sous-titres externes (45 s au plus)."""
    return await tv_playback.download_subtitles(db, item_id, data or {})


@router.get("/stream/{item_id}")
async def stream(item_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Fichier vidéo d'origine, relayé depuis Jellyfin (avance rapide par « Range »)."""
    try:
        status_code, headers, body = await tv_playback.open_stream(
            db, item_id, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return StreamingResponse(body, status_code=status_code, headers=headers)


@router.get("/hls/{item_id}/{path:path}")
async def hls(item_id: str, path: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Remux HLS de Jellyfin (formats que la TV ne lit pas directement)."""
    try:
        status_code, headers, body = await tv_playback.open_hls(
            db, item_id, path, request.url.query, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    if isinstance(body, bytes):
        return Response(body, status_code=status_code, headers=headers)
    return StreamingResponse(body, status_code=status_code, headers=headers)


@router.post("/hls/{item_id}/stop")
async def hls_stop(item_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """La TV quitte la lecture : Jellyfin arrête le remux."""
    await tv_playback.stop_hls(db, item_id)
    return {"status": "ok"}


@router.get("/chapter-image/{item_id}/{index}")
async def chapter_image(item_id: str, index: int, db: AsyncSession = Depends(get_db)) -> Response:
    """Vignette d'un chapitre (menu pause)."""
    try:
        content, media_type = await tv_playback.chapter_image(db, item_id, index)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    # Une vignette ne change pas : la TV peut la garder une journée.
    return Response(
        content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/trickplay/{item_id}/{width}/{index}")
async def trickplay(
    item_id: str, width: int, index: int, db: AsyncSession = Depends(get_db)
) -> Response:
    """Planche de vignettes de la barre de lecture (aperçu quand on avance)."""
    try:
        content, media_type = await tv_playback.trickplay_tile(db, item_id, width, index)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    # Les vignettes d'un fichier ne changent pas : gardées une journée par la TV
    return Response(
        content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"}
    )


@router.get("/item-image/{item_id}")
async def item_image(item_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    """Vignette d'un épisode (écran Série)."""
    try:
        content, media_type = await tv_playback.item_image(db, item_id)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return Response(
        content, media_type=media_type, headers={"Cache-Control": "private, max-age=86400"}
    )

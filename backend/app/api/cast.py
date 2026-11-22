"""Cast API — Chromecast (flux Jellyfin transcodé) et Apple TV (fichier d'origine lu par VLC)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.api.devices import web_base_url
from app.models.service import Service
from app.services import appletv, tv_playback
from app.services import cast as cast_service
from app.services import jellyfin as jellyfin_service
from app.services.activity_log import log_event
from app.services.encryption import encrypt_api_key

router = APIRouter(
    prefix="/api/cast",
    tags=["cast"],
    dependencies=[Depends(get_current_user)],
)

# Sans session : VLC (sur l'Apple TV) n'en a pas. Seuls les liens signés par
# le serveur sont servis (services/appletv.py : file_path / check_link).
public_router = APIRouter(prefix="/api/cast", tags=["cast"])


@public_router.get("/file/{expires}/{signature}/{item_id}/{name}")
async def signed_file(
    expires: int,
    signature: str,
    item_id: str,
    name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Fichier vidéo d'origine pour VLC, relayé depuis Jellyfin (« Range » transmis).

    `name` n'est là que pour VLC, qui l'affiche comme titre.
    """
    if not appletv.check_link(item_id, expires, signature):
        raise HTTPException(status_code=403, detail="Lien de lecture invalide ou expiré")
    try:
        status_code, headers, body = await tv_playback.open_stream(
            db, item_id, request.headers.get("range"), warm=False
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return StreamingResponse(body, status_code=status_code, headers=headers)


@public_router.get("/subtitle/{expires}/{signature}/{item_id}/{index}.{ext}")
async def signed_subtitle(
    expires: int,
    signature: str,
    item_id: str,
    index: int,
    ext: str,
    db: AsyncSession = Depends(get_db),
):
    """Sous-titre posé à côté du fichier (.srt de Bazarr), joint au lien VLC."""
    if not appletv.check_link(item_id, expires, signature):
        raise HTTPException(status_code=403, detail="Lien de lecture invalide ou expiré")
    try:
        content, media_type = await tv_playback.open_subtitle(db, item_id, index, ext)
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    return Response(content, media_type=media_type)


@public_router.get("/hls/{expires}/{signature}/{item_id}/{audio}/{path:path}")
async def signed_hls(
    expires: int,
    signature: str,
    item_id: str,
    audio: int,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Flux remuxé par Jellyfin avec la piste audio `audio`, pour VLC.

    Les listes de Jellyfin ont des adresses relatives : VLC redemande
    main.m3u8 et les morceaux sous ce même préfixe signé.
    """
    if not appletv.check_link(item_id, expires, signature) or not 0 <= audio <= 999:
        raise HTTPException(status_code=403, detail="Lien de lecture invalide ou expiré")
    upstream = appletv.hls_upstream_path(path)
    query = f"audio={audio}" if upstream == "master.m3u8" else request.url.query
    try:
        status_code, headers, body = await tv_playback.open_hls(
            db, item_id, upstream, query, request.headers.get("range")
        )
    except tv_playback.UpstreamError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    # Seule trace de l'avancement pendant un flux remuxé (appletv._progress)
    if upstream == "main.m3u8" and isinstance(body, bytes):
        appletv.note_playlist(item_id, body.decode("utf-8", errors="replace"))
    else:
        appletv.note_segment(item_id, upstream)
    if isinstance(body, bytes):
        return Response(body, status_code=status_code, headers=headers)
    return StreamingResponse(body, status_code=status_code, headers=headers)


async def send_to_apple_tv(
    db: AsyncSession,
    request: Request,
    device_id: int,
    stream: dict[str, Any],
    media: dict[str, Any],
) -> dict[str, Any]:
    """Lance sur une Apple TV le titre résolu dans Jellyfin (`stream`).

    Partagé par le bouton « Caster » de la web app et par « Sur la TV » du
    téléphone. L'adresse du lien est celle du serveur vue du réseau local.
    """
    item_id, base = stream["item_id"], web_base_url(request)
    source = await tv_playback.vlc_source(db, item_id)
    title, audio = stream.get("title") or media.get("title"), source["audio_index"]
    # Bonne piste audio déjà lue d'office : le fichier d'origine. Sinon le
    # flux remuxé qui ne porte qu'elle (image intacte).
    path = (
        appletv.file_path(item_id, title, source["suffix"])
        if audio is None
        else appletv.hls_path(item_id, audio, title)
    )
    subtitle = source["subtitle"]
    subtitle_url = (
        base + appletv.subtitle_path(item_id, subtitle["index"], subtitle["ext"])
        if subtitle
        else None
    )
    return await cast_service.play_on_apple_tv(
        db, device_id, f"{base}{path}", media, subtitle_url, item_id if audio is not None else None
    )


@router.get("/devices")
async def devices(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """List known Cast devices."""
    return await cast_service.list_devices(db)


@router.post("/discover")
async def discover(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Scan the LAN for Cast devices (TCP :8009 + connect) and persist them."""
    return await cast_service.discover(db)


@router.delete("/devices/{device_id}")
async def delete_device(device_id: int, db: AsyncSession = Depends(get_db)):
    return await cast_service.delete_device(db, device_id)


@router.post("/appletv/{device_id}/pair")
async def pair_apple_tv(device_id: int, db: AsyncSession = Depends(get_db)):
    """Démarre l'appairage : un code à 4 chiffres s'affiche sur l'Apple TV."""
    return await cast_service.pair_start(db, device_id)


@router.post("/appletv/{device_id}/pin")
async def pin_apple_tv(device_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    """Valide le code lu sur la TV. Deux codes à la suite (`status: "pin"`
    tant qu'il en reste un, puis `"paired"`)."""
    return await cast_service.pair_pin(db, device_id, str((data or {}).get("pin") or "").strip())


@router.post("/play")
async def play(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """Cast a movie (TMDB id) or an episode (series TVDB id + season + episode)
    to a device: Jellyfin transcoded stream (Chromecast) or original file
    opened by VLC (Apple TV)."""
    tmdb_id = data.get("tmdb_id")
    tvdb_id, season, episode = data.get("tvdb_id"), data.get("season"), data.get("episode")
    device_id = data.get("device_id")
    is_episode = not tmdb_id and tvdb_id and season is not None and episode is not None
    if not device_id or not (tmdb_id or is_episode):
        return {
            "status": "error",
            "detail": "device_id et tmdb_id (film) ou tvdb_id + season + episode requis",
        }

    if is_episode:
        stream = await jellyfin_service.build_episode_stream(
            db, int(tvdb_id), int(season), int(episode)
        )
        missing = "Épisode introuvable dans Jellyfin (ou Jellyfin non configuré)."
    else:
        stream = await jellyfin_service.build_movie_stream(db, int(tmdb_id))
        missing = "Film introuvable dans Jellyfin (ou Jellyfin non configuré)."
    if not stream:
        return {"status": "error", "detail": missing}

    dev = await cast_service._get(db, int(device_id))
    if dev and dev.kind == appletv.KIND:
        media = {
            "media_type": "episode" if is_episode else "movie",
            "id_type": "tvdb" if is_episode else "tmdb",
            "id": str(tvdb_id if is_episode else tmdb_id),
            "season": season if is_episode else None,
            "episode": episode if is_episode else None,
            "title": stream["title"] or data.get("title") or "",
        }
        result = await send_to_apple_tv(db, request, dev.id, stream, media)
    else:
        result = await cast_service.cast_stream(
            db,
            int(device_id),
            stream["url"],
            stream["content_type"],
            stream["title"] or data.get("title"),
        )

    ok = result.get("status") == "casting"
    await log_event(
        category="playback",
        action="cast_play",
        status="ok" if ok else "ko",
        source="arrmada",
        media_type="episode" if is_episode else "movie",
        media_id=data.get("media_id"),
        tmdb_id=None if is_episode else int(tmdb_id),
        title=stream.get("title") or data.get("title"),
        device=dev.name if dev else None,
        detail=None if ok else result.get("detail"),
        meta={"jellyfin_item": stream.get("item_id")} if ok else None,
    )
    return result


@router.post("/control")
async def control(data: dict, db: AsyncSession = Depends(get_db)):
    """Control a casting device: pause | play | stop | quit | volume | mute."""
    device_id = data.get("device_id")
    action = data.get("action")
    if not device_id or not action:
        return {"status": "error", "detail": "device_id et action requis"}
    return await cast_service.control(db, int(device_id), action, data.get("value"))


@router.get("/status")
async def status(device_id: int, db: AsyncSession = Depends(get_db)):
    """Read what a device is currently playing."""
    return await cast_service.status(db, device_id)


# ── Jellyfin config (backing store for cast streams) ───────────


@router.get("/jellyfin")
async def get_jellyfin(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Service).where(Service.type == "jellyfin"))
    svc = res.scalars().first()
    if not svc:
        return {"configured": False}
    return {
        "configured": True,
        "id": svc.id,
        "name": svc.name,
        "url": svc.url,
        "is_enabled": svc.is_enabled,
    }


@router.post("/jellyfin")
async def set_jellyfin(data: dict, db: AsyncSession = Depends(get_db)):
    """Configure the Jellyfin server (idempotent by type)."""
    url = (data.get("url") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    if not url:
        return {"status": "error", "detail": "url requise"}

    res = await db.execute(select(Service).where(Service.type == "jellyfin"))
    svc = res.scalars().first()
    if not svc and not api_key:
        return {"status": "error", "detail": "api_key requise"}
    if svc:
        svc.name = data.get("name", svc.name)
        svc.url = url
        # Keep the stored key when the field is left blank on an update.
        if api_key:
            svc.api_key = encrypt_api_key(api_key)
        svc.is_enabled = data.get("is_enabled", True)
    else:
        svc = Service(
            name=data.get("name", "Jellyfin"),
            type="jellyfin",
            url=url,
            api_key=encrypt_api_key(api_key),
            is_enabled=data.get("is_enabled", True),
        )
        db.add(svc)
    await db.commit()
    return {"status": "ok"}


@router.get("/jellyfin/test")
async def test_jellyfin(db: AsyncSession = Depends(get_db)):
    return await jellyfin_service.test_connection(db)

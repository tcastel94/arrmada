"""Kodi API — settings and synchronization."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.models.device import Device
from app.models.service import Service
from app.services import kodi as kodi_service
from app.services import watch_summary, watch_sync
from app.services.encryption import decrypt_api_key, encrypt_api_key
from app.services.fully_kiosk import kiosk
from app.services.kodi import discover_kodi, sync_kodi
from app.utils.cache import cache
from app.utils.event_bus import event_bus

router = APIRouter(
    prefix="/api/kodi",
    tags=["kodi"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/discover")
async def discover_instances() -> list[dict]:
    """Discover Kodi instances using mDNS."""
    return await discover_kodi()


@router.post("/sync")
async def trigger_kodi_sync(db: AsyncSession = Depends(get_db)):
    """Trigger library scan on all configured Kodis."""
    return await sync_kodi(db)


@router.post("/play")
async def play_on_kodi(data: dict, db: AsyncSession = Depends(get_db)):
    """Start playback of a movie (by TMDB id) on a Kodi instance."""
    tmdb_id = data.get("tmdb_id")
    if not tmdb_id:
        return {"status": "error", "detail": "tmdb_id requis"}
    room = data.get("room") or "salon"
    result = await kodi_service.play_movie(db, int(tmdb_id), data.get("service_id"), room=room)

    from app.services.activity_log import log_event

    ok = result.get("status") == "ok"
    await log_event(
        category="playback",
        action="kodi_play",
        status="ok" if ok else "ko",
        source="arrmada",
        media_type="movie",
        media_id=data.get("media_id"),
        tmdb_id=int(tmdb_id),
        title=data.get("title"),
        device=result.get("kodi"),
        detail=None if ok else result.get("detail"),
        meta={"movieid": result.get("movieid")} if ok else None,
    )
    return result


@router.get("/now-playing")
async def now_playing(db: AsyncSession = Depends(get_db)):
    """Current Kodi playback state (for the remote on the media detail page)."""
    return await kodi_service.get_now_playing(db)


@router.post("/control")
async def control(data: dict, db: AsyncSession = Depends(get_db)):
    """Send a remote command: playpause | stop | seek | volume | mute."""
    action = (data or {}).get("action")
    if not action:
        return {"status": "error", "detail": "action requise"}
    return await kodi_service.control_player(db, action, (data or {}).get("value"))


@router.get("/watched-status")
async def watched_status(db: AsyncSession = Depends(get_db)):
    """Watched/resume state per TMDB id from Kodi (cached 60s)."""

    async def _compute():
        return await kodi_service.get_watched_status(db)

    return await cache.get_or_set("kodi:watched", _compute, ttl_seconds=60)


@router.post("/clean")
async def clean_kodi(data: dict | None = None, db: AsyncSession = Depends(get_db)):
    """Trigger VideoLibrary.Clean on a Kodi instance."""
    cache.invalidate("kodi:watched")
    return await kodi_service.clean_library(db, (data or {}).get("service_id"))


@router.get("/drift")
async def kodi_drift(db: AsyncSession = Depends(get_db)):
    """Movies in Radarr but missing from the Kodi library."""
    return await kodi_service.get_drift(db)


@router.post("/test/{service_id}")
async def test_kodi(service_id: int, db: AsyncSession = Depends(get_db)):
    """Ping a Kodi instance and read its version."""
    return await kodi_service.test_connection(db, service_id)


# ── Settings (instances) ──────────────────────────────────────
# Les identifiants Kodi sont stockés chiffrés dans `Service.api_key` sous la
# forme "utilisateur:motdepasse" (format attendu par app.services.kodi).


def _split_creds(service: Service) -> tuple[str, str]:
    """Return (username, password) decrypted from the stored 'user:pass'."""
    if not service.api_key:
        return "", ""
    creds = decrypt_api_key(service.api_key) or ""
    user, _, password = creds.partition(":")
    return user, password


def _public(service: Service) -> dict[str, Any]:
    """Public view of a Kodi instance.

    SECURITY: the password is never sent back to the browser (it used to be
    returned decrypted, in clear text). Only the username and a boolean.
    """
    user, password = _split_creds(service)
    return {
        "id": service.id,
        "name": service.name,
        "url": service.url,
        "is_enabled": service.is_enabled,
        "username": user,
        "has_password": bool(password),
    }


def _new_creds(data: dict, existing: Service | None) -> str | None:
    """Build the 'user:pass' string to store, or None to keep the current one.

    Accepts the new ``username`` / ``password`` fields, or the legacy
    ``api_key`` ("user:pass"). An EMPTY password never overwrites the stored
    one: re-saving the form (e.g. to rename the instance) used to wipe the
    password because the field is always blank in the UI.
    """
    if "username" in data or "password" in data:
        user = (data.get("username") or "").strip()
        password = data.get("password") or ""
    elif data.get("api_key") is not None:
        user, _, password = str(data.get("api_key")).partition(":")
    else:
        return None

    if not password and existing is not None:
        old_user, old_password = _split_creds(existing)
        user = user or old_user
        password = old_password
    if not user and not password:
        return ""
    return f"{user}:{password}"


@router.get("/settings")
async def get_kodi_settings(db: AsyncSession = Depends(get_db)):
    """Fetch all Kodi services from database (password never included)."""
    stmt = select(Service).where(Service.type == "kodi").order_by(Service.name)
    result = await db.execute(stmt)
    return [_public(k) for k in result.scalars().all()]


@router.post("/settings")
async def add_kodi_setting(data: dict, db: AsyncSession = Depends(get_db)):
    """Add or update a Kodi instance — idempotent by URL to avoid duplicates.

    Adding the same Kodi (same URL) twice used to create a duplicate row, so a
    sync would scan the same Kodi several times. We now reuse the existing entry.
    """
    url = (data.get("url") or "").strip().rstrip("/")
    if not url:
        return {"status": "error", "detail": "URL requise"}

    res = await db.execute(select(Service).where(Service.type == "kodi", Service.url == url))
    existing = res.scalars().first()

    if existing:
        existing.name = data.get("name") or existing.name
        creds = _new_creds(data, existing)
        if creds is not None:
            existing.api_key = encrypt_api_key(creds)
        existing.is_enabled = data.get("is_enabled", True)
        await db.commit()
        await db.refresh(existing)
        return {"id": existing.id, "message": "Kodi mis à jour"}

    new_kodi = Service(
        name=data.get("name") or "Kodi",
        type="kodi",
        url=url,
        api_key=encrypt_api_key(_new_creds(data, None) or ""),
        is_enabled=data.get("is_enabled", True),
    )
    db.add(new_kodi)
    await db.commit()
    await db.refresh(new_kodi)
    return {"id": new_kodi.id, "message": "Kodi ajouté"}


@router.put("/settings/{service_id}")
async def update_kodi_setting(service_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    """Edit an existing Kodi in place (name, URL, credentials).

    Changing the URL through POST created a second row; editing by id keeps a
    single instance. An empty password keeps the stored one.
    """
    svc = await db.get(Service, service_id)
    if not svc or svc.type != "kodi":
        raise HTTPException(status_code=404, detail="Kodi introuvable")

    url = (data.get("url") or "").strip().rstrip("/")
    if url and url != svc.url:
        dup = await db.execute(
            select(Service).where(
                Service.type == "kodi", Service.url == url, Service.id != service_id
            )
        )
        if dup.scalars().first():
            raise HTTPException(status_code=409, detail="Un autre Kodi utilise déjà cette URL")
        svc.url = url
    if data.get("name"):
        svc.name = data["name"]
    creds = _new_creds(data, svc)
    if creds is not None:
        svc.api_key = encrypt_api_key(creds)
    if "is_enabled" in data:
        svc.is_enabled = bool(data["is_enabled"])
    await db.commit()
    await db.refresh(svc)
    return {"id": svc.id, "message": "Kodi mis à jour"}


@router.delete("/settings/{service_id}")
async def delete_kodi_setting(service_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a Kodi instance."""
    svc = await db.get(Service, service_id)
    if svc and svc.type == "kodi":
        await db.delete(svc)
        await db.commit()
    return {"status": "deleted"}


# ── Kodi Add-on Endpoints ─────────────────────────────────────
@router.post("/actions/subtitles")
async def addon_subtitles_action(data: dict, db: AsyncSession = Depends(get_db)):
    """Trigger Bazarr subtitle search & download from Kodi add-on."""
    return await kodi_service.handle_addon_subtitles(db, data)


@router.post("/actions/subtitles/sync")
async def addon_subtitles_sync_action(data: dict, db: AsyncSession = Depends(get_db)):
    """Trigger Bazarr FFsubsync audio-aligned subtitle synchronization from Kodi add-on."""
    return await kodi_service.handle_addon_sync_subtitles(db, data)


@router.post("/actions/search")
async def addon_search_action(data: dict, db: AsyncSession = Depends(get_db)):
    """Trigger Radarr/Sonarr release search from Kodi add-on."""
    return await kodi_service.handle_addon_search(db, data)


@router.post("/scrobble")
async def addon_scrobble(
    data: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Receive live playback status & scrobbles from Kodi add-on service.

    Also feeds the per-room "now playing" state shown by the living-room
    screen (`/api/ambient`): the room is the paired TV's, else the add-on's
    own room setting.
    """
    import time

    from app.services.now_playing import now_playing

    room = user.get("room") or str((data or {}).get("room") or "salon")
    if user.get("device_name"):
        data = dict(data, device_name=user["device_name"])
    now_playing.record(room, data or {}, time.time())
    # Tablette de la pièce en mode kiosk pendant le média (Fully Kiosk) :
    # lancé à part, la réponse à la TV n'attend jamais la tablette.
    _background(kiosk.on_playback(room, str((data or {}).get("event") or "progress")))
    return await kodi_service.handle_addon_scrobble(db, data)


_BACKGROUND: set = set()  # tâches en cours (référence gardée jusqu'à leur fin)


def _background(coro) -> None:
    task = asyncio.create_task(coro)
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


# ── Vu / reprise partagés entre les TV (ADR-004, phase 4.4) ───
@router.get("/watch-state")
async def get_watch_states(
    since: str | None = None, limit: int = watch_sync.MAX_STATES, db: AsyncSession = Depends(get_db)
):
    """États vu / reprise modifiés après `since` (curseur rendu par l'appel précédent).

    Sans `since` : tout, page par page (premier passage d'une TV). `more`
    vrai : il en reste, rappeler avec le nouveau curseur.
    """
    states, more = await watch_sync.changes(db, watch_sync.parse_cursor(since), limit)
    cursor = states[-1]["updated_at"] if states else (since or "")
    return {"states": states, "cursor": cursor, "more": more}


@router.post("/watch-state")
async def post_watch_states(
    data: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    """Une TV dépose l'état de titres qui ont changé chez elle.

    `merge` vrai : premier passage de la TV (« vu » l'emporte, rien n'est
    défait). Les autres TV sont prévenues par l'événement `watch_state`.
    """
    payload = data or {}
    raw = payload.get("states")
    if not isinstance(raw, list):
        raise HTTPException(status_code=422, detail="« states » doit être une liste")
    device = str(user.get("device_name") or payload.get("device") or "ArrMada")
    changed, rejected = await watch_sync.store(db, raw, bool(payload.get("merge")), device)
    cursor = changed[-1]["updated_at"].isoformat() if changed else ""
    if changed:
        await event_bus.publish(
            event_type="watch_state",
            data={"changed": len(changed), "device": device, "cursor": cursor},
        )
    return {"status": "ok", "changed": len(changed), "rejected": rejected, "cursor": cursor}


# ── Vu / reprise dans la web app, « Lire sur la TV » (add-on 1.19.0) ──
@router.get("/watch-summary")
async def get_watch_summary(db: AsyncSession = Depends(get_db)):
    """Badges vu / en cours et page Reprendre de la web app.

    Tiré des états partagés par les TV (`watch_states`), rien n'est demandé
    à Kodi : fonctionne même TV éteintes. Pas ouvert aux TV (hors périmètre).
    """
    return await watch_summary.load_summary(db)


@router.post("/play-on-device")
async def play_on_device(
    data: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)
):
    """Demande à UNE TV appairée de lancer un film ou un épisode de SA médiathèque.

    Corps : {device_id, media_type, id (TMDB d'un film / TVDB d'une série),
    season, episode, title, resume}. Publie l'événement `play_request` ; la
    TV visée le reçoit dans les 5 s. `online` faux : la TV ne s'est pas
    manifestée récemment (éteinte ?), la demande expirera au bout de 2 min.
    """
    payload = data or {}
    try:
        device_id = int(payload.get("device_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="« device_id » manquant") from None
    device = await db.get(Device, device_id)
    if device is None or device.kind != "tv":
        raise HTTPException(status_code=404, detail="TV inconnue (appairée ?)")
    now = datetime.now(UTC)
    request = watch_summary.play_request(
        {"id": device.id, "name": device.name, "room": device.room}, payload, now
    )
    if request is None:
        raise HTTPException(status_code=422, detail="Titre à lire invalide")
    await event_bus.publish(event_type="play_request", data=request)

    from app.services.activity_log import log_event

    code = (
        f" S{request['season']:02d}E{request['episode']:02d}"
        if request["media_type"] == "episode"
        else ""
    )
    await log_event(
        category="playback",
        action="play_on_device",
        source="arrmada",
        media_type=request["media_type"],
        tmdb_id=int(request["id"]) if request["id_type"] == "tmdb" else None,
        title=f"{request['title']}{code}" or None,
        device=device.name,
    )
    return {
        "status": "sent",
        "device": device.name,
        "online": watch_summary.is_online(device.last_seen_at, now),
        "request_id": request["request_id"],
    }


# ── Épisodes d'une série vus par Sonarr (manquants, à venir) ──
@router.get("/series/{tvdb_id}/episodes")
async def addon_series_episodes(tvdb_id: int, db: AsyncSession = Depends(get_db)):
    """Épisodes connus de Sonarr pour une série (repérée par son n° TVDB).

    L'écran Série de la TV les compare à sa médiathèque : ceux qui manquent
    sont affichés grisés (« Manquant », « Diffusion le … »). Gardé 2 min.
    """

    async def _compute():
        return await kodi_service.sonarr_episodes_for_addon(db, tvdb_id)

    return await cache.get_or_set(f"kodi:episodes:{tvdb_id}", _compute, ttl_seconds=120)


@router.get("/addon-status")
async def addon_status(db: AsyncSession = Depends(get_db)):
    """Get active downloads queue and dashboard stats for Kodi add-on."""
    return await kodi_service.get_addon_dashboard_status(db)


@router.get("/dashboard")
async def addon_dashboard(db: AsyncSession = Depends(get_db)):
    """Get complete stack health, disk space, services, and activity history for Kodi UI."""
    return await kodi_service.get_addon_full_dashboard(db)


# ── Kodi Media Discovery & Releases ───────────────────────────
@router.get("/media/lookup")
async def addon_media_lookup(q: str, type: str = "all", db: AsyncSession = Depends(get_db)):
    """Lookup movies and series for Kodi UI."""
    return await kodi_service.lookup_media_for_addon(db, q, type)


@router.get("/media/recommendations")
async def addon_media_recommendations(db: AsyncSession = Depends(get_db)):
    """Get trending and recommended movies/series for Kodi."""
    return await kodi_service.get_recommendations_for_addon(db)


@router.get("/media/options")
async def addon_media_options(type: str = "movie", db: AsyncSession = Depends(get_db)):
    """Get quality profiles and root folders for media type."""
    return await kodi_service.get_media_options_for_addon(db, type)


@router.post("/media/add")
async def addon_media_add(data: dict, db: AsyncSession = Depends(get_db)):
    """Add a movie or series to Radarr/Sonarr from Kodi."""
    return await kodi_service.add_media_for_addon(db, data)


@router.get("/media/{type}/{id}/releases")
async def addon_media_releases(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """List available releases (Usenet & Torrent) for interactive picking."""
    return await kodi_service.list_releases_for_addon(db, type, id)


@router.post("/media/{type}/{id}/grab")
async def addon_media_grab(type: str, id: int, data: dict, db: AsyncSession = Depends(get_db)):
    """Grab a selected release and send to SABnzbd / Torrent client."""
    data["type"] = type
    data["arr_id"] = id
    return await kodi_service.grab_release_for_addon(db, data)


# ── Kodi Queue Control ───────────────────────────────────────
@router.post("/downloads/{type}/{id}/remove")
async def addon_queue_remove(
    type: str, id: int, data: dict | None = None, db: AsyncSession = Depends(get_db)
):
    """Cancel / remove download from Kodi."""
    payload = data or {}
    return await kodi_service.remove_queue_item_for_addon(
        db,
        type,
        id,
        remove_from_client=payload.get("remove_from_client", True),
        blocklist=payload.get("blocklist", False),
    )


@router.post("/downloads/{type}/{id}/resume")
async def addon_queue_resume(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """Resume / unpause download from Kodi."""
    return await kodi_service.resume_queue_item_for_addon(db, type, id)


@router.post("/downloads/{type}/{id}/pause")
async def addon_queue_pause(type: str, id: int, db: AsyncSession = Depends(get_db)):
    """Pause download from Kodi."""
    return await kodi_service.pause_queue_item_for_addon(db, type, id)


# ── Kodi Maintenance & Cleanup ────────────────────────────────
@router.post("/maintenance/clean-orphans")
async def addon_clean_orphans(db: AsyncSession = Depends(get_db)):
    """Trigger clean of empty directories and orphan non-media files."""
    return await kodi_service.clean_orphans_for_addon(db)


# ── Kodi Widgets ──────────────────────────────────────────────
@router.get("/widgets/recent")
async def addon_widgets_recent(db: AsyncSession = Depends(get_db)):
    """Return recently added items for Kodi home screen widgets."""
    return await kodi_service.get_recent_media_for_addon(db)

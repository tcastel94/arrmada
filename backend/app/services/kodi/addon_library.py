"""Add-on Kodi : recherche, scrobble, épisodes et tableaux de bord affichés sur la TV."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.kodi.arr_clients import _get_radarr_client, _get_sonarr_client
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.kodi")


async def handle_addon_search(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Trigger Radarr/Sonarr media search from Kodi context action.

    Lancée depuis la TV : la demande est notée pour passer en tête de
    SABnzbd (services/tv_priority.py), sauf `"priority": false`.
    """
    from app.services import tv_priority
    from app.services.activity_log import log_event

    origin = origin or tv_priority.origin_of(None)
    priority = bool(data.get("priority", True))

    media_type = data.get("media_type") or (
        "episode" if data.get("season") is not None else "movie"
    )
    tmdb_id = data.get("tmdb_id")
    imdb_id = data.get("imdb_id")
    tvdb_id = data.get("tvdb_id")
    title = data.get("title") or ""
    season = data.get("season")
    episode = data.get("episode")

    try:
        if media_type == "movie":
            radarr = await _get_radarr_client(db)
            if not radarr:
                return {"status": "error", "message": "Radarr n'est pas configuré"}

            movies = await radarr.get_movies()
            match = None
            for m in movies:
                if tmdb_id and str(m.get("tmdbId")) == str(tmdb_id):
                    match = m
                    break
                if imdb_id and str(m.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match = m
                    break
                if title and m.get("title", "").strip().lower() == title.strip().lower():
                    match = m
                    break

            if not match:
                return {"status": "error", "message": f"Film '{title}' introuvable dans Radarr"}

            await radarr.search_movie(match["id"])
            await tv_priority.create_request(
                db,
                service_type="radarr",
                arr_id=match["id"],
                title=match.get("title") or title,
                origin=origin,
                priority=priority,
            )
            await log_event(
                category="media",
                action="kodi_media_search",
                status="ok",
                source="kodi",
                media_type="movie",
                title=match.get("title", title),
                tmdb_id=match.get("tmdbId"),
                device=origin["device_name"],
                detail="Recherche de release Radarr déclenchée depuis Kodi",
            )
            return {
                "status": "ok",
                "message": f"Recherche de release lancée pour {match.get('title')}",
                "title": match.get("title"),
            }

        else:  # episode / series
            sonarr = await _get_sonarr_client(db)
            if not sonarr:
                return {"status": "error", "message": "Sonarr n'est pas configuré"}

            series_list = await sonarr.get_series()
            match_series = None
            for s in series_list:
                if tvdb_id and str(s.get("tvdbId")) == str(tvdb_id):
                    match_series = s
                    break
                if imdb_id and str(s.get("imdbId", "")).lower() == str(imdb_id).lower():
                    match_series = s
                    break
                if title and s.get("title", "").strip().lower() == title.strip().lower():
                    match_series = s
                    break

            if not match_series:
                return {"status": "error", "message": f"Série '{title}' introuvable dans Sonarr"}

            series_id = match_series["id"]
            if season is not None and episode is not None:
                episodes = await sonarr.get(f"/episode?seriesId={series_id}")
                match_ep = None
                for ep in episodes:
                    if int(ep.get("seasonNumber", -1)) == int(season) and int(
                        ep.get("episodeNumber", -1)
                    ) == int(episode):
                        match_ep = ep
                        break

                if not match_ep:
                    return {
                        "status": "error",
                        "message": f"Épisode S{int(season):02d}E{int(episode):02d} introuvable",
                    }

                await sonarr.search_episodes([match_ep["id"]])
                desc = f"Recherche épisode S{int(season):02d}E{int(episode):02d}"
                scope = {"scope": "episode", "episode_ids": [match_ep["id"]]}
            elif season is not None:
                await sonarr.search_season(series_id, int(season))
                desc = f"Recherche saison {int(season)}"
                scope = {"scope": "season", "season": int(season)}
            else:
                await sonarr.search_series(series_id)
                desc = "Recherche série complète"
                scope = {"scope": "series"}

            await tv_priority.create_request(
                db,
                service_type="sonarr",
                arr_id=series_id,
                title=match_series.get("title") or title,
                origin=origin,
                priority=priority,
                **scope,
            )

            await log_event(
                category="media",
                action="kodi_media_search",
                status="ok",
                source="kodi",
                media_type="series",
                title=match_series.get("title", title),
                device=origin["device_name"],
                detail=f"{desc} déclenchée depuis Kodi",
            )
            return {
                "status": "ok",
                "message": f"{desc} lancée pour {match_series.get('title')}",
                "title": match_series.get("title"),
            }

    except Exception as exc:
        logger.error(f"Error handling kodi search action: {exc}", exc_info=True)
        return {"status": "error", "message": f"Erreur de recherche : {str(exc)}"}


async def handle_addon_scrobble(db: AsyncSession, data: dict[str, Any]) -> dict[str, Any]:
    """Handle live playback scrobble from Kodi addon service."""
    from app.services.activity_log import log_event
    from app.utils.event_bus import event_bus

    event_type = data.get("event", "progress")  # play, pause, stop, progress
    title = data.get("title", "Inconnu")
    percentage = data.get("percentage", 0)
    kodi_device = data.get("device_name", "Kodi")

    # Broadcast to websocket/SSE listeners
    await event_bus.publish(
        event_type="kodi_scrobble",
        data={
            **data,
            "device": kodi_device,
        },
    )

    if event_type == "stop" and float(percentage or 0) >= 90:
        await log_event(
            category="playback",
            action="kodi_watched",
            status="ok",
            source="kodi",
            media_type=data.get("media_type", "movie"),
            title=title,
            device=kodi_device,
            detail=f"Visionnage terminé ({percentage}%)",
        )

    return {"status": "ok"}


async def sonarr_episodes_for_addon(db: AsyncSession, tvdb_id: int) -> dict[str, Any]:
    """Épisodes Sonarr d'une série, au format court de l'écran Série de la TV.

    `status` : « ok », « unknown » (série absente de Sonarr) ou « error ».
    Les spéciaux (saison 0) sont laissés de côté : trop d'épisodes bonus
    qu'on ne cherche jamais.
    """
    sonarr = await _get_sonarr_client(db)
    if not sonarr:
        return {"status": "error", "message": "Sonarr n'est pas configuré", "episodes": []}
    try:
        series = next(
            (s for s in await sonarr.get_series() if str(s.get("tvdbId")) == str(tvdb_id)),
            None,
        )
        if series is None:
            return {"status": "unknown", "episodes": []}
        raw = await sonarr.get("/episode", params={"seriesId": series["id"]})
    except Exception as exc:
        logger.warning(f"Épisodes Sonarr de la série TVDB {tvdb_id} illisibles : {exc}")
        return {"status": "error", "message": "Sonarr injoignable", "episodes": []}
    items = raw if isinstance(raw, list) else []
    episodes = [
        {
            "season": int(ep.get("seasonNumber") or 0),
            "episode": int(ep.get("episodeNumber") or 0),
            "title": ep.get("title") or "",
            "air_date": ep.get("airDateUtc") or "",
            "has_file": bool(ep.get("hasFile")),
            "monitored": bool(ep.get("monitored")),
            "overview": ep.get("overview") or "",
        }
        for ep in items
        if int(ep.get("seasonNumber") or 0) > 0
    ]
    episodes.sort(key=lambda e: (e["season"], e["episode"]))
    return {"status": "ok", "title": series.get("title") or "", "episodes": episodes}


def _format_addon_queue(queue_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """File de téléchargement au format de l'add-on Kodi.

    Les clés lues sont celles de ``media_aggregator.get_queue_items``
    (``time_left``, ``size_bytes``…). L'ancienne version lisait ``timeleft``
    et ``size``, absentes : temps restant et taille arrivaient toujours vides.
    ``id`` et ``service`` servent aux actions pause / reprise de l'add-on.
    """
    return [
        {
            "id": it.get("id"),
            "title": it.get("title") or it.get("name") or "Téléchargement",
            "status": it.get("status", "downloading"),
            "progress": round(it.get("progress", 0) or 0, 1),
            "size": it.get("size_bytes") or it.get("size") or 0,
            "size_left": it.get("size_left_bytes") or 0,
            "timeleft": it.get("time_left") or it.get("timeleft") or it.get("eta") or "",
            "service": it.get("service_type") or it.get("service") or "",
        }
        for it in queue_items
    ]


async def get_addon_dashboard_status(db: AsyncSession) -> dict[str, Any]:
    """Return download queue, recent events and quick summary for Kodi addon background service."""
    from sqlalchemy import select

    from app.models.activity import ActivityEvent
    from app.services import media_aggregator

    queue_items = await media_aggregator.get_queue_items(db)
    formatted_queue = _format_addon_queue(queue_items)

    # Recent import events for auto-scan trigger
    recent_events = []
    try:
        stmt = (
            select(ActivityEvent)
            .where(ActivityEvent.category.in_(["download", "media"]), ActivityEvent.status == "ok")
            .order_by(ActivityEvent.id.desc())
            .limit(8)
        )
        res = await db.execute(stmt)
        for ev in res.scalars().all():
            recent_events.append(
                {
                    "id": ev.id,
                    "action": ev.action,
                    "title": ev.title,
                    "detail": ev.detail,
                    "timestamp": ev.created_at.timestamp() if ev.created_at else 0,
                }
            )
    except Exception:
        pass

    return {
        "status": "ok",
        "downloads_count": len(formatted_queue),
        "downloads": formatted_queue,
        "recent_events": recent_events,
    }


async def get_addon_full_dashboard(db: AsyncSession) -> dict[str, Any]:
    """Return complete system health, storage, services, and activity history for Kodi (parallel & cached)."""
    import asyncio

    from sqlalchemy import select

    from app.models.activity import ActivityEvent
    from app.models.service import Service
    from app.services import media_aggregator
    from app.utils.cache import cache
    from app.utils.helpers import format_bytes

    async def _fetch():
        # 1. Services & Activities from DB
        stmt_svc = select(Service)
        stmt_act = select(ActivityEvent).order_by(ActivityEvent.id.desc()).limit(15)

        res_svc, res_act = await asyncio.gather(
            db.execute(stmt_svc), db.execute(stmt_act), return_exceptions=True
        )

        services_list = []
        if not isinstance(res_svc, Exception):
            for s in res_svc.scalars().all():
                services_list.append(
                    {
                        "id": s.id,
                        "name": s.name,
                        "type": s.type,
                        "is_enabled": s.is_enabled,
                        "url": s.url,
                        "status": "online" if s.is_enabled else "disabled",
                    }
                )

        recent_activities = []
        if not isinstance(res_act, Exception):
            for ev in res_act.scalars().all():
                time_str = ev.created_at.strftime("%H:%M") if ev.created_at else ""
                recent_activities.append(
                    {
                        "id": ev.id,
                        "time": time_str,
                        "category": ev.category,
                        "action": ev.action,
                        "status": ev.status,
                        "title": ev.title,
                        "subtitle": ev.subtitle or "",
                        "detail": ev.detail or "",
                    }
                )

        # 2. Parallel fetch stats, disks, and queue
        async def _safe_stats():
            try:
                return await media_aggregator.get_dashboard_stats(db)
            except Exception:
                return {}

        async def _safe_disks():
            try:
                from app.api.system import _fetch_disk_space

                return await _fetch_disk_space(db)
            except Exception:
                return []

        async def _safe_queue():
            try:
                return await media_aggregator.get_queue_items(db)
            except Exception:
                return []

        raw_stats, disks, queue_items = await asyncio.gather(
            _safe_stats(),
            _safe_disks(),
            _safe_queue(),
        )

        # get_dashboard_stats returns nested structure: {movies: {total:..}, series: {total:.., total_episodes:..}}
        movies_block = raw_stats.get("movies") or {}
        series_block = raw_stats.get("series") or {}
        stats = {
            "movies_count": movies_block.get("total", 0) or raw_stats.get("total_movies", 0),
            "series_count": series_block.get("total", 0) or raw_stats.get("total_series", 0),
            "episodes_count": series_block.get("total_episodes", 0)
            or raw_stats.get("total_episodes", 0),
            "total_size_bytes": raw_stats.get("total_size_bytes", 0),
            "total_size_human": format_bytes(raw_stats.get("total_size_bytes", 0)),
        }

        formatted_queue = _format_addon_queue(queue_items if isinstance(queue_items, list) else [])

        return {
            "status": "ok",
            "services": services_list,
            "stats": stats,
            "disks": disks if isinstance(disks, list) else [],
            "downloads": formatted_queue,
            "downloads_count": len(formatted_queue),
            "recent_activities": recent_activities,
        }

    return await cache.get_or_set("kodi_addon_full_dashboard", _fetch, ttl_seconds=15)

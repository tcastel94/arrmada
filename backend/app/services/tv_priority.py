"""Gardien de priorité : ce qui est lancé depuis la TV passe devant le reste.

Pourquoi un gardien : Radarr et Sonarr n'ont aucune notion de priorité. Ils
envoient un NZB à SABnzbd, qui le range en fin de file. C'est donc ArrMada qui
repère les téléchargements d'une demande TV et les passe en priorité « Force »
dans SABnzbd, en tête de file, dans l'ordre d'arrivée des demandes.

Analogie exploitation : c'est un job de supervision qui tourne toutes les
15 s (TV_PRIORITY_INTERVAL_SECONDS) et remet en conformité. Il faut repasser
régulièrement, pas seulement au clic : Sonarr envoie une saison en plusieurs
NZB, parfois à quelques minutes d'écart, et chacun doit être repris.

Le lien entre les deux mondes : le « downloadId » d'un élément de la file
Sonarr / Radarr est le nzo_id de SABnzbd.

Limites assumées :
  - les torrents (Deluge) ne passent pas par SABnzbd : pas de priorité pour eux ;
  - un élément mis en pause à la main reste en pause (on ne le force pas).
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.service import Service
from app.models.tv_request import TvRequest
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sabnzbd import SabnzbdClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Fabrique de sessions des passes en arrière-plan (remplacée par les tests)
session_factory = async_session_factory

# Priorités SABnzbd (API « mode=queue&name=priority »)
SAB_FORCE = 2
SAB_HIGH = 1
_FORCE_LABELS = {"force", "2"}
_HIGH_OR_MORE = {"force", "2", "high", "1"}

# Téléchargements sortis de la file depuis 3 min : la demande est terminée.
# Le délai couvre le trou entre deux épisodes d'une même saison.
CLOSE_AFTER = timedelta(minutes=3)
# Demandes fermées encore montrées à la TV (« Prêt »)
RECENT_CLOSED = timedelta(hours=12)

# Une seule passe à la fois (minuterie + webhook peuvent tomber ensemble)
_lock = asyncio.Lock()
_background: set[asyncio.Task] = set()


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite relit les dates sans fuseau : on les remet en UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def origin_of(user: dict[str, Any] | None) -> dict[str, Any]:
    """TV d'origine d'un appel (jeton d'appareil), sinon « TV » sans plus de détail."""
    user = user or {}
    if user.get("role") == "device":
        return {
            "device_id": user.get("device_id"),
            "device_name": str(user.get("device_name") or "TV"),
            "room": user.get("room"),
        }
    return {"device_id": None, "device_name": "TV", "room": None}


# ─────────────────────────────────────────────────────────────────────────────
# Éléments de file : une forme commune (file *arr ou webhook « Grab »)
# ─────────────────────────────────────────────────────────────────────────────


def record_from_queue(service_type: str, rec: dict[str, Any]) -> dict[str, Any]:
    """Une ligne de /api/v3/queue de Radarr / Sonarr (une ligne par épisode)."""
    episode = rec.get("episode") if isinstance(rec.get("episode"), dict) else {}
    season = rec.get("seasonNumber")
    if season is None:
        season = episode.get("seasonNumber")
    return {
        "service_type": service_type,
        "queue_id": rec.get("id"),
        "movie_id": rec.get("movieId"),
        "series_id": rec.get("seriesId"),
        "episode_id": rec.get("episodeId"),
        "season": season,
        "download_id": str(rec.get("downloadId") or ""),
        "title": str(rec.get("title") or ""),
        "protocol": str(rec.get("protocol") or ""),
    }


def records_from_grab(service_type: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Webhook « Grab » : le téléchargement est connu avant que la file *arr le montre.

    Radarr / Sonarr envoient le downloadId (nzo_id) dans le webhook : on peut
    poser la priorité tout de suite, sans attendre leur prochain rafraîchissement.
    """
    download_id = str(payload.get("downloadId") or "")
    if not download_id:
        return []
    release = payload.get("release") if isinstance(payload.get("release"), dict) else {}
    base = {
        "service_type": service_type,
        "queue_id": None,
        "movie_id": None,
        "series_id": None,
        "episode_id": None,
        "season": None,
        "download_id": download_id,
        "title": str(release.get("releaseTitle") or ""),
        "protocol": "",
    }
    movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else None
    if movie:
        return [{**base, "movie_id": movie.get("id")}]
    series = payload.get("series") if isinstance(payload.get("series"), dict) else None
    if not series:
        return []
    episodes = [e for e in payload.get("episodes") or [] if isinstance(e, dict)]
    if not episodes:
        return [{**base, "series_id": series.get("id")}]
    return [
        {
            **base,
            "series_id": series.get("id"),
            "episode_id": ep.get("id"),
            "season": ep.get("seasonNumber"),
        }
        for ep in episodes
    ]


def _same_release(a: str, b: str) -> bool:
    """Même nom de release (casse, espaces et « .nzb » final ignorés)."""

    def norm(text: str) -> str:
        text = text.strip().casefold()
        return text[:-4] if text.endswith(".nzb") else text

    return bool(a) and bool(b) and norm(a) == norm(b)


def in_scope(req: TvRequest, rec: dict[str, Any]) -> bool:
    """Vrai si cet élément de file correspond au film / à la série / saison / épisode demandé."""
    if rec.get("service_type") != req.service_type:
        return False
    if req.service_type == "radarr":
        return rec.get("movie_id") == req.arr_id
    if rec.get("series_id") != req.arr_id:
        return False
    if req.scope == "season":
        return rec.get("season") == req.season
    if req.scope == "episode":
        return rec.get("episode_id") in set(req.episode_ids or [])
    return True  # série entière


def select_records(req: TvRequest, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Éléments de file de cette demande.

    Release choisie à la main : seul ce téléchargement-là si on le reconnaît
    à son nom, sinon tout ce qui correspond à la portée (un nom de job
    SABnzbd peut différer du nom de la release).
    """
    matched = [r for r in records if in_scope(req, r)]
    if req.release_title:
        exact = [r for r in matched if _same_release(r.get("title", ""), req.release_title)]
        if exact:
            return exact
    return matched


# ─────────────────────────────────────────────────────────────────────────────
# Plan d'action SABnzbd (fonctions pures, testées sans réseau)
# ─────────────────────────────────────────────────────────────────────────────


def _ordered(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Éléments dans l'ordre de la file (champ « index » s'il est là)."""
    ranked = sorted(
        enumerate(slots), key=lambda pair: (_int(pair[1].get("index"), pair[0]), pair[0])
    )
    return [slot for _pos, slot in ranked]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def priority_plan(slots: list[dict[str, Any]], wanted: list[str]) -> list[str]:
    """nzo_id à passer en Force (présents dans cette file, pas déjà en Force, pas en pause)."""
    by_id = {s["nzo_id"]: s for s in slots}
    plan = []
    for nzo_id in wanted:
        slot = by_id.get(nzo_id)
        if slot is None:
            continue
        if str(slot.get("status") or "").casefold() == "paused":
            continue  # mis en pause exprès : on respecte
        if str(slot.get("priority") or "").casefold() not in _FORCE_LABELS:
            plan.append(nzo_id)
    return plan


def move_plan(slots: list[dict[str, Any]], wanted: list[str]) -> list[tuple[str, int]]:
    """Déplacements (nzo_id, position) pour mettre `wanted` en tête, dans cet ordre.

    On simule la file pendant le calcul : placer un élément en position k ne
    bouge pas ceux déjà placés avant k. Rien à faire si l'ordre est déjà bon
    (la passe toutes les 15 s n'envoie alors aucun appel à SABnzbd).
    """
    order = [s["nzo_id"] for s in _ordered(slots)]
    present = [n for n in wanted if n in order]
    moves = []
    for target, nzo_id in enumerate(present):
        if order.index(nzo_id) != target:
            moves.append((nzo_id, target))
            order.remove(nzo_id)
            order.insert(target, nzo_id)
    return moves


# ─────────────────────────────────────────────────────────────────────────────
# Accès aux services
# ─────────────────────────────────────────────────────────────────────────────


async def _services(db: AsyncSession, types: tuple[str, ...]) -> list[Service]:
    rows = await db.execute(
        select(Service).where(Service.is_enabled == True, Service.type.in_(types))  # noqa: E712
    )
    return list(rows.scalars().all())


def _arr_client(svc: Service) -> RadarrClient | SonarrClient:
    key = decrypt_api_key(svc.api_key)
    if svc.type == "radarr":
        return RadarrClient(url=svc.url, api_key=key)
    return SonarrClient(url=svc.url, api_key=key)


async def _sab_clients(db: AsyncSession) -> list[SabnzbdClient]:
    return [
        SabnzbdClient(url=s.url, api_key=decrypt_api_key(s.api_key))
        for s in await _services(db, ("sabnzbd",))
    ]


async def fetch_queue_records(
    db: AsyncSession, types: set[str]
) -> tuple[list[dict[str, Any]], set[str]]:
    """Lignes de file des Radarr / Sonarr voulus, et les types qui ont bien répondu.

    Un service injoignable ne doit pas faire croire que ses téléchargements
    sont finis : seuls les types qui ont répondu peuvent fermer une demande.
    """
    records: list[dict[str, Any]] = []
    answered: set[str] = set()
    failed: set[str] = set()
    for svc in await _services(db, tuple(sorted(types))):
        client = _arr_client(svc)
        try:
            data = await client.get_queue()
            rows = data.get("records", []) if isinstance(data, dict) else []
            records.extend(record_from_queue(svc.type, r) for r in rows if isinstance(r, dict))
            answered.add(svc.type)
        except Exception as exc:
            failed.add(svc.type)
            logger.warning("Priorité TV : file de %s illisible (%s)", svc.name, exc)
        finally:
            await client.close()
    return records, answered - failed


# ─────────────────────────────────────────────────────────────────────────────
# Demandes
# ─────────────────────────────────────────────────────────────────────────────


async def create_request(
    db: AsyncSession,
    *,
    service_type: str,
    arr_id: int,
    title: str,
    origin: dict[str, Any],
    scope: str | None = None,
    season: int | None = None,
    episode_ids: list[int] | None = None,
    release_title: str | None = None,
    added: bool = False,
    priority: bool = True,
) -> TvRequest | None:
    """Note une demande lancée depuis la TV (doublon ouvert : on garde l'existante)."""
    if service_type not in ("radarr", "sonarr") or not arr_id:
        return None
    if scope is None:
        scope = "movie" if service_type == "radarr" else "series"
    episode_ids = sorted({int(e) for e in episode_ids or []}) or None
    try:
        existing = (
            (
                await db.execute(
                    select(TvRequest).where(
                        TvRequest.status == "open",
                        TvRequest.service_type == service_type,
                        TvRequest.arr_id == int(arr_id),
                        TvRequest.scope == scope,
                    )
                )
            )
            .scalars()
            .all()
        )
        for req in existing:
            if req.season == season and (req.episode_ids or None) == episode_ids:
                if release_title and not req.release_title:
                    req.release_title = release_title
                    await db.commit()
                return req
        req = TvRequest(
            service_type=service_type,
            arr_id=int(arr_id),
            title=title[:300],
            scope=scope,
            season=season,
            episode_ids=episode_ids,
            release_title=(release_title or None) and release_title[:500],
            priority=priority,
            added=added,
            device_id=origin.get("device_id"),
            device_name=str(origin.get("device_name") or "TV")[:100],
            room=origin.get("room"),
            status="open",
            download_ids=[],
            requested_at=_now(),
        )
        db.add(req)
        await db.commit()
        logger.info("Demande TV : %s (%s) depuis %s", req.title, scope, req.device_name)
        return req
    except Exception as exc:  # une demande non notée ne doit jamais bloquer l'ajout
        logger.warning("Demande TV non enregistrée (%s) : %s", title, exc)
        with contextlib.suppress(Exception):
            await db.rollback()
        return None


def as_dict(req: TvRequest, viewer_device_id: int | None = None) -> dict[str, Any]:
    """Forme envoyée à la TV et à la web app."""

    def iso(value: datetime | None) -> str | None:
        value = _aware(value)
        return value.isoformat() if value else None

    return {
        "id": req.id,
        "service_type": req.service_type,
        "media_type": "movie" if req.service_type == "radarr" else "series",
        "arr_id": req.arr_id,
        "title": req.title,
        "scope": req.scope,
        "season": req.season,
        "episode_ids": req.episode_ids or [],
        "priority": req.priority,
        "device_name": req.device_name,
        "room": req.room,
        "mine": viewer_device_id is not None and req.device_id == viewer_device_id,
        "status": req.status,
        "download_ids": req.download_ids or [],
        "requested_at": iso(req.requested_at),
        "grabbed_at": iso(req.grabbed_at),
        "closed_at": iso(req.closed_at),
        "imported_at": iso(req.imported_at),
        "subtitles": req.subtitles or "",
    }


async def list_requests(db: AsyncSession, viewer_device_id: int | None = None) -> list[dict]:
    """Demandes en cours + fermées depuis moins de 12 h (les plus anciennes d'abord)."""
    since = _now() - RECENT_CLOSED
    rows = await db.execute(
        select(TvRequest)
        .where(or_(TvRequest.status == "open", TvRequest.closed_at >= since))
        .order_by(TvRequest.requested_at)
    )
    return [as_dict(r, viewer_device_id) for r in rows.scalars().all()]


async def annotate_queue(db: AsyncSession, items: list[dict[str, Any]]) -> None:
    """Ajoute `tv_request` aux éléments de /api/downloads lancés depuis la TV."""
    if not items:
        return
    try:
        rows = await db.execute(select(TvRequest).where(TvRequest.status == "open"))
        by_download: dict[str, TvRequest] = {}
        for req in rows.scalars().all():
            for download_id in req.download_ids or []:
                by_download.setdefault(download_id, req)
    except Exception as exc:
        logger.debug("Demandes TV illisibles pour la file : %s", exc)
        return
    for item in items:
        req = by_download.get(str(item.get("download_id") or ""))
        item["tv_request"] = (
            {
                "id": req.id,
                "device_name": req.device_name,
                "room": req.room,
                "priority": req.priority,
                "requested_at": as_dict(req)["requested_at"],
            }
            if req
            else None
        )


# ─────────────────────────────────────────────────────────────────────────────
# La passe du gardien
# ─────────────────────────────────────────────────────────────────────────────


async def _apply_sab(db: AsyncSession, wanted: list[str]) -> dict[str, int]:
    """Force + tête de file pour `wanted` (dans l'ordre) sur chaque SABnzbd."""
    stats = {"forced": 0, "moved": 0}
    if not wanted:
        return stats
    for sab in await _sab_clients(db):
        try:
            slots = await sab.get_slots()
            to_force = priority_plan(slots, wanted)
            for nzo_id in to_force:
                await sab.set_priority(nzo_id, SAB_FORCE)
                stats["forced"] += 1
            if to_force:  # SABnzbd a réordonné sa file : on relit avant de placer
                slots = await sab.get_slots()
            for nzo_id, position in move_plan(slots, wanted):
                await sab.move_to(nzo_id, position)
                stats["moved"] += 1
        except Exception as exc:
            logger.warning("Priorité TV : SABnzbd injoignable (%s)", exc)
        finally:
            await sab.close()
    return stats


async def enforce(extra_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Une passe : rattache la file aux demandes ouvertes, pose la priorité, ferme le fini."""
    if not settings.TV_PRIORITY_ENABLED:
        return {"skipped": "désactivé"}
    async with _lock, session_factory() as db:
        rows = await db.execute(
            select(TvRequest).where(TvRequest.status == "open").order_by(TvRequest.requested_at)
        )
        requests = list(rows.scalars().all())
        if not requests:
            return {"open": 0}

        now = _now()
        types = {r.service_type for r in requests}
        records, answered = await fetch_queue_records(db, types)
        records = list(extra_records or []) + records
        # Un webhook vaut réponse pour son type (le téléchargement existe bien)
        answered |= {r["service_type"] for r in extra_records or []}

        wanted: list[str] = []
        ready: list[TvRequest] = []
        closed = 0
        for req in requests:
            matched = select_records(req, records)
            ids = list(dict.fromkeys(r["download_id"] for r in matched if r.get("download_id")))
            if ids:
                req.grabbed_at = req.grabbed_at or now
                req.last_seen_at = now
                req.download_ids = list(dict.fromkeys([*(req.download_ids or []), *ids]))
                if req.priority:
                    wanted.extend(i for i in ids if i not in wanted)
                continue
            if req.service_type not in answered:
                continue  # file illisible : on ne conclut rien
            if req.subtitles == "searching" and not _too_long(req.imported_at, now):
                continue  # sous-titres en cours (lot 4) : prête juste après
            last = _aware(req.last_seen_at or req.grabbed_at or req.imported_at)
            if last is not None and (ready_now(req) or now - last > CLOSE_AFTER):
                req.status, req.closed_at = "done", now
                ready.append(req)
                closed += 1
            elif last is None and now - _aware(req.requested_at) > timedelta(
                hours=settings.TV_REQUEST_TTL_HOURS
            ):
                req.status, req.closed_at = "expired", now
                closed += 1
        await db.commit()
        for req in ready:
            await _announce_ready(req, now)

        stats = await _apply_sab(db, wanted)
    if stats["forced"] or stats["moved"] or closed:
        logger.info(
            "Priorité TV : %d en Force, %d déplacé(s), %d demande(s) fermée(s)",
            stats["forced"],
            stats["moved"],
            closed,
        )
    return {"open": len(requests) - closed, "closed": closed, "wanted": wanted, **stats}


# Sous-titres jamais revenus (tâche coupée par un redémarrage…) : prête quand même
SUBTITLES_GIVE_UP = timedelta(minutes=6)


def _too_long(imported_at: datetime | None, now: datetime) -> bool:
    imported = _aware(imported_at)
    return imported is None or now - imported > SUBTITLES_GIVE_UP


def ready_now(req: TvRequest) -> bool:
    """Prête dès l'import (et les sous-titres) : un film, ou un seul épisode.

    Une saison ou une série arrive en plusieurs NZB : on garde alors le délai
    CLOSE_AFTER, le temps que les épisodes suivants entrent dans la file.
    """
    if req.imported_at is None:
        return False
    return req.scope == "movie" or (req.scope == "episode" and len(req.episode_ids or []) <= 1)


def ready_event(req: TvRequest, now: datetime) -> dict[str, Any]:
    """Données de l'événement « tv_ready » (format de « Lire sur la TV » pour la lecture)."""
    info = dict(req.ready_info or {})
    return {
        "request_id": req.id,
        "device_id": req.device_id,
        "device_name": req.device_name,
        "room": req.room,
        "title": req.title,
        "subtitles": req.subtitles or "",
        "quality": info.get("quality") or "",
        "media_type": info.get("media_type") or ("movie" if req.service_type == "radarr" else ""),
        "id_type": info.get("id_type") or "",
        "id": info.get("id"),
        "season": info.get("season"),
        "episode": info.get("episode"),
        "service_type": req.service_type,
        "arr_id": req.arr_id,
        "at": now.isoformat(),
    }


async def _announce_ready(req: TvRequest, now: datetime) -> None:
    """Prévient la TV qui a lancé la demande (relevé des événements toutes les 5 s)."""
    from app.services.media_aggregator import find_artwork
    from app.utils.event_bus import event_bus

    data = ready_event(req, now)
    try:
        async with session_factory() as db:
            art = await find_artwork(
                db, "movie" if req.service_type == "radarr" else "series", data["id"], req.title
            )
        data["poster"] = art.get("poster") or ""
    except Exception:
        data["poster"] = ""
    await event_bus.publish("tv_ready", data)
    logger.info("Prêt à regarder : %s (TV %s)", req.title, req.device_name)


def kick(extra_records: list[dict[str, Any]] | None = None, delay: float = 0) -> None:
    """Lance une passe en arrière-plan (après un grab ou un webhook), sans l'attendre."""

    async def _run() -> None:
        if delay:
            await asyncio.sleep(delay)
        try:
            await enforce(extra_records)
        except Exception as exc:
            logger.warning("Priorité TV : passe en échec (%s)", exc)

    try:
        task = asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        return
    _background.add(task)
    task.add_done_callback(_background.discard)


async def on_grab(service_type: str, payload: dict[str, Any]) -> None:
    """Webhook « Grab » de Radarr / Sonarr : priorité posée dans la seconde."""
    records = records_from_grab(service_type, payload)
    if records:
        kick(records)


# ─────────────────────────────────────────────────────────────────────────────
# Actions de la TV sur la file
# ─────────────────────────────────────────────────────────────────────────────


async def queue_action(db: AsyncSession, download_id: str, action: str) -> dict[str, Any]:
    """pause | resume | top sur UN élément de SABnzbd (nzo_id = downloadId *arr).

    « top » : priorité High et place juste après les demandes TV (Force),
    qui restent devant.
    """
    if action not in ("pause", "resume", "top"):
        return {"status": "error", "message": f"Action inconnue : {action}"}
    for sab in await _sab_clients(db):
        try:
            slots = await sab.get_slots()
            slot = next((s for s in slots if s["nzo_id"] == download_id), None)
            if slot is None:
                continue
            if action == "pause":
                await sab.pause_item(download_id)
                return {"status": "ok", "message": "Mis en pause"}
            if action == "resume":
                await sab.resume_item(download_id)
                return {"status": "ok", "message": "Repris"}
            if str(slot.get("priority") or "").casefold() not in _HIGH_OR_MORE:
                await sab.set_priority(download_id, SAB_HIGH)
                slots = await sab.get_slots()
            forced = [
                s
                for s in _ordered(slots)
                if s["nzo_id"] != download_id
                and str(s.get("priority") or "").casefold() in _FORCE_LABELS
            ]
            await sab.move_to(download_id, len(forced))
            return {"status": "ok", "message": "Passé en tête de file"}
        except Exception as exc:
            logger.warning("Action %s sur %s impossible : %s", action, download_id, exc)
            return {"status": "error", "message": f"SABnzbd injoignable : {exc}"}
        finally:
            await sab.close()
    return {
        "status": "error",
        "message": "Pas dans la file SABnzbd (torrent, ou déjà terminé)",
    }


async def cancel_request(db: AsyncSession, request_id: int, user: dict[str, Any]) -> dict[str, Any]:
    """Annule une demande TV encore en cours.

    Seule la TV qui l'a lancée peut l'annuler (la web app aussi). On retire
    ses téléchargements de la file, sans blocklist, et si la demande avait
    ajouté le titre, on arrête sa surveillance pour qu'il ne revienne pas.
    La médiathèque n'est jamais touchée (seul le téléchargement en cours est
    retiré du client, avec ses fichiers partiels).
    """
    from app.services.activity_log import log_event

    req = await db.get(TvRequest, request_id)
    if req is None:
        return {"status": "error", "code": 404, "message": "Demande introuvable"}
    if user.get("role") == "device" and req.device_id != user.get("device_id"):
        return {
            "status": "error",
            "code": 403,
            "message": f"Seule la TV qui l'a lancée ({req.device_name}) peut l'annuler",
        }
    if req.status != "open":
        return {"status": "error", "code": 409, "message": "Cette demande est déjà terminée"}

    removed = 0
    for svc in await _services(db, (req.service_type,)):
        client = _arr_client(svc)
        try:
            data = await client.get_queue()
            rows = data.get("records", []) if isinstance(data, dict) else []
            done: set[str] = set()
            for rec in select_records(req, [record_from_queue(svc.type, r) for r in rows]):
                key = rec["download_id"] or f"id:{rec['queue_id']}"
                if key in done or rec.get("queue_id") is None:
                    continue
                with contextlib.suppress(Exception):
                    await client.remove_queue_item(
                        rec["queue_id"], remove_from_client=True, blocklist=False
                    )
                    removed += 1
                done.add(key)
            if req.added:
                await _stop_monitoring(client, req)
        except Exception as exc:
            logger.warning("Annulation de la demande %s incomplète : %s", req.id, exc)
        finally:
            await client.close()

    req.status, req.closed_at = "cancelled", _now()
    await db.commit()
    await log_event(
        category="download",
        action="tv_request_cancel",
        status="ok",
        source="kodi",
        media_type="movie" if req.service_type == "radarr" else "series",
        media_id=req.arr_id,
        title=req.title,
        device=origin_of(user)["device_name"] if user.get("role") == "device" else None,
        detail=f"{removed} téléchargement(s) retiré(s) de la file",
    )
    return {"status": "ok", "removed": removed, "message": f"« {req.title} » annulé"}


async def retry_request(db: AsyncSession, request_id: int, user: dict[str, Any]) -> dict[str, Any]:
    """« Relancer la recherche » d'une demande (rien trouvé, ou encore en recherche).

    Même portée que la demande (film, série, saison, épisodes) ; la demande
    repart comme neuve (ordre d'arrivée : maintenant), pour 24 h de plus.
    """
    from app.services.activity_log import log_event

    req = await db.get(TvRequest, request_id)
    if req is None:
        return {"status": "error", "code": 404, "message": "Demande introuvable"}
    if req.status not in ("open", "expired"):
        return {"status": "error", "code": 409, "message": "Cette demande est déjà terminée"}
    services = await _services(db, (req.service_type,))
    if not services:
        return {"status": "error", "code": 409, "message": "Service non configuré"}
    client = _arr_client(services[0])
    try:
        if isinstance(client, RadarrClient):
            await client.search_movie(req.arr_id)
        elif req.scope == "episode" and req.episode_ids:
            await client.search_episodes(list(req.episode_ids))
        elif req.scope == "season" and req.season is not None:
            await client.search_season(req.arr_id, req.season)
        else:
            await client.search_series(req.arr_id)
    except Exception as exc:
        logger.warning("Nouvelle recherche de la demande %s impossible : %s", req.id, exc)
        return {"status": "error", "code": 502, "message": f"Recherche impossible : {exc}"}
    finally:
        await client.close()
    req.status, req.closed_at = "open", None
    req.requested_at, req.grabbed_at, req.last_seen_at = _now(), None, None
    await db.commit()
    await log_event(
        category="media",
        action="tv_request_retry",
        status="ok",
        source="kodi",
        media_type="movie" if req.service_type == "radarr" else "series",
        media_id=req.arr_id,
        title=req.title,
        device=origin_of(user)["device_name"] if user.get("role") == "device" else None,
    )
    return {"status": "ok", "message": f"Nouvelle recherche lancée pour « {req.title} »"}


async def _stop_monitoring(client: RadarrClient | SonarrClient, req: TvRequest) -> None:
    """Arrête la surveillance de ce que la demande avait ajouté (rien n'est supprimé)."""
    if isinstance(client, RadarrClient):
        movie = await client.get_movie_by_id(req.arr_id)
        movie["monitored"] = False
        await client.update_movie(req.arr_id, movie)
    elif req.scope == "season" and req.season is not None:
        await client.set_season_monitored(req.arr_id, req.season, False)
    elif req.scope == "episode" and req.episode_ids:
        await client.put(
            "/episode/monitor", data={"episodeIds": req.episode_ids, "monitored": False}
        )
    else:
        series = await client.get_series_by_id(req.arr_id)
        series["monitored"] = False
        await client.update_series(req.arr_id, series)

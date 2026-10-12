"""Artworks des films et séries : logos, disques, clearart, bannières, vignettes.

Radarr et Sonarr ne fournissent que l'affiche, le fond et parfois un logo
(souvent en anglais). Ce module va chercher le reste :

  fanart.tv  logos HD, disques Blu-ray / DVD (films), clearart, bannières,
             vignettes. Clé personnelle gratuite : FANART_API_KEY.
  TMDB       logos (films et séries), avec la clé TMDB_API_KEY déjà utilisée
             par « Pour toi ».

Pour chaque type d'image, on garde la meilleure : français, puis anglais, puis
sans texte, et à langue égale la plus appréciée sur le site. Le résultat est
rangé en base (table media_artwork) ; la médiathèque, la fiche et la file de
téléchargement le fusionnent ensuite dans leurs réponses. Les écrans (web app,
Kodi) n'interrogent donc jamais fanart.tv ou TMDB au moment d'afficher.

Déclenchement :
  - bouton « Récupérer les artworks » de la web app (toute la médiathèque) ;
  - bouton « Actualiser les artworks » d'une fiche (un seul titre) ;
  - tâche planifiée (tasks/artwork_task.py) : les nouveaux titres, chaque jour.
Un titre déjà servi n'est redemandé qu'au bout de 30 jours (7 si rien n'avait
été trouvé, 1 h après une panne de réseau) : relancer le bouton est gratuit.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.artwork import MediaArtwork
from app.utils.logger import get_logger

logger = get_logger(__name__)

FANART_URL = "https://webservice.fanart.tv/v3"
TMDB_URL = "https://api.themoviedb.org/3"
TMDB_IMAGES = "https://image.tmdb.org/t/p"

# Base utilisée par la récupération en arrière-plan (remplacée par celle des tests)
session_factory = async_session_factory

# Requêtes simultanées vers fanart.tv / TMDB : assez pour aller vite sur une
# grosse médiathèque, assez peu pour rester poli avec des services gratuits.
CONCURRENCY = 4
TIMEOUT = 15

# Délais avant de redemander un titre (voir needs_refresh)
REFRESH_OK = timedelta(days=30)
REFRESH_EMPTY = timedelta(days=7)
REFRESH_ERROR = timedelta(hours=1)

# Champs d'images stockés, dans l'ordre d'affichage du diagnostic
FIELDS = ("clearlogo", "discart", "clearart", "banner", "landscape", "poster", "fanart")

# fanart.tv : pour chaque image, les rubriques à essayer (HD d'abord)
FANART_SECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "movie": {
        "clearlogo": ("hdmovielogo", "movielogo"),
        "discart": ("moviedisc",),
        "clearart": ("hdmovieclearart", "movieart"),
        "banner": ("moviebanner",),
        "landscape": ("moviethumb",),
        "poster": ("movieposter",),
        "fanart": ("moviebackground",),
    },
    "series": {
        "clearlogo": ("hdtvlogo", "clearlogo"),
        "clearart": ("hdclearart", "clearart"),
        "banner": ("tvbanner",),
        "landscape": ("tvthumb",),
        "poster": ("tvposter",),
        "fanart": ("showbackground",),
    },
}

# Langues préférées (« 00 » et vide = image sans texte)
_LANG_RANK = {"fr": 0, "en": 1, "00": 2, "": 2}
# Disques : Blu-ray d'abord (c'est ce que montre le boîtier), le 3D en dernier
_DISC_RANK = {"bluray": 0, "dvd": 1, "3d": 2}


# ── Choix des images (fonctions pures, testées) ──────────────────────────────


def lang_rank(lang: Any) -> int:
    """Rang d'une langue : français 0, anglais 1, sans texte 2, autre 3."""
    return _LANG_RANK.get(str(lang if lang is not None else "").strip().lower(), 3)


def _likes(image: dict[str, Any]) -> int:
    try:
        return int(image.get("likes") or 0)
    except (TypeError, ValueError):
        return 0


def pick_fanart(data: dict[str, Any], sections: tuple[str, ...]) -> dict[str, Any] | None:
    """Meilleure image fanart.tv parmi `sections` : langue, puis rubrique HD, puis « likes »."""
    candidates = []
    for order, section in enumerate(sections):
        for image in data.get(section) or []:
            if isinstance(image, dict) and str(image.get("url") or "").startswith("http"):
                candidates.append(
                    (
                        lang_rank(image.get("lang")),
                        order,
                        _DISC_RANK.get(str(image.get("disc_type") or "").lower(), 3),
                        -_likes(image),
                        image,
                    )
                )
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[:4])[4]


def parse_fanart(data: dict[str, Any], media_type: str) -> dict[str, str]:
    """Réponse fanart.tv → {champ: url} (+ « disc_type » quand un disque est trouvé)."""
    found: dict[str, str] = {}
    if not isinstance(data, dict):
        return found
    for field, sections in FANART_SECTIONS.get(media_type, {}).items():
        image = pick_fanart(data, sections)
        if image is None:
            continue
        found[field] = str(image["url"])
        if field == "discart":
            found["disc_type"] = str(image.get("disc_type") or "bluray").lower()
    return found


def parse_tmdb_logo(data: dict[str, Any]) -> str:
    """Meilleur logo TMDB (PNG : Kodi ne sait pas afficher le SVG), URL en 500 px."""
    logos = []
    for logo in (data or {}).get("logos") or []:
        path = str((logo or {}).get("file_path") or "")
        if not path or path.lower().endswith(".svg"):
            continue
        try:
            votes = float(logo.get("vote_average") or 0)
        except (TypeError, ValueError):
            votes = 0.0
        logos.append((lang_rank(logo.get("iso_639_1") or "00"), -votes, path))
    if not logos:
        return ""
    return f"{TMDB_IMAGES}/w500{min(logos)[2]}"


def needs_refresh(
    status: str | None, fetched_at: datetime | None, now: datetime, force: bool = False
) -> bool:
    """Faut-il redemander ce titre ? (jamais demandé, ou réponse trop ancienne)."""
    if force or status is None or fetched_at is None:
        return True
    if fetched_at.tzinfo is None:  # SQLite rend des dates sans fuseau
        fetched_at = fetched_at.replace(tzinfo=UTC)
    delay = {"ok": REFRESH_OK, "empty": REFRESH_EMPTY}.get(status, REFRESH_ERROR)
    return now - fetched_at >= delay


def artwork_key(media_type: str, provider_id: Any) -> str:
    """« movie:438631 » (TMDB) ou « series:280619 » (TVDB)."""
    return f"{media_type}:{provider_id}"


def sources_configured() -> dict[str, bool]:
    return {"fanart": bool(settings.FANART_API_KEY), "tmdb": bool(settings.TMDB_API_KEY)}


# ── Récupération d'un titre ─────────────────────────────────────────────────


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, str]) -> Any:
    """GET JSON ; None si le titre est inconnu du site (404). Lève sur panne."""
    response = await client.get(url, params=params)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def fetch_artwork(
    client: httpx.AsyncClient,
    media_type: str,
    provider_id: int,
    tmdb_tv_id: int | None = None,
) -> dict[str, Any]:
    """Interroge fanart.tv puis TMDB pour un titre.

    Renvoie {"fields": {champ: url, "disc_type"}, "sources": [...], "status"} :
    status « ok » si au moins une image, « empty » si les sites n'ont rien,
    « error » si un site était injoignable et que rien n'a été trouvé.
    """
    fields: dict[str, str] = {}
    sources: list[str] = []
    failed = False

    if settings.FANART_API_KEY:
        section = "movies" if media_type == "movie" else "tv"
        try:
            data = await _get_json(
                client,
                f"{FANART_URL}/{section}/{provider_id}",
                {"api_key": settings.FANART_API_KEY},
            )
            if data:
                sources.append("fanart.tv")
                fields.update(parse_fanart(data, media_type))
        except (httpx.HTTPError, ValueError) as exc:
            failed = True
            logger.debug("fanart.tv %s %s : %s", media_type, provider_id, exc)

    tmdb_id = provider_id if media_type == "movie" else tmdb_tv_id
    if settings.TMDB_API_KEY and tmdb_id and not fields.get("clearlogo"):
        kind = "movie" if media_type == "movie" else "tv"
        try:
            data = await _get_json(
                client,
                f"{TMDB_URL}/{kind}/{tmdb_id}/images",
                {"api_key": settings.TMDB_API_KEY, "include_image_language": "fr,en,null"},
            )
            logo = parse_tmdb_logo(data or {})
            if data is not None:
                sources.append("tmdb")
            if logo:
                fields["clearlogo"] = logo
        except (httpx.HTTPError, ValueError) as exc:
            failed = True
            logger.debug("TMDB images %s %s : %s", kind, tmdb_id, exc)

    found = any(fields.get(f) for f in FIELDS)
    status = "ok" if found else ("error" if failed else "empty")
    return {"fields": fields, "sources": sources, "status": status}


# ── Base de données ─────────────────────────────────────────────────────────


async def load_rows(db: AsyncSession) -> dict[str, MediaArtwork]:
    rows = (await db.execute(select(MediaArtwork))).scalars().all()
    return {row.key: row for row in rows}


async def upsert(db: AsyncSession, values: list[dict[str, Any]]) -> None:
    """INSERT … ON CONFLICT (key) DO UPDATE, PostgreSQL comme SQLite."""
    if not values:
        return
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(MediaArtwork).values(values)
    updated = {c: stmt.excluded[c] for c in values[0] if c != "key"}
    await db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_=updated))
    await db.commit()


def _row_values(item: dict[str, Any], result: dict[str, Any], now: datetime) -> dict[str, Any]:
    fields = result["fields"]
    return {
        "key": artwork_key(item["media_type"], item["provider_id"]),
        "media_type": item["media_type"],
        "provider_id": int(item["provider_id"]),
        "title": str(item.get("title") or "")[:300],
        **{f: str(fields.get(f) or "")[:500] for f in FIELDS},
        "disc_type": str(fields.get("disc_type") or "")[:20],
        "sources": ",".join(result["sources"])[:60],
        "status": result["status"],
        "fetched_at": now,
    }


def as_images(row: MediaArtwork | None) -> dict[str, str]:
    """Ligne en base → {champ: url} (champs vides omis)."""
    if row is None:
        return {}
    images = {f: getattr(row, f) for f in FIELDS if getattr(row, f)}
    if row.discart and row.disc_type:
        images["disc_type"] = row.disc_type
    return images


# ── Fusion dans les réponses existantes ─────────────────────────────────────


async def apply_to_library(items: list[dict[str, Any]]) -> None:
    """Complète les éléments de la médiathèque (mêmes clés que media_aggregator).

    Le logo trouvé ici (français d'abord) passe devant celui de Radarr/Sonarr ;
    l'affiche et le fond de Radarr/Sonarr restent prioritaires (choisis par
    l'utilisateur), ceux d'ici ne servent qu'à combler un manque.

    Lecture dans une session À PART : la médiathèque est parfois calculée en
    parallèle d'autres lectures sur la session de l'appelant (tableau de bord
    Kodi), et une connexion PostgreSQL refuse deux requêtes simultanées.
    """
    try:
        async with session_factory() as db:
            rows = await load_rows(db)
    except Exception as exc:  # jamais bloquant pour la médiathèque
        logger.debug("Artworks indisponibles : %s", exc)
        return
    if not rows:
        return
    for item in items:
        if item.get("type") not in ("movie", "series") or not item.get("tmdb_id"):
            continue
        images = as_images(rows.get(artwork_key(item["type"], item["tmdb_id"])))
        if not images:
            continue
        if images.get("clearlogo"):
            item["clearlogo_url"] = images["clearlogo"]
        for field in ("discart", "clearart", "banner", "landscape"):
            if images.get(field):
                item[f"{field}_url"] = images[field]
        if images.get("disc_type"):
            item["disc_type"] = images["disc_type"]
        for field in ("poster", "fanart"):
            if images.get(field) and not item.get(f"{field}_url"):
                item[f"{field}_url"] = images[field]


async def merge_detail_images(
    db: AsyncSession, media_type: str, provider_id: Any, images: dict[str, Any]
) -> dict[str, Any]:
    """Complète le dict `images` d'une fiche (poster, fanart, banner, clearlogo…)."""
    if not provider_id:
        return images
    try:
        row = (
            await db.execute(
                select(MediaArtwork).where(MediaArtwork.key == artwork_key(media_type, provider_id))
            )
        ).scalar_one_or_none()
    except Exception as exc:
        logger.debug("Artworks indisponibles : %s", exc)
        return images
    found = as_images(row)
    merged = dict(images)
    if found.get("clearlogo"):
        merged["clearlogo"] = found["clearlogo"]
    for field in ("discart", "disc_type", "clearart", "landscape"):
        if found.get(field):
            merged[field] = found[field]
    for field in ("poster", "fanart", "banner"):
        if found.get(field) and not merged.get(field):
            merged[field] = found[field]
    return merged


# ── Récupération sur toute la médiathèque ───────────────────────────────────

_progress: dict[str, Any] = {
    "running": False,
    "total": 0,
    "done": 0,
    "found": 0,
    "errors": 0,
    "skipped": 0,
    "force": False,
    "started_at": None,
    "finished_at": None,
    "message": "",
}
_task: asyncio.Task | None = None


def library_targets(library: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Titres de la médiathèque à traiter : films (TMDB) et séries (TVDB) identifiés."""
    targets = []
    seen = set()
    for item in library:
        media_type = item.get("type")
        provider_id = item.get("tmdb_id")  # séries : TVDB (convention media_aggregator)
        if media_type not in ("movie", "series") or not str(provider_id or "").isdigit():
            continue
        key = artwork_key(media_type, provider_id)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            {
                "media_type": media_type,
                "provider_id": int(provider_id),
                "tmdb_tv_id": item.get("tmdb_tv_id"),
                "title": item.get("title") or "",
                "external_id": item.get("external_id"),
            }
        )
    return targets


async def refresh_targets(
    db: AsyncSession, targets: list[dict[str, Any]], force: bool = False, track: bool = True
) -> dict[str, int]:
    """Récupère les artworks des `targets` qui en ont besoin et les range en base.

    `track` : met à jour la progression affichée par la web app (faux pour le
    bouton d'une fiche, qui ne doit pas brouiller une récupération globale).
    """
    progress = _progress if track else {"done": 0}
    now = datetime.now(UTC)
    rows = await load_rows(db)
    todo = []
    for target in targets:
        row = rows.get(artwork_key(target["media_type"], target["provider_id"]))
        if needs_refresh(row.status if row else None, row.fetched_at if row else None, now, force):
            todo.append(target)
    counts = {"total": len(todo), "found": 0, "errors": 0, "skipped": len(targets) - len(todo)}
    progress.update(total=len(todo), done=0, found=0, errors=0, skipped=counts["skipped"])
    if not todo:
        return counts

    semaphore = asyncio.Semaphore(CONCURRENCY)
    batch: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:

        async def _one(target: dict[str, Any]) -> None:
            async with semaphore:
                result = await fetch_artwork(
                    client, target["media_type"], target["provider_id"], target.get("tmdb_tv_id")
                )
            batch.append(_row_values(target, result, datetime.now(UTC)))
            if result["status"] == "ok":
                counts["found"] += 1
            elif result["status"] == "error":
                counts["errors"] += 1
            progress.update(
                done=progress["done"] + 1, found=counts["found"], errors=counts["errors"]
            )

        # Par paquets : la base reçoit les résultats au fil de l'eau (un arrêt
        # du serveur en cours de route ne perd pas tout le travail fait).
        for start in range(0, len(todo), 50):
            await asyncio.gather(*(_one(t) for t in todo[start : start + 50]))
            await upsert(db, batch)
            batch.clear()
    return counts


def _invalidate_library_cache() -> None:
    from app.utils.cache import cache

    cache.invalidate("media:all")


async def refresh_library(force: bool = False) -> dict[str, int]:
    """Toute la médiathèque (bouton de la web app, tâche planifiée)."""
    from app.services import media_aggregator
    from app.services.activity_log import log_event

    started = time.monotonic()
    _progress.update(
        running=True,
        force=force,
        started_at=datetime.now(UTC).isoformat(),
        finished_at=None,
        message="Lecture de la médiathèque…",
    )
    counts = {"total": 0, "found": 0, "errors": 0, "skipped": 0}
    try:
        if not any(sources_configured().values()):
            _progress["message"] = "Aucune source configurée (FANART_API_KEY ou TMDB_API_KEY)"
            return counts
        async with session_factory() as db:
            library = await media_aggregator.fetch_all_media(db)
            _progress["message"] = "Récupération en cours…"
            counts = await refresh_targets(db, library_targets(library), force)
        _invalidate_library_cache()
        _progress["message"] = (
            f"{counts['found']} titre(s) avec des artworks sur {counts['total']} interrogé(s)"
            + (f", {counts['errors']} en échec" if counts["errors"] else "")
        )
        if counts["total"]:
            await log_event(
                category="library",
                action="artwork_refresh",
                status="error" if counts["errors"] and not counts["found"] else "ok",
                title="Artworks récupérés",
                detail=_progress["message"],
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        logger.info("Artworks : %s", _progress["message"])
        return counts
    except Exception as exc:
        logger.error("Récupération des artworks interrompue : %s", exc)
        _progress["message"] = f"Interrompue : {exc}"
        return counts
    finally:
        _progress.update(running=False, finished_at=datetime.now(UTC).isoformat())


def start_refresh(force: bool = False) -> bool:
    """Lance la récupération en arrière-plan ; False si elle tourne déjà."""
    global _task
    if _progress["running"] or (_task is not None and not _task.done()):
        return False
    _progress["running"] = True  # avant même le premier `await` du travail
    _task = asyncio.get_running_loop().create_task(refresh_library(force))
    return True


async def wait_for_refresh() -> None:
    """Attend la fin de la récupération en cours (tests, arrêt propre)."""
    if _task is not None:
        await _task


async def refresh_one(db: AsyncSession, media_type: str, arr_id: int) -> dict[str, Any] | None:
    """Un seul titre, tout de suite (bouton d'une fiche). None si titre inconnu."""
    from app.services import media_aggregator

    library = await media_aggregator.fetch_all_media(db)
    item = next(
        (
            m
            for m in library
            if m.get("type") == media_type and str(m.get("external_id")) == str(arr_id)
        ),
        None,
    )
    targets = library_targets([item] if item else [])
    if not targets:
        return None
    await refresh_targets(db, targets, force=True, track=False)
    _invalidate_library_cache()
    row = (
        await db.execute(
            select(MediaArtwork).where(
                MediaArtwork.key == artwork_key(media_type, targets[0]["provider_id"])
            )
        )
    ).scalar_one_or_none()
    return {"status": row.status if row else "empty", "images": as_images(row)}


async def status(db: AsyncSession) -> dict[str, Any]:
    """Progression en cours + bilan de la base (pour la web app)."""
    rows = await db.execute(
        select(
            func.count(MediaArtwork.id),
            func.count(MediaArtwork.id).filter(MediaArtwork.clearlogo != ""),
            func.count(MediaArtwork.id).filter(MediaArtwork.discart != ""),
            func.count(MediaArtwork.id).filter(MediaArtwork.clearart != ""),
        )
    )
    total, logos, discs, cleararts = rows.one()
    return {
        **_progress,
        "sources": sources_configured(),
        "stored": {"titles": total, "logos": logos, "discs": discs, "clearart": cleararts},
    }

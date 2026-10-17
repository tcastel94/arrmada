"""Sous-titres cherchés dès l'import, et « Prêt à regarder » (ADR-005, lot 4).

Pour une demande lancée depuis la TV, on n'attend pas la tâche planifiée de
Bazarr : au webhook « Download » (fichier importé par Radarr / Sonarr), le
serveur
  1. note l'import sur la demande, avec de quoi lancer la lecture sur la TV
     (ids publics, saison / épisode) ;
  2. lance en arrière-plan la recherche Bazarr : français d'abord (complets,
     puis forcés), relancée toutes les SUBS_POLL secondes pendant SUBS_WAIT
     (Bazarr met un moment à découvrir le nouveau fichier) ; rien en français
     au bout du délai : anglais ;
  3. pose sur le titre le profil de langues Bazarr qui contient le français
     s'il n'en a pas (Bazarr continuera de chercher tout seul ensuite).
Le gardien de priorité (services/tv_priority.py) ferme alors la demande et
publie l'événement « tv_ready » pour la TV qui l'avait lancée.

Bazarr absent ou en panne : la demande devient prête quand même, sans
sous-titres (« off » / « missing ») ; les sous-titres automatiques pendant la
lecture (appli 1.17) restent le filet de sécurité.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.models.tv_request import TvRequest
from app.services import tv_priority
from app.utils.logger import get_logger

logger = get_logger(__name__)

SUBS_WAIT = 180.0  # s : recherche en français avant de se rabattre sur l'anglais
SUBS_POLL = 20.0  # s entre deux essais (remplacés par les tests)
LANG_FIRST = "fr"
LANG_FALLBACK = "en"

_jobs: set[asyncio.Task] = set()


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions pures (testées sans réseau)
# ─────────────────────────────────────────────────────────────────────────────


def import_targets(service_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Ce que le webhook « Download » vient d'importer (film, ou série + épisodes)."""
    if service_type == "radarr":
        movie = payload.get("movie") if isinstance(payload.get("movie"), dict) else {}
        if not movie.get("id"):
            return None
        return {"service_type": "radarr", "movie_id": movie["id"], "tmdb_id": movie.get("tmdbId")}
    series = payload.get("series") if isinstance(payload.get("series"), dict) else {}
    if not series.get("id"):
        return None
    episodes = [e for e in payload.get("episodes") or [] if isinstance(e, dict) and e.get("id")]
    return {
        "service_type": "sonarr",
        "series_id": series["id"],
        "tvdb_id": series.get("tvdbId"),
        "episodes": [
            {"id": e["id"], "season": e.get("seasonNumber"), "number": e.get("episodeNumber")}
            for e in episodes
        ],
    }


def import_records(targets: dict[str, Any]) -> list[dict[str, Any]]:
    """Mêmes « éléments de file » que le gardien, pour réutiliser son rapprochement."""
    base = {"service_type": targets["service_type"], "download_id": "", "title": ""}
    if targets["service_type"] == "radarr":
        return [{**base, "movie_id": targets["movie_id"]}]
    episodes = targets["episodes"] or [{"id": None, "season": None}]
    return [
        {**base, "series_id": targets["series_id"], "episode_id": e["id"], "season": e["season"]}
        for e in episodes
    ]


def ready_info(targets: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """De quoi lancer la lecture sur la TV (format de l'événement « Lire sur la TV »)."""
    file = payload.get("movieFile") or payload.get("episodeFile") or {}
    quality = file.get("quality") if isinstance(file, dict) else ""
    info: dict[str, Any] = {"quality": quality if isinstance(quality, str) else ""}
    if targets["service_type"] == "radarr":
        info.update(media_type="movie", id_type="tmdb", id=targets.get("tmdb_id"))
        return info
    first = (targets["episodes"] or [{}])[0]
    info.update(
        media_type="episode",
        id_type="tvdb",
        id=targets.get("tvdb_id"),
        season=first.get("season"),
        episode=first.get("number"),
    )
    return info


def has_language(item: dict[str, Any] | None, language: str) -> bool:
    """Un film / épisode Bazarr a-t-il un sous-titre dans cette langue ?"""
    for sub in (item or {}).get("subtitles") or []:
        # Sous-titre externe (fichier .srt) ou intégré au fichier vidéo : les deux comptent
        if str(sub.get("code2") or sub.get("code") or "").casefold() == language:
            return True
    return False


def french_profile(profiles: Any) -> int | None:
    """Premier profil de langues Bazarr qui contient le français."""
    for profile in profiles or []:
        items = (profile.get("items") or []) if isinstance(profile, dict) else []
        if any(str(i.get("language") or "").casefold() == LANG_FIRST for i in items):
            return profile.get("profileId")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Webhook « Download »
# ─────────────────────────────────────────────────────────────────────────────


async def on_import(service_type: str, payload: dict[str, Any]) -> list[int]:
    """Import d'un titre demandé depuis la TV : note l'import, lance les sous-titres.

    Renvoie les numéros des demandes concernées (vide : import ordinaire).
    """
    targets = import_targets(service_type, payload)
    if targets is None:
        return []
    records = import_records(targets)
    now = datetime.now(UTC)
    matched: list[int] = []
    async with tv_priority.session_factory() as db:
        rows = await db.execute(
            select(TvRequest).where(
                TvRequest.status == "open", TvRequest.service_type == service_type
            )
        )
        bazarr = await _bazarr(db)
        has_bazarr = bazarr is not None
        if bazarr:
            await bazarr.close()
        for req in rows.scalars().all():
            if not any(tv_priority.in_scope(req, r) for r in records):
                continue
            req.imported_at = now
            req.ready_info = ready_info(targets, payload)
            req.subtitles = "searching" if has_bazarr else "off"
            matched.append(req.id)
        await db.commit()
    if not matched:
        return []
    logger.info("Demande(s) TV importée(s) %s : sous-titres en recherche", matched)
    if has_bazarr:
        _spawn(_search(matched, targets))
    else:
        tv_priority.kick()  # pas de Bazarr : prête tout de suite
    return matched


def _spawn(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)


async def _bazarr(db):
    from app.services import kodi

    return await kodi._get_bazarr_client(db)


# ─────────────────────────────────────────────────────────────────────────────
# Recherche Bazarr (tâche de fond)
# ─────────────────────────────────────────────────────────────────────────────


async def _items(bazarr, targets: dict[str, Any]) -> list[dict[str, Any]]:
    """Fiches Bazarr du film / des épisodes importés (vide : pas encore connues)."""
    if targets["service_type"] == "radarr":
        data = await bazarr.get("/movies", params={"radarrid[]": targets["movie_id"]})
    else:
        ids = [e["id"] for e in targets["episodes"]]
        if not ids:
            return []
        data = await bazarr.get("/episodes", params={"episodeid[]": ids})
    rows = data.get("data") if isinstance(data, dict) else data
    return [r for r in rows or [] if isinstance(r, dict)]


async def _ensure_profile(bazarr, targets: dict[str, Any], items: list[dict[str, Any]]) -> None:
    """Titre sans profil de langues dans Bazarr : on lui met celui du français."""
    if not items or any(i.get("profileId") for i in items):
        return
    profile = french_profile(await bazarr.get("/system/languages/profiles"))
    if profile is None:
        return
    if targets["service_type"] == "radarr":
        await bazarr._request_params(
            "POST", "/movies", {"radarrid": targets["movie_id"], "profileid": profile}
        )
    else:
        await bazarr._request_params(
            "POST", "/series", {"seriesid": targets["series_id"], "profileid": profile}
        )


async def _attempt(bazarr, targets: dict[str, Any], language: str) -> bool:
    """Un essai : téléchargement Bazarr dans `language`, puis vérification."""
    items = await _items(bazarr, targets)
    if not items:
        return False  # Bazarr n'a pas encore vu le nouveau fichier
    if all(has_language(i, language) for i in items):
        return True  # Bazarr l'a déjà fait tout seul
    await _ensure_profile(bazarr, targets, items)
    for forced in (False, True) if language == LANG_FIRST else (False,):
        try:
            if targets["service_type"] == "radarr":
                await bazarr.download_movie_subtitle(
                    radarr_id=targets["movie_id"], language=language, forced=forced
                )
            else:
                for episode in targets["episodes"]:
                    await bazarr.download_episode_subtitle(
                        series_id=targets["series_id"],
                        episode_id=episode["id"],
                        language=language,
                        forced=forced,
                    )
        except Exception as exc:  # rien trouvé chez les fournisseurs : on réessaiera
            logger.debug("Bazarr %s (forcés=%s) : %s", language, forced, exc)
    return all(has_language(i, language) for i in await _items(bazarr, targets))


async def _search(request_ids: list[int], targets: dict[str, Any]) -> None:
    result = "missing"
    try:
        async with tv_priority.session_factory() as db:
            bazarr = await _bazarr(db)
        if bazarr is None:
            result = "off"
        else:
            try:
                waited = 0.0
                while True:
                    try:
                        if await _attempt(bazarr, targets, LANG_FIRST):
                            result = LANG_FIRST
                            break
                    except Exception as exc:
                        logger.debug("Sous-titres : Bazarr injoignable (%s)", exc)
                    if waited >= SUBS_WAIT:
                        break
                    await asyncio.sleep(SUBS_POLL)
                    waited += SUBS_POLL
                if result != LANG_FIRST:
                    try:
                        if await _attempt(bazarr, targets, LANG_FALLBACK):
                            result = LANG_FALLBACK
                    except Exception as exc:
                        logger.debug("Sous-titres anglais : %s", exc)
            finally:
                await bazarr.close()
    finally:
        async with tv_priority.session_factory() as db:
            for request_id in request_ids:
                req = await db.get(TvRequest, request_id)
                if req is not None and req.subtitles == "searching":
                    req.subtitles = result
            await db.commit()
        logger.info("Sous-titres des demandes TV %s : %s", request_ids, result)
        tv_priority.kick()  # le gardien ferme la demande et prévient la TV

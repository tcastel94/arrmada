"""Gardien des sous-titres : les chercher AVANT la séance, pas pendant.

Le menu pause et la fiche ne sont qu'un dernier recours : quand toute la
famille est installée, attendre Bazarr deux minutes est déjà de trop. Ce
gardien passe toutes les SUBTITLE_GUARDIAN_INTERVAL_MINUTES minutes (comme
une tâche planifiée Control-M) et :

  1. **pose le profil de langues « français »** sur les séries et films de
     Bazarr qui n'en ont aucun. Sans profil, Bazarr ne cherche JAMAIS ces
     titres de lui-même : c'est le cas de beaucoup d'animes ajoutés
     directement dans Sonarr ;
  2. lit la liste « il manque des sous-titres français » de Bazarr et en
     cherche quelques-uns par passage (SUBTITLE_GUARDIAN_BATCH), **les
     épisodes des séries en cours d'abord** (vues ces 30 derniers jours :
     l'épisode suivant est probablement celui de ce soir) ;
  3. **espace les essais** d'un même titre : 1 h, 3 h, 6 h, 12 h, 24 h, 2 j,
     4 j puis 7 j. Le sous-titre d'un fansub arrive souvent quelques jours
     après l'épisode ; chercher en boucle ferait bloquer les fournisseurs.

Les recherches passent par la file des sous-titres (subtitle_jobs), dans sa
file « de fond » : une demande faite devant la TV passe toujours devant.

Le même mécanisme sert au **préchargement** : ouvrir la fiche d'un film ou
lancer un épisode sans sous-titre français lance la recherche en fond (et
celle de l'épisode suivant), pendant qu'on lit le résumé ou le générique.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select

from app.config import settings
from app.database import async_session_factory
from app.models.subtitle_search import SubtitleSearch
from app.services import subtitle_jobs as sj
from app.utils.logger import get_logger

logger = get_logger(__name__)

session_factory = async_session_factory  # remplacée par les tests

# Délai avant l'essai suivant, selon le nombre d'essais déjà faits (heures)
RETRY_HOURS = (1, 3, 6, 12, 24, 48, 96, 168)
IN_PROGRESS_DAYS = 30  # série « en cours » : un épisode vu ces N derniers jours
FORGET_DAYS = 90  # ligne sans nouvel essai depuis N jours : oubliée
PROFILE_BATCH = 50  # profils posés au plus par passage (Bazarr reste réactif)

_lock = asyncio.Lock()
_last: dict[str, Any] = {}  # résumé du dernier passage (page Santé, journal)


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions pures (testées sans réseau)
# ─────────────────────────────────────────────────────────────────────────────


def next_delay(attempts: int) -> timedelta:
    """Délai avant le prochain essai après [attempts] essais infructueux."""
    index = max(0, min(attempts, len(RETRY_HOURS)) - 1)
    return timedelta(hours=RETRY_HOURS[index])


def _has_missing(row: dict[str, Any], language: str) -> bool:
    return any(
        sj.code2((m or {}).get("code2")) == language and not sj._truthy((m or {}).get("forced"))
        for m in row.get("missing_subtitles") or []
        if isinstance(m, dict)
    )


def wanted_targets(
    episodes: Any, movies: Any, language: str, in_progress: set[int]
) -> list[sj.Target]:
    """Listes « wanted » de Bazarr → cibles, dans l'ordre où les chercher.

    Ordre : épisodes des séries en cours (séries Sonarr [in_progress]), du
    plus ancien au plus récent (l'épisode suivant d'abord) ; puis les films
    (soirées cinéma), puis les autres épisodes ; les plus récemment ajoutés
    d'abord (identifiant le plus grand).
    """
    urgent: list[tuple[int, sj.Target]] = []
    films: list[tuple[int, sj.Target]] = []
    others: list[tuple[int, sj.Target]] = []
    for row in episodes if isinstance(episodes, list) else []:
        if not isinstance(row, dict) or not _has_missing(row, language):
            continue
        series_id, episode_id = row.get("sonarrSeriesId"), row.get("sonarrEpisodeId")
        if not series_id or not episode_id:
            continue
        target = sj.Target(
            kind="episode", language=language, series_id=int(series_id),
            episode_id=int(episode_id), title=str(row.get("seriesTitle") or ""),
        )  # fmt: skip
        (urgent if int(series_id) in in_progress else others).append((int(episode_id), target))
    for row in movies if isinstance(movies, list) else []:
        if not isinstance(row, dict) or not _has_missing(row, language) or not row.get("radarrId"):
            continue
        target = sj.Target(
            kind="movie", language=language, radarr_id=int(row["radarrId"]),
            title=str(row.get("title") or ""),
        )  # fmt: skip
        films.append((int(row["radarrId"]), target))
    urgent.sort(key=lambda t: t[0])
    films.sort(key=lambda t: -t[0])
    others.sort(key=lambda t: -t[0])
    return [t for _, t in urgent] + [t for _, t in films] + [t for _, t in others]


def in_progress_tvdb(keys: list[str]) -> set[int]:
    """Clés de vu / reprise (« episode:tvdb:280619:2:5 ») → séries TVDB."""
    out = set()
    for key in keys:
        parts = key.split("|")[-1].split(":")  # « 3|episode:… » : profil famille devant
        if len(parts) >= 3 and parts[0] == "episode" and parts[1] == "tvdb" and parts[2].isdigit():
            out.add(int(parts[2]))
    return out


def _rows(data: Any) -> list[dict[str, Any]]:
    rows = data.get("data") if isinstance(data, dict) else data
    return [r for r in rows or [] if isinstance(r, dict)]


# ─────────────────────────────────────────────────────────────────────────────
# Passage du gardien
# ─────────────────────────────────────────────────────────────────────────────


async def run_once() -> dict[str, Any]:
    """Un passage : profils manquants, puis quelques recherches dues."""
    if _lock.locked():
        return {"status": "busy"}
    async with _lock:
        summary = await _pass()
    _last.clear()
    _last.update(summary, at=datetime.now(UTC).isoformat())
    return summary


def last_run() -> dict[str, Any]:
    return dict(_last)


async def _pass() -> dict[str, Any]:
    from app.services import kodi

    language = sj.code2(settings.SUBTITLE_LANGUAGE) or "fr"
    async with session_factory() as db:
        bazarr = await kodi._get_bazarr_client(db)
    if bazarr is None:
        return {"status": "off"}
    bazarr.timeout = 60
    try:
        series = _rows(await bazarr.get_series())
        movies = _rows(await bazarr.get_movies())
        profiles = await _assign_profiles(bazarr, series, movies)
        wanted_eps = _rows(await bazarr.get_wanted_series())
        wanted_movies = _rows(await bazarr.get_wanted_movies())
    except Exception as exc:  # Bazarr en panne : on réessaiera au prochain passage
        logger.info("Gardien des sous-titres : Bazarr injoignable (%s)", exc)
        return {"status": "bazarr_down"}
    finally:
        await bazarr.close()

    in_progress = await _in_progress_series(series)
    targets = wanted_targets(wanted_eps, wanted_movies, language, in_progress)
    due = await _due(targets)
    searched = found = 0
    for target in due[: max(0, settings.SUBTITLE_GUARDIAN_BATCH)]:
        if sj.running(background=False):
            break  # quelqu'un attend devant la TV : on lui laisse Bazarr
        job = sj.start(target, origin="guardian", reuse_done=False)
        await job.done.wait()
        searched += 1
        found += job.status == "found"
        await _record(target, job)
    await _forget_old()
    summary = {
        "status": "ok",
        "profiles_set": profiles,
        "wanted": len(targets),
        "due": len(due),
        "searched": searched,
        "found": found,
    }
    if searched or profiles:
        logger.info("Gardien des sous-titres : %s", summary)
    return summary


async def _assign_profiles(bazarr: Any, series: list[dict], movies: list[dict]) -> int:
    """Profil « français » sur les titres sans profil (PROFILE_BATCH au plus)."""
    from app.services.tv_subtitles import french_profile

    if not settings.SUBTITLE_GUARDIAN_ASSIGN_PROFILES:
        return 0
    bare_series = [s for s in series if not s.get("profileId") and s.get("sonarrSeriesId")]
    bare_movies = [m for m in movies if not m.get("profileId") and m.get("radarrId")]
    if not bare_series and not bare_movies:
        return 0
    profile = french_profile(await bazarr.get("/system/languages/profiles"))
    if profile is None:
        return 0
    done = 0
    for row in bare_series[:PROFILE_BATCH]:
        code, _ = await bazarr.request_raw(
            "POST", "/series", {"seriesid": row["sonarrSeriesId"], "profileid": profile}
        )
        done += code < 300
    for row in bare_movies[: max(0, PROFILE_BATCH - len(bare_series))]:
        code, _ = await bazarr.request_raw(
            "POST", "/movies", {"radarrid": row["radarrId"], "profileid": profile}
        )
        done += code < 300
    return done


async def _in_progress_series(series: list[dict]) -> set[int]:
    """Séries Sonarr dont un épisode a été vu ces IN_PROGRESS_DAYS derniers jours."""
    from app.models.watch_state import WatchState

    since = datetime.now(UTC) - timedelta(days=IN_PROGRESS_DAYS)
    async with session_factory() as db:
        keys = (
            (
                await db.execute(
                    select(WatchState.key).where(
                        WatchState.media_type == "episode", WatchState.updated_at >= since
                    )
                )
            )
            .scalars()
            .all()
        )
    tvdb = in_progress_tvdb(list(keys))
    return {
        int(s["sonarrSeriesId"])
        for s in series
        if s.get("sonarrSeriesId")
        and str(s.get("tvdbId") or "").isdigit()
        and int(s["tvdbId"]) in tvdb
    }


async def _due(targets: list[sj.Target]) -> list[sj.Target]:
    """Cibles dont l'essai suivant est arrivé (ou jamais essayées)."""
    now = datetime.now(UTC)
    async with session_factory() as db:
        rows = (await db.execute(select(SubtitleSearch))).scalars().all()
    waiting = {r.key for r in rows if _aware(r.next_try_at) > now}
    return [t for t in targets if t.dedup_keys()[0] not in waiting]


def _aware(value: datetime) -> datetime:
    # SQLite (tests) relit les dates sans fuseau : elles sont en UTC
    return value if value.tzinfo else value.replace(tzinfo=UTC)


async def _record(target: sj.Target, job: sj.Job) -> None:
    """Note l'essai : ligne supprimée si trouvé, prochain essai planifié sinon."""
    key = target.dedup_keys()[0]
    now = datetime.now(UTC)
    async with session_factory() as db:
        row = (
            (await db.execute(select(SubtitleSearch).where(SubtitleSearch.key == key)))
            .scalars()
            .first()
        )
        if job.status == "found":
            if row is not None:
                await db.delete(row)
            await db.commit()
            return
        if row is None:
            row = SubtitleSearch(key=key, title=target.label()[:300], first_try_at=now)
            db.add(row)
        row.attempts = (row.attempts or 0) + 1
        row.last_result = job.status[:20]
        row.last_message = (job.message or "")[:400]
        row.last_try_at = now
        row.next_try_at = now + next_delay(row.attempts)
        await db.commit()


async def _forget_old() -> None:
    limit = datetime.now(UTC) - timedelta(days=FORGET_DAYS)
    async with session_factory() as db:
        await db.execute(delete(SubtitleSearch).where(SubtitleSearch.last_try_at < limit))
        await db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Préchargement (fiche ouverte, épisode lancé)
# ─────────────────────────────────────────────────────────────────────────────


# Langues des sous-titres complets d'un élément Jellyfin (voir subtitle_jobs)
full_languages = sj.full_languages


def prefetch(target: sj.Target) -> None:
    """Lance en fond la recherche d'un titre qui n'a pas ses sous-titres.

    Sans effet si une recherche existe déjà (en cours ou finie depuis moins
    de 15 min) ou si le gardien a planifié son prochain essai plus tard :
    ouvrir dix fois la fiche ne lance pas dix recherches.
    """
    if not settings.SUBTITLE_GUARDIAN_ENABLED:
        return
    target.language = sj.code2(target.language) or settings.SUBTITLE_LANGUAGE
    if sj.find(target) is not None:
        return
    task = asyncio.get_running_loop().create_task(_prefetch(target))
    sj._tasks.add(task)
    task.add_done_callback(sj._tasks.discard)


async def _prefetch(target: sj.Target) -> None:
    try:
        # Identifiants Radarr / Sonarr d'abord : le suivi des essais est rangé
        # sous ces clés (les mêmes que celles du gardien)
        bazarr, radarr, sonarr, _jf = await sj._clients()
        try:
            problem = (
                "Bazarr absent" if bazarr is None else await sj._resolve(target, radarr, sonarr)
            )
        finally:
            for client in (bazarr, radarr, sonarr):
                if client is not None:
                    await client.close()
        if problem:
            return  # épisode suivant inexistant, titre hors Radarr / Sonarr…
        now = datetime.now(UTC)
        async with session_factory() as db:
            rows = (
                (
                    await db.execute(
                        select(SubtitleSearch).where(SubtitleSearch.key.in_(target.dedup_keys()))
                    )
                )
                .scalars()
                .all()
            )
        if any(_aware(r.next_try_at) > now for r in rows):
            return
        if sj.find(target) is not None:
            return
        job = sj.start(target, origin="prefetch", reuse_done=False)
        await job.done.wait()
        if job.status in ("found", "none"):
            # Même suivi que le gardien (clé Radarr / Sonarr connue après résolution)
            await _record(job.target, job)
    except Exception as exc:  # jamais au point de gêner la lecture
        logger.debug("Préchargement des sous-titres de %s : %s", target.label(), exc)

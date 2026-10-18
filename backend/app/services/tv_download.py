"""« Télécharger » depuis la TV : film, série entière, une saison ou des épisodes.

Remplace l'assistant en 3 listes de l'add-on (profil qualité → dossier →
mode) par un seul appel : la TV dit QUOI (portée) et SI c'est pour ce soir
(priorité), le serveur fait le reste.

Déroulé, en deux temps (la TV ne doit jamais attendre plus de quelques
secondes) :

  1. tout de suite (pendant l'appel de la TV) : le titre est retrouvé, ajouté
     au *arr si besoin (profil et dossier habituels, voir `library_defaults`),
     et la demande TV est notée (services/tv_priority.py) ;
  2. en arrière-plan : pour une série tout juste ajoutée, on attend que Sonarr
     ait chargé ses épisodes (il le fait seul, en quelques secondes), on ne
     surveille QUE ce qui est demandé, puis on lance la recherche.

Pour ce soir (`priority`) : la release est choisie par ArrMada parmi celles
que le *arr accepte (profil respecté), Usenet d'abord : c'est la seule voie
qu'ArrMada sait faire passer en tête (SABnzbd), et la plus rapide. Aucune
release Usenet acceptée : recherche automatique classique du *arr.

Piège évité : une série ajoutée « en entier » est surveillée en entier, et
Sonarr téléchargerait toutes ses saisons. Pour une saison ou un épisode, la
série est ajoutée avec `monitor: none`, puis seul ce qui est demandé est
surveillé.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tv_request import TvRequest
from app.services import tv_priority
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Sonarr charge les épisodes d'une série tout juste ajoutée en arrière-plan :
# on les attend au plus EPISODES_WAIT secondes, en regardant toutes les
# EPISODES_POLL secondes (remplacés par les tests).
EPISODES_WAIT = 90.0
EPISODES_POLL = 3.0
# Une recherche interactive interroge tous les indexeurs (une saison : une
# requête par épisode) : bien plus long que les 10 s par défaut.
RELEASES_TIMEOUT = 180

TMDB_BASE = "https://api.themoviedb.org/3"

_jobs: set[asyncio.Task] = set()


# ─────────────────────────────────────────────────────────────────────────────
# Fonctions pures (testées sans réseau)
# ─────────────────────────────────────────────────────────────────────────────


def library_defaults(items: list[dict[str, Any]]) -> tuple[int | None, str | None]:
    """Profil qualité et dossier racine les plus utilisés de la médiathèque.

    « Comme d'habitude » : c'est ce que la famille aurait choisi dans
    l'ancien assistant, sans avoir à le demander à chaque fois.
    """
    profiles = Counter(i.get("qualityProfileId") for i in items if i.get("qualityProfileId"))
    folders = Counter(
        str(i.get("rootFolderPath")).rstrip("/") for i in items if i.get("rootFolderPath")
    )
    profile = profiles.most_common(1)[0][0] if profiles else None
    folder = folders.most_common(1)[0][0] if folders else None
    return profile, folder


def pick_release(
    releases: list[dict[str, Any]], *, full_season: bool | None = None
) -> dict[str, Any] | None:
    """Release Usenet acceptée par le *arr la mieux classée, sinon None.

    Le *arr renvoie ses releases déjà classées (champ `releaseWeight`, sinon
    l'ordre de la liste) selon le profil qualité de l'utilisateur : on garde
    son classement et on ne fait que préférer Usenet.
    `full_season` : True = packs de saison seulement (portée « saison »).
    """
    candidates = []
    for index, rel in enumerate(releases or []):
        if not isinstance(rel, dict) or not rel.get("approved"):
            continue
        if rel.get("downloadAllowed") is False or rel.get("temporarilyRejected"):
            continue
        if str(rel.get("protocol") or "").lower() != "usenet":
            continue
        if full_season is not None and bool(rel.get("fullSeason")) != full_season:
            continue
        if not rel.get("guid") or rel.get("indexerId") is None:
            continue
        weight = rel.get("releaseWeight")
        candidates.append((weight if isinstance(weight, int) else index, index, rel))
    if not candidates:
        return None
    return min(candidates, key=lambda c: (c[0], c[1]))[2]


def default_season(seasons: list[dict[str, Any]], in_library: bool) -> int | None:
    """Saison montrée en premier sur la TV.

    Pas encore dans la médiathèque : la première (on commence par le début).
    Déjà là : la première saison incomplète, sinon la dernière (la nouvelle).
    """
    numbers = [s for s in seasons if s.get("number", 0) >= 1]
    if not numbers:
        return None
    if in_library:
        missing = [s for s in numbers if s.get("have", 0) < s.get("aired", s.get("episodes", 0))]
        return (missing[0] if missing else numbers[-1])["number"]
    return numbers[0]["number"]


def _season_list(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Saisons (≥ 1) d'une liste d'épisodes : nombre, diffusés, présents."""
    seasons: dict[int, dict[str, Any]] = {}
    for ep in episodes:
        number = ep["season"]
        if number < 1:
            continue
        s = seasons.setdefault(number, {"number": number, "episodes": 0, "aired": 0, "have": 0})
        s["episodes"] += 1
        s["aired"] += 1 if ep.get("aired") else 0
        s["have"] += 1 if ep.get("has_file") else 0
    return [seasons[n] for n in sorted(seasons)]


def _sonarr_episode(ep: dict[str, Any]) -> dict[str, Any]:
    from datetime import UTC, datetime

    air = str(ep.get("airDateUtc") or "")
    try:
        aired = bool(air) and datetime.fromisoformat(air.replace("Z", "+00:00")) <= datetime.now(
            UTC
        )
    except ValueError:
        aired = False
    return {
        "id": ep.get("id"),
        "season": int(ep.get("seasonNumber") or 0),
        "number": int(ep.get("episodeNumber") or 0),
        "title": ep.get("title") or "",
        "air_date": air[:10],
        "aired": aired,
        "has_file": bool(ep.get("hasFile")),
        "runtime": int(ep.get("runtime") or 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Clients
# ─────────────────────────────────────────────────────────────────────────────


async def _clients(db: AsyncSession, service_type: str) -> RadarrClient | SonarrClient | None:
    from app.services import kodi

    if service_type == "radarr":
        return await kodi._get_radarr_client(db)
    return await kodi._get_sonarr_client(db)


async def _defaults(client: RadarrClient | SonarrClient) -> tuple[int | None, str | None]:
    """Profil / dossier habituels ; à défaut, le premier profil et le premier dossier."""
    items = await (client.get_movies() if isinstance(client, RadarrClient) else client.get_series())
    profile, folder = library_defaults(items if isinstance(items, list) else [])
    if profile is None:
        profiles = await client.get_quality_profiles()
        profile = profiles[0]["id"] if profiles else None
    if folder is None:
        folders = await client.get_root_folders()
        folder = folders[0]["path"] if folders else None
    return profile, folder


async def _sonarr_episodes(sonarr: SonarrClient, series_id: int) -> list[dict[str, Any]]:
    raw = await sonarr.get("/episode", params={"seriesId": series_id})
    return [_sonarr_episode(e) for e in raw or [] if isinstance(e, dict)]


async def _tmdb(path: str) -> dict[str, Any] | None:
    if not settings.TMDB_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(
                f"{TMDB_BASE}{path}",
                params={"api_key": settings.TMDB_API_KEY, "language": "fr-FR"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("TMDB %s illisible : %s", path, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Saisons et épisodes (feuille « Télécharger » d'une série)
# ─────────────────────────────────────────────────────────────────────────────


async def get_seasons(
    db: AsyncSession,
    *,
    title: str = "",
    tmdb_id: int | None = None,
    tvdb_id: int | None = None,
    season: int | None = None,
) -> dict[str, Any]:
    """Saisons d'une série et épisodes d'UNE saison (`season`, sinon celle par défaut).

    Série déjà dans Sonarr : ses épisodes (ids, présents ou non). Sinon TMDB
    (titres en français, TMDB_API_KEY) ; sans TMDB, les saisons seulement
    (Sonarr ne donne pas les épisodes d'une série qu'il ne suit pas).
    """
    from app.services import kodi

    sonarr = await _clients(db, "sonarr")
    if not sonarr:
        return {"status": "error", "message": "Sonarr n'est pas configuré"}
    try:
        series = await kodi._find_series_for_addon(sonarr, title, tmdb_id, tvdb_id)
        if not series:
            return {"status": "error", "message": f"« {title} » introuvable dans Sonarr"}
        arr_id = series.get("id") or None
        base = {
            "status": "ok",
            "title": series.get("title") or title,
            "tvdb_id": series.get("tvdbId"),
            "tmdb_id": series.get("tmdbId") or tmdb_id,
            "arr_id": arr_id,
            "in_library": bool(arr_id),
        }
        if arr_id:
            episodes = await _sonarr_episodes(sonarr, arr_id)
            seasons = _season_list(episodes)
            chosen = season if season is not None else default_season(seasons, True)
            return {
                **base,
                "source": "sonarr",
                "seasons": seasons,
                "season": chosen,
                "episodes": [e for e in episodes if e["season"] == chosen],
            }
    except Exception as exc:
        logger.warning("Saisons de « %s » illisibles : %s", title, exc)
        return {"status": "error", "message": "Sonarr injoignable"}
    finally:
        await sonarr.close()

    # Pas encore suivie : saisons du lookup Sonarr, épisodes par TMDB
    lookup_seasons = [
        {"number": int(s.get("seasonNumber") or 0), "episodes": 0, "aired": 0, "have": 0}
        for s in series.get("seasons") or []
        if int(s.get("seasonNumber") or 0) >= 1
    ]
    tmdb = base["tmdb_id"]
    details = await _tmdb(f"/tv/{tmdb}") if tmdb else None
    if details:
        lookup_seasons = [
            {
                "number": int(s.get("season_number") or 0),
                "episodes": int(s.get("episode_count") or 0),
                "aired": int(s.get("episode_count") or 0),
                "have": 0,
            }
            for s in details.get("seasons") or []
            if int(s.get("season_number") or 0) >= 1
        ] or lookup_seasons
    chosen = season if season is not None else default_season(lookup_seasons, False)
    episodes: list[dict[str, Any]] = []
    if tmdb and chosen is not None:
        data = await _tmdb(f"/tv/{tmdb}/season/{chosen}")
        from datetime import date

        today = date.today().isoformat()
        for ep in (data or {}).get("episodes") or []:
            air = str(ep.get("air_date") or "")
            episodes.append(
                {
                    "id": None,
                    "season": chosen,
                    "number": int(ep.get("episode_number") or 0),
                    "title": ep.get("name") or "",
                    "air_date": air,
                    "aired": bool(air) and air <= today,
                    "has_file": False,
                    "runtime": int(ep.get("runtime") or 0),
                }
            )
    return {
        **base,
        "source": "tmdb" if episodes else "sonarr",
        "seasons": lookup_seasons,
        "season": chosen,
        "episodes": episodes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Télécharger
# ─────────────────────────────────────────────────────────────────────────────


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        return None


async def start_download(
    db: AsyncSession, data: dict[str, Any], origin: dict[str, Any]
) -> dict[str, Any]:
    """Point d'entrée de la feuille « Télécharger » de la TV (réponse en quelques secondes)."""
    from app.services.activity_log import log_event

    media_type = "movie" if data.get("type", "movie") == "movie" else "series"
    scope = str(data.get("scope") or ("movie" if media_type == "movie" else "series"))
    if media_type == "series" and scope not in ("series", "season", "episode"):
        return {"status": "error", "message": f"Portée inconnue : {scope}"}
    season = _int(data.get("season")) if scope in ("season", "episode") else None
    if scope in ("season", "episode") and season is None:
        return {"status": "error", "message": "Saison manquante"}
    numbers = sorted({int(n) for n in data.get("episodes") or [] if _int(n)})
    if scope == "episode" and not numbers:
        return {"status": "error", "message": "Aucun épisode choisi"}
    priority = bool(data.get("priority", True))

    service_type = "radarr" if media_type == "movie" else "sonarr"
    client = await _clients(db, service_type)
    if not client:
        return {"status": "error", "message": f"{service_type.capitalize()} n'est pas configuré"}
    try:
        if media_type == "movie":
            found = await _ensure_movie(client, data)
        else:
            found = await _ensure_series(client, data, scope, season)
    except Exception as exc:
        from app.services.kodi import _arr_error

        logger.error("Télécharger depuis la TV (%s) : %s", data.get("title"), exc)
        return {"status": "error", "message": _arr_error(service_type.capitalize(), exc)}
    finally:
        await client.close()
    if found.get("status") != "ok":
        return found

    arr_id, title, added = found["arr_id"], found["title"], found["added"]
    request = await tv_priority.create_request(
        db,
        service_type=service_type,
        arr_id=arr_id,
        title=title,
        origin=origin,
        # Épisodes : leurs ids Sonarr ne sont connus qu'après chargement →
        # demande « saison » d'abord, affinée par la tâche de fond
        scope="season" if scope == "episode" else scope,
        season=season,
        priority=priority,
        added=added,
    )
    job = {
        "service_type": service_type,
        "arr_id": arr_id,
        "title": title,
        "scope": scope,
        "season": season,
        "numbers": numbers,
        "priority": priority,
        "request_id": request.id if request else None,
        "fresh": added and service_type == "sonarr",
        "device": origin.get("device_name"),
    }
    _spawn(_run_job(job))

    what = _describe(scope, season, numbers)
    await log_event(
        category="download",
        action="tv_download",
        status="ok",
        source="kodi",
        media_type=media_type,
        media_id=arr_id,
        title=title,
        subtitle=what,
        device=origin.get("device_name"),
        detail=("Pour ce soir (prioritaire)" if priority else "File normale")
        + (" · ajouté au " + service_type.capitalize() if added else ""),
    )
    return {
        "status": "ok",
        "arr_id": arr_id,
        "title": title,
        "added": added,
        "request_id": request.id if request else None,
        "message": f"{title} · {what} : c'est parti" + (" (prioritaire)" if priority else ""),
    }


def _describe(scope: str, season: int | None, numbers: list[int]) -> str:
    if scope == "movie":
        return "film"
    if scope == "series":
        return "toute la série"
    if scope == "season":
        return f"saison {season}"
    if len(numbers) == 1:
        return f"S{season:02d}E{numbers[0]:02d}"
    return f"saison {season}, {len(numbers)} épisodes"


async def _ensure_movie(radarr: RadarrClient, data: dict[str, Any]) -> dict[str, Any]:
    """Film dans Radarr (ajouté si besoin, sans recherche : c'est la tâche qui la lance)."""
    title = str(data.get("title") or "")
    arr_id = _int(data.get("arr_id"))
    if arr_id:
        movie = await radarr.get_movie_by_id(arr_id)
    else:
        tmdb_id = _int(data.get("tmdb_id"))
        results = await radarr.lookup_movie(f"tmdb:{tmdb_id}" if tmdb_id else title)
        movie = results[0] if results else None
    if not movie or not movie.get("tmdbId"):
        return {"status": "error", "message": f"« {title} » introuvable dans Radarr"}
    if movie.get("id"):
        if movie.get("hasFile") and not data.get("force"):
            return {
                "status": "error",
                "code": "available",
                "message": f"« {movie.get('title') or title} » est déjà sur le NAS",
            }
        if not movie.get("monitored"):
            movie["monitored"] = True
            await radarr.update_movie(movie["id"], movie)
        return {"status": "ok", "arr_id": movie["id"], "title": movie.get("title"), "added": False}
    profile, folder = await _defaults(radarr)
    payload = {
        "title": movie.get("title") or title,
        "tmdbId": movie["tmdbId"],
        "year": movie.get("year"),
        "qualityProfileId": _int(data.get("quality_profile_id")) or profile,
        "rootFolderPath": data.get("root_folder_path") or folder,
        "monitored": True,
        "addOptions": {"searchForMovie": False},
        "images": movie.get("images", []),
    }
    res = await radarr.add_movie(payload)
    return {"status": "ok", "arr_id": res.get("id"), "title": payload["title"], "added": True}


async def _ensure_series(
    sonarr: SonarrClient, data: dict[str, Any], scope: str, season: int | None
) -> dict[str, Any]:
    """Série dans Sonarr ; ajoutée en ne surveillant que la portée demandée."""
    from app.services import kodi

    title = str(data.get("title") or "")
    arr_id = _int(data.get("arr_id"))
    if arr_id:
        series = await sonarr.get_series_by_id(arr_id)
    else:
        series = await kodi._find_series_for_addon(
            sonarr, title, _int(data.get("tmdb_id")), _int(data.get("tvdb_id"))
        )
    if not series or not series.get("tvdbId"):
        return {"status": "error", "message": f"« {title} » introuvable dans Sonarr"}
    if series.get("id"):
        return {
            "status": "ok",
            "arr_id": series["id"],
            "title": series.get("title") or title,
            "added": False,
        }
    profile, folder = await _defaults(sonarr)
    whole = scope == "series"
    payload = {
        "title": series.get("title") or title,
        "tvdbId": series["tvdbId"],
        "year": series.get("year"),
        "qualityProfileId": _int(data.get("quality_profile_id")) or profile,
        "rootFolderPath": data.get("root_folder_path") or folder,
        "monitored": True,
        "seasonFolder": True,
        # Saison / épisode : rien de surveillé à l'ajout, sinon Sonarr
        # téléchargerait toute la série dans notre dos
        "seasons": [
            {
                "seasonNumber": s.get("seasonNumber"),
                "monitored": whole and int(s.get("seasonNumber") or 0) >= 1,
            }
            for s in series.get("seasons") or []
        ],
        "addOptions": {"monitor": "all" if whole else "none", "searchForMissingEpisodes": False},
        "images": series.get("images", []),
    }
    res = await sonarr.add_series(payload)
    return {"status": "ok", "arr_id": res.get("id"), "title": payload["title"], "added": True}


# ─────────────────────────────────────────────────────────────────────────────
# Tâche de fond : surveiller juste ce qu'il faut, chercher
# ─────────────────────────────────────────────────────────────────────────────


def _spawn(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)


async def _run_job(job: dict[str, Any]) -> None:
    from app.services.activity_log import log_event

    try:
        async with tv_priority.session_factory() as db:
            client = await _clients(db, job["service_type"])
            if not client:
                return
            client.timeout = RELEASES_TIMEOUT
            try:
                if job["service_type"] == "radarr":
                    picked = await _search_movie(client, job)
                else:
                    picked = await _search_series(client, job, db)
            finally:
                await client.close()
            if picked and job["request_id"]:
                req = await db.get(TvRequest, job["request_id"])
                if req is not None and not req.release_title:
                    req.release_title = str(picked.get("title") or "")[:500] or None
                    await db.commit()
        if picked:
            tv_priority.kick(delay=2)  # la release est déjà chez SABnzbd
    except Exception as exc:
        logger.error("Télécharger « %s » : tâche de fond en échec (%s)", job["title"], exc)
        await log_event(
            category="download",
            action="tv_download",
            status="ko",
            source="kodi",
            title=job["title"],
            device=job.get("device"),
            detail=f"Recherche non lancée : {exc}",
        )


async def _grab_or_none(client, releases: list[dict[str, Any]], **kwargs) -> dict | None:
    """Prend la meilleure release Usenet acceptée, s'il y en a une."""
    picked = pick_release(releases, **kwargs)
    if picked:
        await client.grab_release(picked["guid"], picked["indexerId"])
        logger.info("Pour ce soir : release Usenet choisie « %s »", picked.get("title"))
    return picked


async def _search_movie(radarr: RadarrClient, job: dict[str, Any]) -> dict | None:
    picked = None
    if job["priority"]:
        try:
            picked = await _grab_or_none(radarr, await radarr.get_releases(job["arr_id"]))
        except Exception as exc:
            logger.warning("Releases de « %s » illisibles (%s) : recherche auto", job["title"], exc)
    if not picked:
        await radarr.search_movie(job["arr_id"])
    return picked


async def _wait_episodes(sonarr: SonarrClient, job: dict[str, Any]) -> list[dict[str, Any]]:
    """Épisodes de la série ; série tout juste ajoutée : on attend que Sonarr les charge."""
    waited = 0.0
    while True:
        episodes = await _sonarr_episodes(sonarr, job["arr_id"])
        wanted = [
            e
            for e in episodes
            if job["season"] is None and e["season"] >= 1 or e["season"] == job["season"]
        ]
        if wanted or not job["fresh"] or waited >= EPISODES_WAIT:
            return episodes
        await asyncio.sleep(EPISODES_POLL)
        waited += EPISODES_POLL


async def _search_series(
    sonarr: SonarrClient, job: dict[str, Any], db: AsyncSession
) -> dict | None:
    series_id, scope, season = job["arr_id"], job["scope"], job["season"]
    if scope == "series":
        await sonarr.search_series(series_id)
        return None

    episodes = await _wait_episodes(sonarr, job)
    in_season = [e for e in episodes if e["season"] == season]
    if scope == "episode":
        targets = [e for e in in_season if e["number"] in set(job["numbers"])]
    else:
        targets = in_season
    ids = [e["id"] for e in targets if e.get("id")]
    if not ids:
        raise RuntimeError(f"aucun épisode trouvé dans Sonarr pour la saison {season}")

    # Surveiller exactement ce qui est demandé (et la saison, pour une saison entière)
    await sonarr.put("/episode/monitor", data={"episodeIds": ids, "monitored": True})
    if scope == "season":
        await sonarr.set_season_monitored(series_id, season, True)
    if scope == "episode" and job["request_id"]:
        req = await db.get(TvRequest, job["request_id"])
        if req is not None:
            req.scope, req.episode_ids = "episode", sorted(ids)
            await db.commit()

    picked = None
    if job["priority"]:
        try:
            if scope == "season":
                releases = await sonarr.get_releases(series_id, season)
                picked = await _grab_or_none(sonarr, releases, full_season=True)
            elif len(ids) == 1:
                releases = await sonarr.get_releases_for_episode(ids[0])
                picked = await _grab_or_none(sonarr, releases, full_season=False)
        except Exception as exc:
            logger.warning("Releases de « %s » illisibles (%s) : recherche auto", job["title"], exc)
    if not picked:
        if scope == "season":
            await sonarr.search_season(series_id, season)
        else:
            await sonarr.search_episodes(ids)
    return picked

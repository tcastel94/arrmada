"""Remux à alléger : remplacer un remux trop lourd par une version plus légère (ADR-021).

Baisser un profil qualité (ADR-020) ne remplace aucun fichier : Radarr ne
descend jamais en qualité de lui-même. Pour qu'il aille chercher un
Bluray-2160p à la place d'un remux de 70 Go, il faut lui retirer le fichier
(pas le film), une fois la version plus légère mise en téléchargement.

Ce module fait trois choses :

  - ``inventory`` : la liste des films dont le fichier est un remux que leur
    profil n'autorise plus, lue sur TOUTE la médiathèque (pas de plafond) ;
  - ``replace_one`` : pour un film, trouver chez les indexeurs un remplaçant
    plus léger, le mettre en téléchargement, puis seulement supprimer le remux ;
  - un lot en tâche de fond (``start`` / ``job``), film par film.

Analogie exploitation : on ne purge pas un fichier de production avant
d'avoir vérifié que la nouvelle livraison est disponible ; et on traite par
petits lots, avec une pause, pour ne pas saturer la chaîne en aval
(indexeurs, SABnzbd).

Garde-fous :
  - jamais le film, seulement son fichier (``DELETE /moviefile/{id}``) ;
  - rien n'est supprimé tant qu'un remplaçant vérifié à l'instant, et plus
    léger, n'est pas parti en téléchargement ;
  - un film dont le profil autorise son remux (« films d'exception ») n'est
    jamais dans la liste, et l'état est relu juste avant chaque suppression ;
  - un film non surveillé ou à la taille incohérente pour un remux (qualité
    mal détectée) est signalé, pas traité ;
  - ``MAX_BATCH`` films par lot, un seul lot à la fois ;
  - le fichier part dans la corbeille de Radarr quand elle est réglée.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.database import async_session_factory
from app.models.service import Service
from app.services import activity_log, health_checker
from app.utils.logger import get_logger

logger = get_logger(__name__)

GIB = 1024**3

#: Films par lot : au-delà, les indexeurs et SABnzbd reçoivent trop d'un coup.
MAX_BATCH = 10
#: Pause entre deux films d'un lot (secondes).
PAUSE_SECONDS = 20
#: La recherche interactive interroge tous les indexeurs : elle peut être longue.
RELEASE_TIMEOUT_SECONDS = 120
ARR_TIMEOUT_SECONDS = 30

#: Taille attendue du remplaçant, en Go par heure de film (ordre de grandeur :
#: un Bluray-2160p de 2 h pèse environ 20 Go, un Bluray-1080p environ 10 Go).
_TARGET_GIB_PER_HOUR = {2160: 10.0, 1080: 5.0}
#: En dessous de ce rapport taille réelle / taille attendue du remplaçant, le
#: « remux » n'en est sans doute pas un (qualité mal détectée) : rien à gagner.
_SUSPECT_RATIO = 1.25
#: Un remplaçant doit peser au plus cette part du remux : sinon aucun gain réel.
_MAX_REPLACEMENT_RATIO = 0.7


class Refused(Exception):
    """Demande impossible : le message est montré tel quel à la personne."""


# ══════════════════════════════════════════════════════════════
# Accès à Radarr
# ══════════════════════════════════════════════════════════════


async def _radarr() -> Any:
    """Client du premier Radarr activé."""
    async with async_session_factory() as db:
        rows = list((await db.execute(select(Service))).scalars())
    found = [s for s in rows if s.type.lower() == "radarr" and s.is_enabled]
    if not found:
        raise Refused("Radarr n'est pas configuré dans ArrMada")
    client = health_checker._build_client(found[0])
    client.timeout = ARR_TIMEOUT_SECONDS
    return client


@contextlib.asynccontextmanager
async def _open():
    client = await _radarr()
    try:
        yield client
    finally:
        await client.close()


# ══════════════════════════════════════════════════════════════
# Lecture (pur)
# ══════════════════════════════════════════════════════════════


def allowed_quality_ids(profile: dict[str, Any]) -> set[int]:
    """Identifiants des qualités cochées d'un profil (un groupe coché vaut pour ses qualités)."""
    ids: set[int] = set()
    for item in profile.get("items") or []:
        if not item.get("allowed"):
            continue
        if item.get("quality"):
            ids.add(int(item["quality"]["id"]))
        else:
            ids.update(int(c["quality"]["id"]) for c in item.get("items") or [] if c.get("quality"))
    return ids


def _quality(holder: dict[str, Any] | None) -> dict[str, Any]:
    """La qualité d'un fichier ou d'une release : {id, name, resolution, modifier…}."""
    return ((holder or {}).get("quality") or {}).get("quality") or {}


def is_remux(quality: dict[str, Any]) -> bool:
    return (
        str(quality.get("modifier") or "").lower() == "remux"
        or "remux" in str(quality.get("name") or "").lower()
    )


def estimated_bytes(resolution: int, runtime_minutes: Any) -> int:
    """Taille attendue du remplaçant, selon la durée du film (2 h si inconnue)."""
    per_hour = _TARGET_GIB_PER_HOUR.get(resolution, _TARGET_GIB_PER_HOUR[1080])
    minutes = int(runtime_minutes or 0) or 120
    minutes = max(60, min(minutes, 240))
    return int(per_hour * minutes / 60 * GIB)


def _poster(movie: dict[str, Any]) -> str | None:
    return next(
        (
            img.get("remoteUrl")
            for img in movie.get("images") or []
            if img.get("coverType") == "poster" and img.get("remoteUrl")
        ),
        None,
    )


def candidate(
    movie: dict[str, Any], profiles: dict[int, dict[str, Any]], *, include_1080p: bool
) -> dict[str, Any] | None:
    """Le film s'il a un remux que son profil n'autorise plus, sinon None.

    ``status`` : ``ready`` (remplaçable), ``unmonitored`` (Radarr ne chercherait
    rien) ou ``suspect`` (trop petit pour un remux : qualité mal détectée).
    """
    file = movie.get("movieFile") or {}
    quality = _quality(file)
    if not movie.get("hasFile") or not file.get("id") or not is_remux(quality):
        return None
    resolution = int(quality.get("resolution") or 0)
    if resolution != 2160 and not (include_1080p and resolution == 1080):
        return None
    profile = profiles.get(int(movie.get("qualityProfileId") or 0))
    if profile is None or int(quality.get("id") or 0) in allowed_quality_ids(profile):
        return None  # profil inconnu, ou remux voulu (« films d'exception »)

    size = int(file.get("size") or 0)
    target = estimated_bytes(resolution, movie.get("runtime"))
    status, note = "ready", ""
    if size < target * _SUSPECT_RATIO:
        status = "suspect"
        note = "Trop petit pour un remux : qualité sans doute mal détectée, rien à gagner"
    elif not movie.get("monitored"):
        status = "unmonitored"
        note = "Film non surveillé : Radarr ne chercherait pas de remplaçant"
    return {
        "movie_id": int(movie["id"]),
        "file_id": int(file["id"]),
        "tmdb_id": movie.get("tmdbId"),
        "title": movie.get("title") or "?",
        "year": movie.get("year"),
        "quality": quality.get("name"),
        "resolution": resolution,
        "size_bytes": size,
        "estimated_bytes": target,
        "gain_bytes": max(0, size - target) if status == "ready" else 0,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "monitored": bool(movie.get("monitored")),
        "poster_url": _poster(movie),
        "status": status,
        "note": note,
    }


def label(item: dict[str, Any]) -> str:
    return f"{item.get('title')} ({item.get('year')})" if item.get("year") else str(item["title"])


def _recycle_bin(config: Any) -> dict[str, Any]:
    config = config if isinstance(config, dict) else {}
    path = str(config.get("recycleBin") or "").strip()
    days = int(config.get("recycleBinCleanupDays") or 0)
    return {"enabled": bool(path), "path": path or None, "cleanup_days": days}


def _summarise(
    movies: list[dict[str, Any]],
    profile_list: list[dict[str, Any]],
    media_management: Any,
    *,
    include_1080p: bool,
) -> dict[str, Any]:
    profiles = {int(p["id"]): p for p in profile_list if p.get("id") is not None}
    items = [
        c for m in movies if (c := candidate(m, profiles, include_1080p=include_1080p)) is not None
    ]
    items.sort(key=lambda c: c["size_bytes"], reverse=True)
    ready = [c for c in items if c["status"] == "ready"]

    # Profils qui gardent le remux (« films d'exception ») et nombre de films
    # qui s'y trouvent déjà : ceux-là ne sont jamais proposés.
    remux_ids: dict[int, set[int]] = {}
    for movie in movies:
        quality = _quality(movie.get("movieFile"))
        if movie.get("hasFile") and is_remux(quality):
            remux_ids.setdefault(int(quality.get("resolution") or 0), set()).add(
                int(quality.get("id") or 0)
            )
    wanted = remux_ids.get(2160, set()) | (remux_ids.get(1080, set()) if include_1080p else set())
    keep_profiles = []
    for profile in profile_list:
        if wanted and wanted & allowed_quality_ids(profile):
            kept = sum(
                1
                for m in movies
                if m.get("qualityProfileId") == profile.get("id")
                and m.get("hasFile")
                and is_remux(_quality(m.get("movieFile")))
            )
            keep_profiles.append(
                {"id": profile.get("id"), "name": profile.get("name"), "remux_kept": kept}
            )

    return {
        "items": items,
        "total": len(items),
        "ready": len(ready),
        "size_bytes": sum(c["size_bytes"] for c in ready),
        "reclaimable_bytes": sum(c["gain_bytes"] for c in ready),
        "keep_profiles": keep_profiles,
        "recycle_bin": _recycle_bin(media_management),
        "batch_max": MAX_BATCH,
        "include_1080p": include_1080p,
    }


async def _media_management(client: Any) -> Any:
    try:
        return await client.get("/config/mediamanagement")
    except Exception as exc:  # noqa: BLE001 : l'inventaire reste utile sans la corbeille
        logger.warning("Remux : réglage de la corbeille illisible : %s", exc)
        return None


async def inventory(*, include_1080p: bool = False) -> dict[str, Any]:
    """Tous les films à alléger, du plus lourd au plus léger, avec le total récupérable."""
    async with _open() as client:
        movies, profiles, config = await asyncio.gather(
            client.get("/movie"), client.get("/qualityprofile"), _media_management(client)
        )
    return _summarise(movies or [], profiles or [], config, include_1080p=include_1080p)


# ══════════════════════════════════════════════════════════════
# Vérifier qu'un remplaçant existe
# ══════════════════════════════════════════════════════════════


def _rejections(release: dict[str, Any]) -> list[str]:
    out = []
    for rejection in release.get("rejections") or []:
        text = rejection.get("reason") if isinstance(rejection, dict) else rejection
        if text:
            out.append(str(text))
    return out


def _only_blocked_by_current_file(release: dict[str, Any]) -> bool:
    """Vrai si la release n'est refusée QUE parce que le remux est encore là.

    Tant que le fichier existe, Radarr refuse tout ce qui n'est pas mieux que
    lui (« Existing file on disk is of equal or higher preference », « Existing
    file meets cutoff »…). Ces refus tombent dès que le fichier est retiré ;
    tout autre refus (langue, taille, format interdit…) resterait.
    """
    return all("existing file" in reason.lower() for reason in _rejections(release))


def acceptable_releases(
    releases: list[Any], profile: dict[str, Any], *, min_resolution: int, max_bytes: int
) -> list[dict[str, Any]]:
    """Releases acceptées par le profil ET plus légères que le remux, la meilleure d'abord.

    ``max_bytes`` écarte les « Bluray-2160p » aussi lourds qu'un remux (vu en
    vrai : 120 Go pour remplacer un remux de 98 Go). Classement : la qualité
    la mieux placée du profil, puis le score des formats personnalisés.
    """
    allowed = allowed_quality_ids(profile)
    order = {
        qid: rank
        for rank, item in enumerate(profile.get("items") or [])
        for qid in (
            [int(item["quality"]["id"])]
            if item.get("quality")
            else [int(c["quality"]["id"]) for c in item.get("items") or [] if c.get("quality")]
        )
    }
    kept = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        quality = _quality(release)
        size = int(release.get("size") or 0)
        if (
            int(quality.get("id") or 0) not in allowed
            or is_remux(quality)
            or int(quality.get("resolution") or 0) < min_resolution
            or not 0 < size <= max_bytes
            or not release.get("guid")
            or release.get("temporarilyRejected")
            or release.get("downloadAllowed") is False
            or not _only_blocked_by_current_file(release)
        ):
            continue
        kept.append(release)
    kept.sort(
        key=lambda r: (
            order.get(int(_quality(r).get("id") or 0), -1),
            int(r.get("customFormatScore") or 0),
        ),
        reverse=True,
    )
    return kept


async def find_replacement(
    client: Any, item: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any] | None:
    """Recherche interactive : le meilleur remplaçant plus léger, ou None."""
    response = await client.client.get(
        f"{client.API_PREFIX}/release",
        params={"movieId": item["movie_id"]},
        timeout=RELEASE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    found = acceptable_releases(
        response.json() or [],
        profile,
        min_resolution=item["resolution"],
        max_bytes=int(item["size_bytes"] * _MAX_REPLACEMENT_RATIO),
    )
    if not found:
        return None
    best = found[0]
    return {
        "guid": best.get("guid"),
        "indexer_id": best.get("indexerId"),
        "title": best.get("title"),
        "quality": _quality(best).get("name"),
        "size_bytes": int(best.get("size") or 0),
        "indexer": best.get("indexer"),
        "choices": len(found),
    }


# ══════════════════════════════════════════════════════════════
# Remplacer un film
# ══════════════════════════════════════════════════════════════


def _result(item: dict[str, Any] | None, movie_id: int, status: str, message: str) -> dict:
    return {
        "movie_id": movie_id,
        "title": label(item) if item else f"film {movie_id}",
        "status": status,  # replaced | skipped | error
        "message": message,
        "freed_bytes": 0,
        "replacement": None,
    }


async def replace_one(
    client: Any, movie_id: int, *, include_1080p: bool = False, source: str = "arrmada"
) -> dict[str, Any]:
    """Remplace le remux d'un film. Ne lève jamais : rend un résultat.

    Ordre voulu, du moins risqué au plus risqué :
      1. relire le film (il a pu changer de profil ou de fichier depuis la liste) ;
      2. trouver un remplaçant plus léger chez les indexeurs ;
      3. le mettre en téléchargement (``POST /release``) ;
      4. seulement alors retirer le fichier du remux.
    Si l'étape 2 ou 3 échoue, rien n'a été supprimé. On télécharge la release
    vérifiée plutôt que de relancer une recherche automatique : ce qui a été
    contrôlé est ce qui arrive, et jamais une version plus lourde.
    """
    item: dict[str, Any] | None = None
    try:
        movie, profile_list = await asyncio.gather(
            client.get(f"/movie/{movie_id}"), client.get("/qualityprofile")
        )
        profiles = {int(p["id"]): p for p in profile_list or [] if p.get("id") is not None}
        item = candidate(movie or {}, profiles, include_1080p=include_1080p)
        if item is None:
            return _result(
                None,
                movie_id,
                "skipped",
                "Plus rien à alléger : fichier déjà remplacé, ou profil qui garde le remux",
            )
        if item["status"] != "ready":
            return _result(item, movie_id, "skipped", item["note"])

        replacement = await find_replacement(client, item, profiles[item["profile_id"]])
        if replacement is None:
            return _result(
                item,
                movie_id,
                "skipped",
                "Aucun remplaçant plus léger chez les indexeurs pour l'instant : remux conservé",
            )

        # Rien n'est encore supprimé : si l'envoi au client échoue, on s'arrête là.
        await client.post(
            "/release",
            data={"guid": replacement["guid"], "indexerId": replacement["indexer_id"]},
        )
        public = {k: v for k, v in replacement.items() if k not in ("guid", "indexer_id")}
        result = _result(
            item,
            movie_id,
            "replaced",
            f"{replacement['quality']} en téléchargement, remux retiré",
        )
        result["replacement"] = public
        try:
            await client.delete(f"/moviefile/{item['file_id']}")
            result["freed_bytes"] = item["size_bytes"]
        except Exception as exc:  # noqa: BLE001 : le téléchargement est parti, on le dit
            result["status"] = "error"
            result["message"] = (
                f"{replacement['quality']} en téléchargement, mais le remux n'a pas pu être "
                f"retiré ({exc}) : Radarr refusera l'import tant que le remux est là"
            )
        await activity_log.log_event(
            category="library",
            action="remux_replaced",
            status="ok" if result["status"] == "replaced" else "error",
            source=source,
            media_type="movie",
            media_id=movie_id,
            tmdb_id=item.get("tmdb_id"),
            title=label(item),
            detail=result["message"],
            meta={
                "quality": item["quality"],
                "size_bytes": item["size_bytes"],
                "replacement": public,
            },
        )
        return result
    except Exception as exc:  # noqa: BLE001 : un film en erreur n'arrête pas le lot
        logger.warning("Remux : remplacement du film %s impossible : %s", movie_id, exc)
        return _result(item, movie_id, "error", f"{type(exc).__name__} : {exc}"[:300])


# ══════════════════════════════════════════════════════════════
# Lot en tâche de fond
# ══════════════════════════════════════════════════════════════


@dataclass
class Job:
    id: str
    movie_ids: list[int]
    include_1080p: bool
    source: str
    state: str = "running"  # running | done | stopped
    current: str | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    stop_requested: bool = False
    task: asyncio.Task | None = None

    def to_dict(self) -> dict[str, Any]:
        replaced = [r for r in self.results if r["status"] == "replaced"]
        return {
            "id": self.id,
            "state": self.state,
            "total": len(self.movie_ids),
            "done": len(self.results),
            "current": self.current,
            "replaced": len(replaced),
            "skipped": sum(1 for r in self.results if r["status"] == "skipped"),
            "errors": sum(1 for r in self.results if r["status"] == "error"),
            "freed_bytes": sum(r["freed_bytes"] for r in self.results),
            "results": self.results,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


_job: Job | None = None


def job() -> dict[str, Any] | None:
    """Le lot en cours, ou le dernier terminé (None si aucun depuis le démarrage)."""
    return _job.to_dict() if _job else None


def is_running() -> bool:
    return _job is not None and _job.state == "running"


async def _run(current: Job) -> None:
    try:
        async with _open() as client:
            for index, movie_id in enumerate(current.movie_ids):
                if current.stop_requested:
                    current.state = "stopped"
                    break
                if index:
                    await asyncio.sleep(PAUSE_SECONDS)
                    if current.stop_requested:
                        current.state = "stopped"
                        break
                current.current = f"film {movie_id}"
                result = await replace_one(
                    client, movie_id, include_1080p=current.include_1080p, source=current.source
                )
                current.current = result["title"]
                current.results.append(result)
    except Exception as exc:  # noqa: BLE001 : Radarr injoignable, etc.
        logger.warning("Remux : lot %s interrompu : %s", current.id, exc)
        current.results.append(
            {
                "movie_id": 0,
                "title": "Lot interrompu",
                "status": "error",
                "message": f"{type(exc).__name__} : {exc}"[:300],
                "freed_bytes": 0,
                "replacement": None,
            }
        )
    finally:
        if current.state == "running":
            current.state = "done"
        current.current = None
        current.finished_at = datetime.now(UTC)


def start(
    movie_ids: list[int], *, include_1080p: bool = False, source: str = "arrmada"
) -> dict[str, Any]:
    """Lance un lot. Refuse s'il est vide, trop gros, ou si un autre tourne."""
    global _job
    ids = list(dict.fromkeys(int(i) for i in movie_ids))
    if not ids:
        raise Refused("Aucun film choisi")
    if len(ids) > MAX_BATCH:
        raise Refused(
            f"{len(ids)} films demandés : {MAX_BATCH} au plus par lot, pour ne pas saturer "
            "les indexeurs et SABnzbd. Lance le lot suivant quand celui-ci est fini"
        )
    if is_running():
        raise Refused("Un lot de remplacement est déjà en cours : attends qu'il se termine")
    _job = Job(id=secrets.token_hex(4), movie_ids=ids, include_1080p=include_1080p, source=source)
    _job.task = asyncio.create_task(_run(_job))
    return _job.to_dict()


def stop() -> dict[str, Any] | None:
    """Arrête le lot après le film en cours (ce qui est fait reste fait)."""
    if _job is not None and _job.state == "running":
        _job.stop_requested = True
    return job()


async def wait(seconds: float) -> dict[str, Any] | None:
    """Attend la fin du lot au plus ``seconds`` secondes, puis rend son état."""
    if _job is not None and _job.task is not None and not _job.task.done():
        await asyncio.wait({_job.task}, timeout=seconds)
    return job()


# ══════════════════════════════════════════════════════════════
# Garder le remux : passer des films dans un profil qui l'autorise
# ══════════════════════════════════════════════════════════════


async def keep(movie_ids: list[int], profile_id: int) -> dict[str, Any]:
    """Passe des films dans un profil qui garde le remux (« films d'exception »)."""
    ids = list(dict.fromkeys(int(i) for i in movie_ids))
    if not ids:
        raise Refused("Aucun film choisi")
    async with _open() as client:
        movies, profile_list = await asyncio.gather(
            client.get("/movie"), client.get("/qualityprofile")
        )
        profile = next((p for p in profile_list or [] if p.get("id") == profile_id), None)
        if profile is None:
            raise Refused(f"Profil {profile_id} introuvable dans Radarr")
        allowed = allowed_quality_ids(profile)
        chosen = [m for m in movies or [] if m.get("id") in ids]
        refused = [
            label(m)
            for m in chosen
            if int(_quality(m.get("movieFile")).get("id") or 0) not in allowed
        ]
        if refused or len(chosen) != len(ids):
            raise Refused(
                f"Le profil « {profile.get('name')} » n'autorise pas le remux de : "
                + (", ".join(refused[:5]) or "films introuvables")
            )
        await client.put("/movie/editor", data={"movieIds": ids, "qualityProfileId": profile_id})
    await activity_log.log_event(
        category="library",
        action="remux_kept",
        source="arrmada",
        media_type="movie",
        title=f"{len(ids)} films passés au profil « {profile.get('name')} »",
        detail=", ".join(label(m) for m in chosen[:10]),
    )
    return {"changed": len(ids), "profile_id": profile_id, "profile_name": profile.get("name")}

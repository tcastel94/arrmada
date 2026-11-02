"""Sagas de films : les « collections » de Radarr (TMDB), voir docs/adr/016-sagas.md.

D'où viennent les sagas
-----------------------
Radarr range chaque film dans sa collection TMDB (Le Seigneur des anneaux,
Harry Potter…) dès qu'un film de la collection est dans la bibliothèque. Il
expose ces collections (``/api/v3/collection``) avec la liste COMPLÈTE de
leurs films, présents ou non. ArrMada n'ajoute aucune source : il croise
cette liste avec les films de Radarr (``/api/v3/movie``) pour dire, film par
film, s'il est sur le NAS, attendu, manquant ou pas encore sorti.

États d'un film dans une saga
-----------------------------
- ``available`` : dans Radarr, fichier présent (on peut le regarder) ;
- ``wanted``    : dans Radarr, pas encore de fichier (Radarr le cherche) ;
- ``missing``   : pas dans Radarr, déjà sorti (on peut l'ajouter) ;
- ``upcoming``  : pas dans Radarr, pas encore sorti (annoncé) ;
- ``excluded``  : écarté à la main dans Radarr (liste d'exclusions) : jamais
  ajouté par « Compléter la saga ».

Ordre : l'ordre de sortie (année, puis titre), le seul que TMDB donne.

Films vus (étape 2)
-------------------
ArrMada garde déjà le « vu » et la reprise de chaque film, par profil
famille, dans `watch_states` (partagés par les TV, ADR-004 et ADR-008).
Une saga en tire : les films vus, le **prochain film à voir** (le premier
sur le NAS, dans l'ordre, pas encore vu ; commencé : avec sa reprise) et
l'heure du dernier film regardé (rangée « Sagas à terminer »).

Étape 3
-------
- **Suivre une saga** : Radarr « surveille » la collection et ajoute de
  lui-même tout nouveau film annoncé ; ArrMada prévient (notification) quand
  un film arrive ainsi dans une saga suivie.
- **Ordre personnalisé** (table `saga_orders`) : l'ordre de l'histoire
  plutôt que celui de sortie, choisi à la main dans la web app.
- **Collections Jellyfin** : la saga recréée en collection (« BoxSet ») dans
  Jellyfin, pour la retrouver regroupée là aussi.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.saga_order import SagaOrder
from app.models.service import Service
from app.models.watch_state import WatchState
from app.services import watch_sync
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Statuts TMDB / Radarr d'un film déjà sorti (au cinéma ou en vidéo)
_RELEASED = {"released", "inCinemas"}

_STATES = ("available", "wanted", "missing", "upcoming", "excluded")


async def radarr_client(db: AsyncSession, *, timeout: int = 30) -> RadarrClient:
    """Client du Radarr activé ; 400 si aucun n'est déclaré (message lisible par la TV)."""
    res = await db.execute(
        select(Service).where(Service.type == "radarr", Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if svc is None:
        raise HTTPException(status_code=400, detail="Radarr n'est pas configuré dans ArrMada")
    return RadarrClient(url=svc.url, api_key=decrypt_api_key(svc.api_key), timeout=timeout)


# ── Mise en forme (sans réseau) ───────────────────────────────


def _image(images: list[dict[str, Any]] | None, kind: str) -> str | None:
    """Adresse publique (TMDB) d'une image : affiche ou fond."""
    for img in images or []:
        if img.get("coverType") == kind:
            url = img.get("remoteUrl") or img.get("url")
            if url and str(url).startswith("http"):
                return str(url)
    return None


def _state(film: dict[str, Any], library: dict[int, dict[str, Any]], year_now: int) -> str:
    """État d'un film de saga, voir l'en-tête du module."""
    movie = library.get(int(film.get("tmdbId") or 0))
    if movie is not None:
        return "available" if movie.get("hasFile") else "wanted"
    if film.get("isExcluded"):
        return "excluded"
    status = film.get("status") or ""
    year = int(film.get("year") or 0)
    if status in _RELEASED or (status not in {"announced", "tba"} and 0 < year < year_now):
        return "missing"
    return "upcoming"


def film_summary(
    film: dict[str, Any],
    library: dict[int, dict[str, Any]],
    year_now: int,
    watch: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Un film d'une saga : état, identifiant Radarr, vu / reprise du profil."""
    tmdb_id = int(film.get("tmdbId") or 0)
    movie = library.get(tmdb_id)
    seen = (watch or {}).get(tmdb_id) or {}
    watched = bool(seen.get("watched"))
    position, total = int(seen.get("position") or 0), int(seen.get("total") or 0)
    return {
        "tmdb_id": tmdb_id,
        "movie_id": movie.get("id") if movie else None,
        "title": film.get("title") or "",
        "year": film.get("year") or None,
        "overview": film.get("overview") or None,
        "runtime": film.get("runtime") or None,
        "poster": _image(film.get("images"), "poster")
        or (_image(movie.get("images"), "poster") if movie else None),
        "state": _state(film, library, year_now),
        "watched": watched,
        "position": 0 if watched else position,  # s : reprise d'un film commencé
        # % (1-99) d'un film commencé, None sinon
        "progress": None
        if watched or position <= 0 or total <= 0
        else max(1, min(99, round(position * 100 / total))),
        "watched_at": seen.get("updated_at") or None,
    }


def _ordered(films: list[dict[str, Any]], order: list[int] | None = None) -> list[dict[str, Any]]:
    """Ordre de sortie (un film sans année en dernier), ou l'ordre choisi à la main.

    Ordre choisi : les films qui n'y figurent pas (ajoutés depuis à la saga)
    suivent, dans l'ordre de sortie.
    """
    by_release = sorted(films, key=lambda f: (f["year"] or 9999, f["title"].casefold()))
    if not order:
        return by_release
    rank = {tmdb: i for i, tmdb in enumerate(order)}
    return sorted(by_release, key=lambda f: rank.get(f["tmdb_id"], len(rank)))


def _films(
    collection: dict[str, Any],
    library: dict[int, dict[str, Any]],
    year_now: int,
    watch: dict[int, dict[str, Any]] | None,
    order: list[int] | None = None,
) -> list[dict[str, Any]]:
    return _ordered(
        [film_summary(f, library, year_now, watch) for f in collection.get("movies") or []],
        order,
    )


def next_film(films: list[dict[str, Any]], after: int = 0) -> dict[str, Any] | None:
    """Prochain film à voir : le premier sur le NAS, pas encore vu, à partir de [after] (index)."""
    return next((f for f in films[after:] if f["state"] == "available" and not f["watched"]), None)


def saga_summary(
    collection: dict[str, Any],
    library: dict[int, dict[str, Any]],
    year_now: int,
    watch: dict[int, dict[str, Any]] | None = None,
    order: list[int] | None = None,
) -> dict[str, Any]:
    """Une saga pour la grille : compteurs, trois affiches (éventail), films vus, suivant."""
    films = _films(collection, library, year_now, watch, order)
    count = {s: sum(1 for f in films if f["state"] == s) for s in _STATES}
    seen = sum(1 for f in films if f["watched"])
    started = seen > 0 or any(f["progress"] for f in films)
    upcoming_next = next_film(films)
    posters = [f["poster"] for f in films if f["poster"]][:3]
    return {
        "id": collection.get("id"),
        "tmdb_id": collection.get("tmdbId"),
        "title": collection.get("title") or "",
        "overview": collection.get("overview") or None,
        "poster": _image(collection.get("images"), "poster") or (posters[0] if posters else None),
        "fanart": _image(collection.get("images"), "fanart"),
        "posters": posters,
        "monitored": bool(collection.get("monitored")),
        "total": len(films),
        "available": count["available"],
        "wanted": count["wanted"],
        "missing": count["missing"],
        "upcoming": count["upcoming"],
        # Rien à ajouter : tous les films sortis sont dans Radarr
        "complete": count["missing"] == 0,
        "years": [y for y in (films[0]["year"], films[-1]["year"]) if y] if films else [],
        "seen": seen,
        "started": started,
        # Prochain film à voir (« Reprendre la saga ») ; None : rien de prêt
        "next": upcoming_next,
        "last_watched_at": max((f["watched_at"] for f in films if f["watched_at"]), default=None),
        # Ordre choisi à la main (sinon : ordre de sortie)
        "custom_order": bool(order),
    }


def saga_detail(
    collection: dict[str, Any],
    library: dict[int, dict[str, Any]],
    year_now: int,
    watch: dict[int, dict[str, Any]] | None = None,
    order: list[int] | None = None,
) -> dict[str, Any]:
    """Fiche d'une saga : le résumé et tous ses films, dans l'ordre (de sortie ou choisi)."""
    films = _films(collection, library, year_now, watch, order)
    return {**saga_summary(collection, library, year_now, watch, order), "films": films}


def in_progress(sagas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sagas commencées et pas finies (un film prêt reste à voir), la plus récente d'abord."""
    started = [s for s in sagas if s["started"] and s["next"] is not None]
    return sorted(started, key=lambda s: s["last_watched_at"] or "", reverse=True)


def sort_sagas(sagas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordre alphabétique (sans l'article « The » / « Le »…)."""

    def key(s: dict[str, Any]) -> str:
        title = s["title"].casefold()
        for article in ("the ", "le ", "la ", "les ", "l'"):
            if title.startswith(article):
                return title[len(article) :]
        return title

    return sorted(sagas, key=key)


def library_by_tmdb(movies: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Films de Radarr indexés par identifiant TMDB."""
    return {int(m["tmdbId"]): m for m in movies if m.get("tmdbId")}


def this_year() -> int:
    return datetime.now(UTC).year


async def movie_watch(db: AsyncSession, profile_id: int | None) -> dict[int, dict[str, Any]]:
    """Vu / reprise des films du profil, par identifiant TMDB (`watch_states`)."""
    rows = (
        (
            await db.execute(
                select(WatchState).where(
                    WatchState.media_type == "movie",
                    WatchState.id_type == "tmdb",
                    WatchState.profile_id.is_(None)
                    if profile_id is None
                    else WatchState.profile_id == profile_id,
                )
            )
        )
        .scalars()
        .all()
    )
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        state = watch_sync.public(row)
        if str(state["id"]).isdigit():
            out[int(state["id"])] = state
    return out


# ── Ordre personnalisé (base ArrMada) ─────────────────────────


async def custom_orders(db: AsyncSession) -> dict[int, list[int]]:
    """Ordres choisis à la main : {TMDB de la saga → TMDB des films dans l'ordre}."""
    rows = (await db.execute(select(SagaOrder))).scalars().all()
    return {row.collection_tmdb: row.ids() for row in rows if row.ids()}


async def set_order(db: AsyncSession, collection: dict[str, Any], tmdb_ids: list[int]) -> None:
    """Enregistre l'ordre choisi (upsert) ; seuls les films de la saga sont gardés."""
    known = {int(f.get("tmdbId") or 0) for f in collection.get("movies") or []}
    ids = [i for i in dict.fromkeys(tmdb_ids) if i in known]  # sans doublon, dans la saga
    tmdb = int(collection.get("tmdbId") or 0)
    row = (
        await db.execute(select(SagaOrder).where(SagaOrder.collection_tmdb == tmdb))
    ).scalar_one_or_none()
    if row is None:
        row = SagaOrder(collection_tmdb=tmdb)
        db.add(row)
    row.title = str(collection.get("title") or "")[:300]
    row.tmdb_ids = ",".join(str(i) for i in ids)
    row.updated_at = datetime.now(UTC)
    await db.flush()


async def reset_order(db: AsyncSession, collection_tmdb: int) -> None:
    """Revient à l'ordre de sortie."""
    row = (
        await db.execute(select(SagaOrder).where(SagaOrder.collection_tmdb == collection_tmdb))
    ).scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.flush()


# ── Appels à Radarr ───────────────────────────────────────────


async def load(client: RadarrClient) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """Collections de Radarr et films de la bibliothèque (par TMDB)."""
    collections = await client.get_collections()
    movies = await client.get_movies()
    return (collections if isinstance(collections, list) else []), library_by_tmdb(movies)


async def complete(
    client: RadarrClient,
    collection: dict[str, Any],
    library: dict[int, dict[str, Any]],
    tmdb_ids: list[int] | None,
) -> list[str]:
    """Ajoute à Radarr les films manquants d'une saga (ou ceux demandés) et les fait chercher.

    Seuls les films « manquants » (sortis, pas dans Radarr, pas exclus) sont
    ajoutés : un film annoncé n'a encore aucune release à trouver. Réglages
    de la saga dans Radarr (profil, dossier) s'ils existent, sinon les
    premiers de Radarr, comme pour une demande de film. Rend les titres ajoutés.
    """
    year_now = this_year()
    targets = [
        f
        for f in collection.get("movies") or []
        if _state(f, library, year_now) == "missing"
        and (tmdb_ids is None or int(f.get("tmdbId") or 0) in tmdb_ids)
    ]
    if not targets:
        return []
    profile = collection.get("qualityProfileId") or 0
    root = collection.get("rootFolderPath") or ""
    if not profile:
        profiles = await client.get_quality_profiles()
        profile = profiles[0]["id"] if profiles else 0
    if not root:
        folders = await client.get_root_folders()
        root = folders[0]["path"] if folders else ""
    if not profile or not root:
        raise HTTPException(
            status_code=409, detail="Radarr n'a ni profil de qualité ni dossier racine"
        )

    added: list[str] = []
    for film in targets:
        payload = {
            "title": film.get("title"),
            "tmdbId": film.get("tmdbId"),
            "year": film.get("year"),
            "images": film.get("images") or [],
            "qualityProfileId": profile,
            "rootFolderPath": root,
            "monitored": True,
            "minimumAvailability": collection.get("minimumAvailability") or "released",
            "addOptions": {"searchForMovie": True},
        }
        await client.add_movie(payload)
        added.append(str(film.get("title") or ""))
    logger.info("Saga « %s » : %d film(s) ajouté(s)", collection.get("title"), len(added))
    return added


async def follow(client: RadarrClient, collection: dict[str, Any], monitored: bool) -> None:
    """Suivre (ou ne plus suivre) une saga : Radarr ajoute seul ses nouveaux films.

    Radarr a besoin d'un profil de qualité et d'un dossier pour ajouter un
    film de lui-même : ceux de la saga s'ils existent, sinon les premiers.
    Les films ajoutés ainsi sont cherchés tout de suite, une fois sortis.
    """
    data = dict(collection)
    data.pop("movies", None)  # Radarr n'en a pas besoin pour modifier la saga
    data["monitored"] = monitored
    if monitored:
        if not data.get("qualityProfileId"):
            profiles = await client.get_quality_profiles()
            data["qualityProfileId"] = profiles[0]["id"] if profiles else 0
        if not data.get("rootFolderPath"):
            folders = await client.get_root_folders()
            data["rootFolderPath"] = folders[0]["path"] if folders else ""
        if not data["qualityProfileId"] or not data["rootFolderPath"]:
            raise HTTPException(
                status_code=409, detail="Radarr n'a ni profil de qualité ni dossier racine"
            )
        data["searchOnAdd"] = True
        data["minimumAvailability"] = data.get("minimumAvailability") or "released"
    await client.update_collection(int(collection["id"]), data)
    logger.info("Saga « %s » : suivie = %s", collection.get("title"), monitored)


async def notify_new_film(db: AsyncSession, movie_id: int) -> str | None:
    """Film ajouté à Radarr : s'il appartient à une saga suivie, une notification.

    Appelé par le webhook « MovieAdded » de Radarr. Rend le titre de la
    notification, ou None (pas de saga suivie, Radarr injoignable…).
    """
    from app.services.notification_service import create_notification

    try:
        client = await radarr_client(db)
    except HTTPException:
        return None
    try:
        movie = await client.get_movie_by_id(movie_id)
        tmdb = int((movie.get("collection") or {}).get("tmdbId") or 0)
        if not tmdb:
            return None
        collections = await client.get_collections()
    except Exception as exc:  # une notification ne doit jamais casser le webhook
        logger.info("Sagas : film %s non vérifié (%s)", movie_id, exc)
        return None
    finally:
        await client.close()
    saga = next((c for c in collections or [] if int(c.get("tmdbId") or 0) == tmdb), None)
    if saga is None or not saga.get("monitored"):
        return None
    title = f"Nouveau film dans la saga {saga.get('title')}"
    year = movie.get("year")
    await create_notification(
        db,
        type="saga_new_film",
        title=title,
        message=f"{movie.get('title')}{f' ({year})' if year else ''} : ajouté par Radarr, recherché dès sa sortie.",
        severity="info",
        service_name="radarr",
    )
    return title


# ── Collections Jellyfin ──────────────────────────────────────


async def jellyfin_collection(db: AsyncSession, saga: dict[str, Any]) -> dict[str, Any]:
    """Crée (ou complète) la collection Jellyfin d'une saga avec ses films sur le NAS.

    Rend {status, message, count} ; status « ok », « empty » (aucun film de
    la saga dans Jellyfin) ou « unavailable » (Jellyfin absent).
    """
    import httpx

    from app.services import jellyfin

    cfg = await jellyfin.get_config(db)
    if cfg is None:
        return {"status": "unavailable", "message": "Jellyfin n'est pas configuré", "count": 0}
    base, key = cfg
    ids: list[str] = []
    for film in saga.get("films") or []:
        if film.get("state") != "available":
            continue
        item = await jellyfin.find_movie_item(db, int(film["tmdb_id"]))
        if item and item.get("id"):
            ids.append(str(item["id"]))
    if not ids:
        return {"status": "empty", "message": "Aucun film de la saga dans Jellyfin", "count": 0}
    name = str(saga.get("title") or "Saga")
    headers = jellyfin.auth_header(key)
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=30) as http:
        # Collection du même nom déjà là : on la complète (Jellyfin ignore les doublons)
        found = await http.get(
            "/Items",
            params={"IncludeItemTypes": "BoxSet", "Recursive": "true", "SearchTerm": name},
        )
        found.raise_for_status()
        existing = next(
            (
                it
                for it in (found.json() or {}).get("Items") or []
                if str(it.get("Name") or "").casefold() == name.casefold()
            ),
            None,
        )
        if existing:
            resp = await http.post(
                f"/Collections/{existing['Id']}/Items", params={"Ids": ",".join(ids)}
            )
            resp.raise_for_status()
            verb = "complétée"
        else:
            resp = await http.post("/Collections", params={"Name": name, "Ids": ",".join(ids)})
            resp.raise_for_status()
            verb = "créée"
    count = len(ids)
    return {
        "status": "ok",
        "message": f"Collection « {name} » {verb} dans Jellyfin ({count} film{'s' if count > 1 else ''})",
        "count": count,
    }

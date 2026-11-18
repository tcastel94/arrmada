"""Liste blanche d'outils de l'agent local, et leur exécution validée.

@author : Jeff Pomponne <jpomponne@gmail.com>

Ce que le modèle peut demander tient dans ``exposed()`` : les 8 outils de
LECTURE de ce fichier (``READ_TOOLS``) et les 4 outils d'ÉCRITURE de
``write_tools.py``, et rien d'autre. Ce qui n'y est pas n'existe pas pour lui :
aucune suppression, aucune modification de profil ou d'indexeur n'est exposée,
donc aucune consigne contournée (« ignore tes règles ») ne peut en déclencher
une. C'est un pare-feu en liste blanche, pas un filtre de mots interdits.

Les lectures s'exécutent seules. Les écritures passent TOUJOURS par une
confirmation de l'utilisateur, gérée par la boucle (``agent.py``), jamais par
le modèle. ``LOCAL_AGENT_WRITE_TOOLS=false`` les retire de la liste.

Un outil = un modèle pydantic pour ses paramètres + une fonction asynchrone.
Le modèle pydantic sert deux fois :

1. son schéma JSON est envoyé à Ollama (c'est le « formulaire » du bon de
   commande que le modèle doit remplir) ;
2. les paramètres reçus sont validés avec. Paramètre inconnu, type faux,
   valeur hors bornes : l'appel est REJETÉ et l'erreur rendue au modèle, qui
   peut corriger. Un petit modèle se trompe parfois ; on ne devine jamais à
   sa place.

On s'appuie sur les briques de l'agent Claude (``services/copilot/tools``) :
accès aux services enregistrés, clients *arr, masquage des secrets. Mais les
résultats sont ici bien plus COMPACTS : le contexte d'un modèle local se
compte en milliers de jetons, pas en centaines de milliers.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import settings
from app.services.copilot import tools as copilot_tools
from app.services.copilot.redaction import Redactor
from app.services.copilot.tools.args import NoArgs, _Args
from app.services.copilot.tools.common import _client, _error, _fold, _services
from app.services.local_agent import diagnosis
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Résultat rendu au modèle : au-delà, coupé. 6 000 caractères ≈ 2 000 jetons,
# soit 1/8 du contexte par défaut : de quoi enchaîner 3 ou 4 outils par tour.
MAX_RESULT_CHARS = 6_000
TOOL_TIMEOUT_SECONDS = 45

MediaType = Literal["all", "series", "movie"]

_WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _day_name(day: str | None) -> str | None:
    """« 2026-11-19 » → « jeudi ». Calculé ici : un petit modèle se trompe sur les jours."""
    try:
        return _WEEKDAYS[date.fromisoformat(str(day)[:10]).weekday()]
    except (TypeError, ValueError):
        return None


def _clean(item: dict[str, Any]) -> dict[str, Any]:
    """Retire les champs vides : chaque caractère inutile est du contexte perdu."""
    return {k: v for k, v in item.items() if v not in (None, "", [], {})}


# ══════════════════════════════════════════════════════════════
# Paramètres des outils
# ══════════════════════════════════════════════════════════════


class TitleSearchArgs(_Args):
    title: str = Field(
        min_length=1,
        max_length=120,
        description="Titre tel que l'utilisateur l'a écrit, sans la saison ni la qualité.",
    )
    year: int = Field(
        default=0,
        ge=0,
        le=2100,
        description="Année de sortie si l'utilisateur l'a donnée, sinon 0.",
    )


class QueueArgs(_Args):
    title: str = Field(
        default="",
        max_length=120,
        description="Mots du titre pour ne garder que ce média. Vide : toute la file.",
    )


class HistoryArgs(_Args):
    type: MediaType = Field(default="all", description="series, movie, ou all pour les deux.")
    title: str = Field(
        default="",
        max_length=120,
        description="Mots du titre pour ne garder que ce média. Vide : tout l'historique.",
    )
    only_failures: bool = Field(
        default=False, description="true : seulement les téléchargements échoués ou ignorés."
    )
    limit: int = Field(default=15, ge=1, le=30, description="Nombre d'événements, de 1 à 30.")


class CalendarArgs(_Args):
    days: int = Field(
        default=7,
        ge=1,
        le=60,
        description="Nombre de jours à partir d'aujourd'hui (7 = cette semaine).",
    )
    type: MediaType = Field(default="all", description="series, movie, ou all pour les deux.")


class MissingArgs(_Args):
    type: MediaType = Field(default="all", description="series, movie, ou all pour les deux.")
    limit: int = Field(default=20, ge=1, le=50, description="Nombre de titres listés, de 1 à 50.")


# ══════════════════════════════════════════════════════════════
# Recherche d'un titre (bibliothèque + catalogue en ligne)
# ══════════════════════════════════════════════════════════════


def _series_candidate(item: dict[str, Any]) -> dict[str, Any]:
    stats = item.get("statistics") or {}
    in_library = bool(item.get("id"))
    return _clean(
        {
            "title": item.get("title"),
            "year": item.get("year"),
            "tvdb_id": item.get("tvdbId"),
            "status": item.get("status"),  # continuing | ended | upcoming
            "network": item.get("network"),
            "seasons": sum(1 for s in item.get("seasons") or [] if s.get("seasonNumber")),
            "in_library": in_library,
            "monitored": item.get("monitored") if in_library else None,
            "episodes_on_disk": f"{stats.get('episodeFileCount', 0)}/{stats.get('episodeCount', 0)}"
            if in_library and stats
            else None,
        }
    )


def _movie_candidate(item: dict[str, Any]) -> dict[str, Any]:
    in_library = bool(item.get("id"))
    original = item.get("originalTitle")
    return _clean(
        {
            "title": item.get("title"),
            "original_title": original if original != item.get("title") else None,
            "year": item.get("year"),
            "tmdb_id": item.get("tmdbId"),
            "status": item.get("status"),  # announced | inCinemas | released
            "in_library": in_library,
            "monitored": item.get("monitored") if in_library else None,
            "has_file": item.get("hasFile") if in_library else None,
        }
    )


async def _search_title(kind: Literal["series", "movie"], args: TitleSearchArgs) -> dict[str, Any]:
    """Cherche un titre dans Sonarr / Radarr (qui interrogent TheTVDB / TMDB).

    La réponse dit au modèle quoi faire du résultat (champ ``note``) : un
    homonyme ou un titre approchant doit donner une QUESTION à l'utilisateur,
    jamais un choix au hasard. Cette décision est calculée ici, par du code,
    plutôt que laissée au jugement d'un petit modèle.
    """
    service_type = "sonarr" if kind == "series" else "radarr"
    services = await _services(service_type)
    if not services:
        return {"error": f"Aucun {service_type.capitalize()} actif dans ArrMada."}
    async with _client(services[0]) as client:
        found = await (
            client.lookup_series(args.title)
            if kind == "series"
            else client.lookup_movie(args.title)
        )
    build = _series_candidate if kind == "series" else _movie_candidate
    candidates = [build(item) for item in found or [] if isinstance(item, dict)]
    return rank_candidates(kind, args, candidates)


def rank_candidates(
    kind: Literal["series", "movie"], args: TitleSearchArgs, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    """Classe les titres trouvés : un seul bon candidat, plusieurs, ou aucun d'identique.

    Fonction sans appel réseau, partagée avec le banc de test : la règle
    « ambiguïté = question » est la même en production et dans les essais.
    """
    label = "série" if kind == "series" else "film"
    if args.year:
        same_year = [c for c in candidates if c.get("year") == args.year]
        candidates = same_year or candidates

    wanted = _fold(args.title)
    exact = [
        c for c in candidates if wanted in (_fold(c.get("title")), _fold(c.get("original_title")))
    ]
    result: dict[str, Any] = {"query": args.title, "matches": len(candidates)}
    if not candidates:
        result["note"] = (
            f"Aucun {label} trouvé pour ce titre. Dis-le à l'utilisateur et demande-lui de "
            "vérifier l'orthographe. N'invente aucun titre."
        )
    elif len(exact) == 1:
        result["best_match"] = exact[0]
        others = [c for c in candidates if c is not exact[0]][:3]
        if others:
            result["other_results"] = others
    elif len(exact) > 1:
        result["ambiguous"] = True
        result["candidates"] = exact[:5]
        result["note"] = (
            f"Plusieurs {label}s portent ce titre. Ne choisis pas : cite-les avec leur année "
            "et demande à l'utilisateur lequel il veut."
        )
    else:
        result["candidates"] = candidates[:5]
        result["note"] = (
            "Aucun titre identique à la demande (faute de frappe possible). Propose le plus "
            "proche et demande confirmation à l'utilisateur avant d'aller plus loin."
        )
    return result


async def search_series(args: TitleSearchArgs) -> dict[str, Any]:
    return await _search_title("series", args)


async def search_movie(args: TitleSearchArgs) -> dict[str, Any]:
    return await _search_title("movie", args)


# ══════════════════════════════════════════════════════════════
# File d'attente
# ══════════════════════════════════════════════════════════════

_QUEUE_KEYS = (
    "title",
    "service_type",
    "status",
    "tracked_state",
    "progress",
    "time_left",
    "size",
    "protocol",
    "download_client",
    "indexer",
    "quality",
    "error",
    "detail",
)


async def library_titles(title: str) -> list[str]:
    """Titres exacts de la bibliothèque pour une demande approximative (voir ``library_state``)."""
    return [str(entry["title"]) for entry in await library_state(title)]


async def library_state(title: str) -> list[dict[str, Any]]:
    """Ce que la bibliothèque possède pour une demande, même approximative.

    Rend le titre EXACT et s'il est complet (film avec son fichier, série avec
    tous ses épisodes).

    « Dune 2 » ne figure dans aucun nom de release ; « Dune: Part Two », si.
    On demande donc à Radarr / Sonarr ce qu'ils comprennent, et on ne garde que
    ce qui est déjà dans la bibliothèque (un téléchargement en cours concerne
    forcément un titre suivi). Appelé seulement quand le filtre direct ne
    trouve rien : deux recherches de plus, environ 300 ms chacune.
    """
    found: list[dict[str, Any]] = []
    for service_type in ("radarr", "sonarr"):
        services = await _services(service_type)
        if not services:
            continue
        try:
            async with _client(services[0]) as client:
                items = await (
                    client.lookup_movie(title)
                    if service_type == "radarr"
                    else client.lookup_series(title)
                )
        except Exception:  # noqa: BLE001, S112 : une aide en plus, pas indispensable
            continue
        owned = [
            item
            for item in items or []
            if isinstance(item, dict) and item.get("id") and item.get("title")
        ][:2]
        for item in owned:
            if service_type == "radarr":
                entry = {"type": "movie", "complete": bool(item.get("hasFile"))}
            else:
                stats = item.get("statistics") or {}
                on_disk, wanted = stats.get("episodeFileCount", 0), stats.get("episodeCount", 0)
                entry = {
                    "type": "series",
                    "episodes_on_disk": f"{on_disk}/{wanted}",
                    "complete": bool(wanted) and on_disk >= wanted,
                }
            found.append({"title": str(item["title"]), "year": item.get("year"), **entry})
    return found[:3]


async def get_queue(args: QueueArgs) -> dict[str, Any]:
    """File d'attente de Sonarr / Radarr et état de SABnzbd, bloqués d'abord et expliqués."""
    raw = await copilot_tools.get_download_queue(NoArgs())
    items = [
        _clean({key: item.get(key) for key in _QUEUE_KEYS})
        for item in (raw.get("arr_queue") or {}).get("items") or []
    ]
    library: list[dict[str, Any]] = []
    if args.title and not any(diagnosis.matches(i.get("title"), args.title) for i in items):
        library = await library_state(args.title)
    alternates = [str(entry["title"]) for entry in library]
    clients = []
    for sab in raw.get("sabnzbd") or []:
        if sab.get("error"):
            clients.append({"service": sab.get("service"), "error": sab["error"]})
            continue
        clients.append(
            _clean(
                {
                    "service": sab.get("service"),
                    "paused": sab.get("paused"),
                    "speed": sab.get("speed"),
                    "time_left": sab.get("time_left"),
                    "free_space_gb": sab.get("free_space_complete_gb"),
                    "slots": len(sab.get("slots") or []),
                    "recent_failures": [
                        _clean({"name": f.get("name"), "reason": f.get("fail_message")})
                        for f in (sab.get("recent_failures") or [])[:5]
                    ],
                }
            )
        )
    return diagnosis.queue_view(
        items, title=args.title, alternates=alternates, clients=clients, library=library
    )


# ══════════════════════════════════════════════════════════════
# Historique
# ══════════════════════════════════════════════════════════════


def _records(payload: Any) -> list[dict[str, Any]]:
    """Les *arr rendent ``{"records": [...]}`` (paginé) ; on tolère une liste nue."""
    if isinstance(payload, dict):
        payload = payload.get("records")
    return [r for r in payload or [] if isinstance(r, dict)]


def _history_event(record: dict[str, Any], service_type: str) -> dict[str, Any]:
    data = record.get("data") or {}
    if service_type == "sonarr":
        episode = record.get("episode") or {}
        title = (record.get("series") or {}).get("title")
        if title and episode.get("seasonNumber") is not None:
            title += f" S{episode['seasonNumber']:02d}E{episode.get('episodeNumber', 0):02d}"
    else:
        title = (record.get("movie") or {}).get("title")
    return _clean(
        {
            "date": str(record.get("date") or "")[:16],
            "event": record.get("eventType"),
            "title": title,
            "release": record.get("sourceTitle"),
            "quality": (record.get("quality") or {}).get("quality", {}).get("name"),
            "indexer": data.get("indexer"),
            "download_client": data.get("downloadClient"),
            "reason": data.get("reason") or data.get("message"),
        }
    )


def _service_types(media: str) -> tuple[str, ...]:
    return {"series": ("sonarr",), "movie": ("radarr",)}.get(media, ("sonarr", "radarr"))


async def get_history(args: HistoryArgs) -> dict[str, Any]:
    """Derniers événements de Sonarr / Radarr, échecs expliqués, et leurs journaux."""
    services = await _services(*_service_types(args.type))
    if not services:
        return {"error": "Aucun Sonarr / Radarr actif dans ArrMada."}
    # Avec un filtre, on lit plus large : le tri se fait ici, pas dans l'*arr.
    page_size = 200 if args.title or args.only_failures else args.limit
    events: list[dict[str, Any]] = []
    log_records: list[dict[str, Any]] = []
    errors: list[str] = []
    for svc in services:
        service_type = svc.type.lower()
        params: dict[str, Any] = {
            "page": 1,
            "pageSize": page_size,
            "sortKey": "date",
            "sortDirection": "descending",
        }
        if service_type == "sonarr":
            params |= {"includeSeries": "true", "includeEpisode": "true"}
        else:
            params["includeMovie"] = "true"
        try:
            async with _client(svc) as client:
                records = _records(await client.get("/history", params=params))
                if args.title:
                    log_records += await _warnings(client)
        except Exception as exc:  # noqa: BLE001 : la panne est une information pour le modèle
            errors.append(f"{svc.name} : {_error(exc)}")
            continue
        events += [_history_event(record, service_type) for record in records]

    alternates: list[str] = []
    if args.title and not any(
        diagnosis.matches(f"{e.get('title', '')} {e.get('release', '')}", args.title)
        for e in events
    ):
        alternates = await library_titles(args.title)
    result = diagnosis.history_view(
        events,
        title=args.title,
        alternates=alternates,
        only_failures=args.only_failures,
        limit=args.limit,
        logs=diagnosis.log_lines(log_records, args.title, alternates) if args.title else None,
    )
    if errors:
        result["errors"] = errors
        result.pop("note", None)
    elif args.title:
        result = diagnosis.attach_indexers(result, await get_indexer_status(NoArgs()))
    return result


async def _warnings(client: Any) -> list[dict[str, Any]]:
    """Dernières lignes « warn » et « error » du journal d'un *arr (Système › Journaux)."""
    try:
        payload = await client.get(
            "/log",
            params={
                "page": 1,
                "pageSize": 100,
                "sortKey": "time",
                "sortDirection": "descending",
                "level": "warn",
            },
        )
    except Exception:  # noqa: BLE001 : un complément d'enquête, jamais bloquant
        return []
    return _records(payload)


# ══════════════════════════════════════════════════════════════
# Calendrier
# ══════════════════════════════════════════════════════════════


def _movie_release(movie: dict[str, Any], start: date, end: date) -> tuple[str, str] | None:
    """Date de sortie du film qui tombe dans la fenêtre, avec son type."""
    for key, label in (
        ("digitalRelease", "numérique"),
        ("physicalRelease", "physique"),
        ("inCinemas", "cinéma"),
    ):
        day = str(movie.get(key) or "")[:10]
        try:
            if start <= date.fromisoformat(day) <= end:
                return day, label
        except ValueError:
            continue
    return None


async def get_calendar(args: CalendarArgs) -> dict[str, Any]:
    """Épisodes et films SUIVIS qui sortent dans les prochains jours."""
    services = await _services(*_service_types(args.type))
    if not services:
        return {"error": "Aucun Sonarr / Radarr actif dans ArrMada."}
    start = datetime.now().date()
    end = start + timedelta(days=args.days)
    params = {"start": start.isoformat(), "end": (end + timedelta(days=1)).isoformat()}
    releases: list[dict[str, Any]] = []
    errors: list[str] = []
    for svc in services:
        service_type = svc.type.lower()
        try:
            async with _client(svc) as client:
                if service_type == "sonarr":
                    rows = await client.get("/calendar", params=params | {"includeSeries": "true"})
                else:
                    rows = await client.get("/calendar", params=params)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{svc.name} : {_error(exc)}")
            continue
        for row in rows or []:
            if service_type == "sonarr":
                day = str(row.get("airDate") or row.get("airDateUtc") or "")[:10]
                releases.append(
                    _clean(
                        {
                            "date": day,
                            "day": _day_name(day),
                            "type": "series",
                            "title": (row.get("series") or {}).get("title"),
                            "episode": f"S{row.get('seasonNumber', 0):02d}"
                            f"E{row.get('episodeNumber', 0):02d}",
                            "episode_title": row.get("title"),
                            "downloaded": bool(row.get("hasFile")),
                        }
                    )
                )
            else:
                picked = _movie_release(row, start, end)
                if picked is None:
                    continue
                releases.append(
                    _clean(
                        {
                            "date": picked[0],
                            "day": _day_name(picked[0]),
                            "type": "movie",
                            "title": row.get("title"),
                            "release": picked[1],
                            "downloaded": bool(row.get("hasFile")),
                        }
                    )
                )
    releases.sort(key=lambda r: r.get("date", ""))
    result: dict[str, Any] = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "count": len(releases),
        "releases": releases[:40],
    }
    if errors:
        result["errors"] = errors
    if not releases and not errors:
        result["note"] = "Rien de prévu sur cette période dans les titres suivis."
    return result


# ══════════════════════════════════════════════════════════════
# Manquants
# ══════════════════════════════════════════════════════════════


async def get_missing(args: MissingArgs) -> dict[str, Any]:
    """Titres suivis, déjà sortis, sans fichier (« Wanted › Missing » des *arr)."""
    services = await _services(*_service_types(args.type))
    if not services:
        return {"error": "Aucun Sonarr / Radarr actif dans ArrMada."}
    result: dict[str, Any] = {}
    errors: list[str] = []
    for svc in services:
        service_type = svc.type.lower()
        params: dict[str, Any] = {"page": 1, "pageSize": 500, "monitored": "true"}
        if service_type == "sonarr":
            params["includeSeries"] = "true"
        try:
            async with _client(svc) as client:
                payload = await client.get("/wanted/missing", params=params)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{svc.name} : {_error(exc)}")
            continue
        records = _records(payload)
        total = payload.get("totalRecords") if isinstance(payload, dict) else None
        if service_type == "sonarr":
            # Une ligne par SÉRIE (avec le compte), pas une par épisode.
            by_series: dict[str, dict[str, Any]] = {}
            for record in records:
                title = (record.get("series") or {}).get("title") or "Série inconnue"
                entry = by_series.setdefault(title, {"title": title, "missing_episodes": 0})
                entry["missing_episodes"] += 1
                entry.setdefault("seasons", set()).add(record.get("seasonNumber"))
            series = sorted(by_series.values(), key=lambda s: -s["missing_episodes"])
            for entry in series:
                entry["seasons"] = sorted(s for s in entry["seasons"] if s is not None)
            result["series"] = {
                "missing_episodes_total": total if total is not None else len(records),
                "series_count": len(series),
                "items": series[: args.limit],
            }
        else:
            movies = [
                _clean({"title": r.get("title"), "year": r.get("year"), "status": r.get("status")})
                for r in records
            ]
            result["movies"] = {
                "missing_total": total if total is not None else len(movies),
                "items": movies[: args.limit],
            }
    if errors:
        result["errors"] = errors
    return result


# ══════════════════════════════════════════════════════════════
# Indexeurs
# ══════════════════════════════════════════════════════════════


async def get_indexer_status(_: NoArgs) -> dict[str, Any]:
    """État des indexeurs dans Prowlarr : actifs, en échec, désactivés temporairement."""
    services = await _services("prowlarr")
    if not services:
        return {"error": "Aucun Prowlarr actif dans ArrMada."}
    try:
        async with _client(services[0]) as client:
            indexers = await client.get_indexers()
            stats = {
                row.get("indexerId"): row
                for row in (await client.get_indexer_stats()).get("indexers") or []
            }
            # Indexeurs mis en pause par Prowlarr après des échecs répétés
            try:
                paused = {
                    row.get("indexerId"): row for row in await client.get("/indexerstatus") or []
                }
            except Exception:  # noqa: BLE001 : information en plus, pas indispensable
                paused = {}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Prowlarr injoignable ou en erreur : {_error(exc)}"}

    rows = []
    for indexer in indexers or []:
        stat = stats.get(indexer.get("id"), {})
        pause = paused.get(indexer.get("id"), {})
        queries = stat.get("numberOfQueries", 0)
        failed = stat.get("numberOfFailedQueries", 0)
        rows.append(
            _clean(
                {
                    "name": indexer.get("name"),
                    "protocol": indexer.get("protocol"),
                    "enabled": bool(indexer.get("enable")),
                    "queries": queries,
                    "failed_queries": failed,
                    "success_percent": round((queries - failed) / queries * 100)
                    if queries
                    else None,
                    "disabled_until": str(pause.get("disabledTill") or "")[:16],
                    "last_failure": str(pause.get("mostRecentFailure") or "")[:16],
                    "messages": [m.get("message") for m in indexer.get("statusMessages") or []],
                }
            )
        )
    return diagnosis.indexer_view(rows)


# ══════════════════════════════════════════════════════════════
# Espace disque
# ══════════════════════════════════════════════════════════════

LOW_SPACE_PERCENT = 95.0


async def get_disk_space(_: NoArgs) -> dict[str, Any]:
    """Espace disque vu par Radarr / Sonarr, un chemin n'apparaissant qu'une fois."""
    raw = await copilot_tools.get_disk_space(NoArgs())
    if "error" in raw:
        return raw
    disks: dict[str, dict[str, Any]] = {}
    errors = []
    for service in raw.get("services") or []:
        if service.get("error"):
            errors.append(service["error"])
        for disk in service.get("disks") or []:
            disks.setdefault(str(disk.get("path")), _clean(disk))
    rows = list(disks.values())
    result: dict[str, Any] = {
        "disks": rows,
        "almost_full": [
            d["path"] for d in rows if (d.get("used_percent") or 0) >= LOW_SPACE_PERCENT
        ],
    }
    if errors:
        result["errors"] = errors
    return result


# ══════════════════════════════════════════════════════════════
# Registre : LA liste blanche
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Tool:
    name: str
    label: str  # affiché dans l'interface pendant l'appel
    description: str  # lue par le modèle pour choisir l'outil
    args: type[BaseModel]
    handler: Callable[[Any], Awaitable[Any]]
    # True : l'outil modifie quelque chose. Son ``handler`` ne fait alors RIEN :
    # il rend un ``write_tools.Plan`` (ce qui serait fait), que la boucle
    # soumet à la confirmation de l'utilisateur avant de l'exécuter.
    write: bool = False
    # True : outil d'enquête (historique, indexeurs, disque). Après l'un d'eux,
    # la boucle refuse toute action dans le même tour (voir agent.py).
    diagnostic: bool = False


READ_TOOLS: tuple[Tool, ...] = (
    Tool(
        "search_series",
        "Recherche d'une série",
        "Cherche une SÉRIE par son titre : dit si elle existe, son année, son nombre de "
        "saisons, et si elle est déjà dans la bibliothèque. À appeler dès qu'une série est "
        "nommée, avant toute autre chose.",
        TitleSearchArgs,
        search_series,
    ),
    Tool(
        "search_movie",
        "Recherche d'un film",
        "Cherche un FILM par son titre : dit s'il existe, son année, s'il est déjà dans la "
        "bibliothèque et s'il a un fichier. À appeler dès qu'un film est nommé, avant toute "
        "autre chose.",
        TitleSearchArgs,
        search_movie,
    ),
    Tool(
        "get_queue",
        "File de téléchargement",
        "Téléchargements en cours ou bloqués dans Sonarr et Radarr (état, progression, message "
        "d'erreur, indexeur) et état de SABnzbd. Filtrable par titre. PREMIER outil à appeler "
        "pour « où en est… », « pourquoi … ne se télécharge pas », « … n'apparaît pas », "
        "« qu'est-ce qui télécharge ».",
        QueueArgs,
        get_queue,
    ),
    Tool(
        "get_history",
        "Historique des téléchargements",
        "Derniers événements de Sonarr et Radarr : release récupérée, importée, échouée, avec "
        "la raison de l'échec, plus les avertissements des journaux sur ce titre. Filtrable par "
        "titre. À appeler APRÈS get_queue, pour comprendre ce qui est arrivé à un titre précis.",
        HistoryArgs,
        get_history,
        diagnostic=True,
    ),
    Tool(
        "get_calendar",
        "Calendrier des sorties",
        "Épisodes et films SUIVIS qui sortent dans les prochains jours, avec la date et le "
        "jour de la semaine. À appeler pour « qu'est-ce qui sort… », « quand sort le prochain "
        "épisode de… ».",
        CalendarArgs,
        get_calendar,
    ),
    Tool(
        "get_missing",
        "Titres manquants",
        "Films et épisodes suivis, déjà sortis, mais absents de la bibliothèque. À appeler "
        "pour « qu'est-ce qui me manque », « liste les films manquants ».",
        MissingArgs,
        get_missing,
    ),
    Tool(
        "get_indexer_status",
        "État des indexeurs",
        "État des indexeurs de Prowlarr : lesquels répondent, lesquels sont en échec ou "
        "désactivés. À appeler quand aucune release n'est trouvée ou pour « mes indexeurs "
        "marchent-ils ».",
        NoArgs,
        get_indexer_status,
        diagnostic=True,
    ),
    Tool(
        "get_disk_space",
        "Espace disque",
        "Espace libre et occupé sur les disques de la médiathèque et des téléchargements. À "
        "appeler pour « reste-t-il de la place » ou quand un import échoue.",
        NoArgs,
        get_disk_space,
        diagnostic=True,
    ),
)


# Remplace toute la liste quand il est renseigné : le banc de test y met ses
# faux outils. ``None`` en fonctionnement normal.
OVERRIDE: tuple[Tool, ...] | None = None


def exposed() -> tuple[Tool, ...]:
    """LA liste blanche : les outils proposés au modèle à cet instant."""
    if OVERRIDE is not None:
        return OVERRIDE
    if not settings.LOCAL_AGENT_WRITE_TOOLS:
        return READ_TOOLS
    # Import tardif : write_tools s'appuie sur ce fichier (recherche de titres).
    from app.services.local_agent import write_tools

    return READ_TOOLS + write_tools.WRITE_TOOLS


def resolve(name: str) -> Tool | None:
    """Outil par son nom EXACT. Un nom approchant n'est pas deviné : il est rejeté."""
    for tool in exposed():
        if tool.name == name:
            return tool
    return None


def writes_exposed() -> bool:
    """Des outils d'écriture sont-ils proposés au modèle ? (choix de la consigne)"""
    return any(tool.write for tool in exposed())


def label_of(name: str) -> str:
    tool = resolve(name)
    return tool.label if tool else name


def definitions() -> list[dict[str, Any]]:
    """La liste d'outils au format attendu par Ollama (``tools`` de ``/api/chat``)."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": copilot_tools._strip_titles(tool.args.model_json_schema()),
            },
        }
        for tool in exposed()
    ]


# ══════════════════════════════════════════════════════════════
# Exécution validée
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ToolOutcome:
    content: str  # ce que le modèle reçoit
    is_error: bool  # l'outil a tourné mais a échoué (service en panne…)
    invalid: bool  # l'appel lui-même était faux (outil inconnu, paramètres refusés)
    duration_ms: int


def serialise(result: Any, redactor: Redactor) -> str:
    text = json.dumps(redactor.data(result), ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = (
            f"{text[:MAX_RESULT_CHARS]}\n[… résultat coupé. Affine la demande "
            "(titre, type, limite) pour voir la suite.]"
        )
    return text


# Ajouté à tout appel rejeté. Sans cette phrase, un petit modèle « comble le
# vide » : vu au banc de test, il a inventé une liste d'épisodes après un rejet.
_REJECTED = (
    "APPEL REJETÉ : rien n'a été exécuté et tu n'as reçu AUCUNE donnée. Corrige l'appel et "
    "recommence, ou dis à l'utilisateur que tu n'as pas pu obtenir l'information. N'invente rien."
)


def validate(name: str, raw_arguments: Any) -> tuple[Tool, BaseModel] | ToolOutcome:
    """Contrôle du « bon de commande » : outil de la liste blanche, paramètres conformes.

    Rend l'outil et ses paramètres validés, ou le rejet à rendre au modèle.
    Rien n'est exécuté ici.
    """
    tool = resolve(name)
    if tool is None:
        known = ", ".join(t.name for t in exposed())
        return ToolOutcome(
            f"Outil inconnu : {name!r}. Seuls ces outils existent : {known}. {_REJECTED}",
            True,
            True,
            0,
        )
    if not isinstance(raw_arguments, dict):
        return ToolOutcome(
            f"Arguments illisibles pour {tool.name} : un objet JSON est attendu. {_REJECTED}",
            True,
            True,
            0,
        )
    args = copilot_tools.parse_args(tool, raw_arguments)  # type: ignore[arg-type]
    if isinstance(args, str):
        return ToolOutcome(f"{args}. {_REJECTED}", True, True, 0)
    return tool, args


async def execute(name: str, raw_arguments: Any, redactor: Redactor) -> ToolOutcome:
    """Valide le « bon de commande » puis exécute un outil de LECTURE. Ne lève jamais.

    Trois issues, toutes rendues au modèle sous forme de texte :

    - appel invalide (``invalid``) : outil hors liste blanche ou paramètres
      refusés par le schéma. Rien n'a été exécuté ;
    - échec (``is_error``) : l'outil a tourné, le service derrière a répondu
      une erreur ou n'a pas répondu ;
    - succès : le résultat JSON, sans secret et borné en taille.

    Un outil d'écriture n'est JAMAIS exécuté ici : il passe par la
    confirmation de la boucle (``agent._run_action``).
    """
    checked = validate(name, raw_arguments)
    if isinstance(checked, ToolOutcome):
        return checked
    tool, args = checked
    if tool.write:
        return ToolOutcome(
            f"{tool.name} est une action : elle passe par la confirmation.", True, True, 0
        )

    started = time.monotonic()

    def outcome(content: str, *, is_error: bool) -> ToolOutcome:
        return ToolOutcome(content, is_error, False, int((time.monotonic() - started) * 1000))

    try:
        result = await asyncio.wait_for(tool.handler(args), timeout=TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        return outcome(
            f"{tool.name} n'a pas répondu en {TOOL_TIMEOUT_SECONDS} s "
            "(service lent ou injoignable).",
            is_error=True,
        )
    except Exception as exc:  # noqa: BLE001 : l'échec est rendu au modèle, qui l'explique
        logger.warning("Agent local : outil %s en échec : %s", tool.name, exc)
        return outcome(redactor.text(f"{tool.name} a échoué : {_error(exc)}"), is_error=True)
    is_error = isinstance(result, dict) and set(result) == {"error"}
    return outcome(serialise(result, redactor), is_error=is_error)

"""Outils du copilote : tout ce que le modèle peut LIRE de l'installation.

Chaque outil est une fonction en lecture seule branchée sur un service
existant d'ArrMada (clients *arr, agrégateur, cache TRaSH, journaux Docker…).
Aucun n'écrit quoi que ce soit : le copilote conseille et simule, l'utilisateur
agit (ADR-017). Ajouter une action passera par un outil dédié avec
confirmation, jamais par un de ceux-ci.

Un outil = un modèle pydantic pour ses arguments (le schéma JSON envoyé au
modèle en est tiré, et les arguments reçus sont validés avec) + une fonction
asynchrone qui renvoie une structure JSON. Le résultat est ensuite nettoyé de
ses secrets (``redaction``) et borné en taille avant de partir chez Anthropic.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from app import __version__
from app.config import settings
from app.database import async_session_factory
from app.models.service import Service
from app.services import activity_log, health_checker, media_aggregator
from app.services.copilot import knowledge
from app.services.copilot.redaction import MASK, Redactor, is_secret_name
from app.services.encryption import decrypt_api_key
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Remplacée par les tests (base en mémoire), comme dans les autres services
# qui ouvrent leurs propres sessions hors d'une requête.
session_factory = async_session_factory

# Un résultat plus long est coupé : au-delà, c'est du contexte (et de l'argent)
# dépensé pour des lignes que le modèle ne lira pas mieux qu'un résumé.
MAX_RESULT_CHARS = 30_000
TOOL_TIMEOUT_SECONDS = 60
ARR_TIMEOUT_SECONDS = 30

ManagerType = Literal["radarr", "sonarr"]


# ══════════════════════════════════════════════════════════════
# Accès aux services
# ══════════════════════════════════════════════════════════════


async def _services(*types: str, enabled_only: bool = True) -> list[Service]:
    """Services enregistrés, filtrés par type (``radarr``, ``sonarr``…)."""
    async with session_factory() as db:
        rows = list((await db.execute(select(Service))).scalars())
    return [
        svc
        for svc in rows
        if (not types or svc.type.lower() in types) and (svc.is_enabled or not enabled_only)
    ]


@contextlib.asynccontextmanager
async def _client(service: Service):
    """Client HTTP du service (clé déchiffrée), fermé en sortie."""
    client = health_checker._build_client(service)
    client.timeout = ARR_TIMEOUT_SECONDS
    try:
        yield client
    finally:
        await client.close()


def _error(exc: Exception) -> str:
    """Erreur lisible par le modèle : type + message, sans trace."""
    message = str(exc).strip() or "sans message"
    return f"{type(exc).__name__} : {message}"[:500]


async def _per_service(
    types: tuple[str, ...], fetch: Callable[[Service, Any], Awaitable[dict[str, Any]]]
) -> dict[str, Any]:
    """Applique ``fetch`` à chaque service du type demandé ; une panne n'arrête pas les autres."""
    services = await _services(*types)
    if not services:
        return {
            "error": f"Aucun service {' / '.join(types)} actif dans ArrMada "
            "(Paramètres › Services)."
        }
    results = []
    for svc in services:
        try:
            async with _client(svc) as client:
                data = await fetch(svc, client)
        except Exception as exc:  # noqa: BLE001 : la panne est une information pour le modèle
            data = {"error": f"{svc.name} injoignable ou en erreur : {_error(exc)}"}
        results.append({"service": svc.name, "type": svc.type.lower(), **data})
    return {"services": results}


# ══════════════════════════════════════════════════════════════
# Mise en forme des réponses *arr (brutes : trop verbeuses pour un modèle)
# ══════════════════════════════════════════════════════════════


def _quality_names(item: dict[str, Any]) -> Any:
    """Une ligne de profil : une qualité, ou un groupe de qualités fusionnées."""
    if item.get("items"):
        return {
            "group": item.get("name"),
            "qualities": [q.get("quality", {}).get("name") for q in item["items"]],
        }
    return item.get("quality", {}).get("name")


def _cutoff_name(profile: dict[str, Any]) -> Any:
    cutoff = profile.get("cutoff")
    for item in profile.get("items") or []:
        if item.get("id") == cutoff and item.get("name"):
            return item["name"]
        if item.get("quality", {}).get("id") == cutoff:
            return item["quality"].get("name")
    return cutoff


def _profile_summary(profile: dict[str, Any], used_by: Counter[int] | None) -> dict[str, Any]:
    scores = sorted(
        ((f.get("name"), f.get("score", 0)) for f in profile.get("formatItems") or []),
        key=lambda pair: pair[1],
        reverse=True,
    )
    summary: dict[str, Any] = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "upgrade_allowed": profile.get("upgradeAllowed"),
        "cutoff": _cutoff_name(profile),
        "min_format_score": profile.get("minFormatScore"),
        "cutoff_format_score": profile.get("cutoffFormatScore"),
        "min_upgrade_format_score": profile.get("minUpgradeFormatScore"),
        # Du meilleur au moins bon (l'API les donne dans l'autre sens)
        "allowed_qualities": [
            _quality_names(i) for i in reversed(profile.get("items") or []) if i.get("allowed")
        ],
        "format_scores": {name: score for name, score in scores if score},
        "formats_scored_zero": sum(1 for _, score in scores if not score),
    }
    if profile.get("language"):
        summary["language"] = profile["language"].get("name")
    if used_by is not None:
        summary["used_by_titles"] = used_by.get(profile.get("id"), 0)
    return summary


def _field_value(spec: dict[str, Any]) -> Any:
    """Valeur d'une condition de format (les champs sont une liste côté API, un dict côté TRaSH)."""
    fields = spec.get("fields")
    if isinstance(fields, dict):
        return fields.get("value")
    for f in fields or []:
        if isinstance(f, dict) and f.get("name") == "value":
            return f.get("value")
    return None


def _spec_summary(spec: dict[str, Any]) -> dict[str, Any]:
    value = _field_value(spec)
    if isinstance(value, str) and len(value) > 300:
        value = value[:300] + "…"
    return {
        "name": spec.get("name"),
        "type": str(spec.get("implementation", "")).removesuffix("Specification"),
        "negate": bool(spec.get("negate")),
        "required": bool(spec.get("required")),
        "value": value,
    }


# Clés d'un fournisseur (client de téléchargement, indexeur, notification…)
# qui ne décrivent que l'interface de l'*arr, pas la configuration.
_PROVIDER_NOISE = {"fields", "presets", "infoLink", "message", "implementationName"}


def _compact_provider(item: Any) -> Any:
    """Fournisseur *arr : ses ~30 champs de formulaire réduits à ``{nom: valeur}``."""
    if not isinstance(item, dict) or not isinstance(item.get("fields"), list):
        return item
    out = {k: v for k, v in item.items() if k not in _PROVIDER_NOISE}
    fields: dict[str, Any] = {}
    for f in item["fields"]:
        if not isinstance(f, dict):
            continue
        value = f.get("value")
        if value in (None, "", []):
            continue
        private = str(f.get("privacy", "")).lower() in {"password", "apikey"}
        fields[str(f.get("name"))] = MASK if private or is_secret_name(f.get("name")) else value
    out["fields"] = fields
    return out


def _fold(text: Any) -> str:
    return knowledge.fold(str(text or ""))


def _matches(text: Any, words: list[str]) -> bool:
    folded = _fold(text)
    return all(word in folded for word in words)


def _words(query: str) -> list[str]:
    return [w for w in _fold(query).split() if w]


def _find(items: list[Any], text_of: Callable[[Any], Any], words: list[str]) -> list[Any]:
    """Éléments dont le texte contient TOUS les mots ; à défaut, au moins un.

    « dv hdr10 » ne correspond à aucun nom exact de format : mieux vaut rendre
    « DV Boost » et « HDR10+ Boost » qu'une liste vide.
    """
    found = [item for item in items if _matches(text_of(item), words)]
    if found or len(words) < 2:
        return found
    return [item for item in items if any(word in _fold(text_of(item)) for word in words)]


# ══════════════════════════════════════════════════════════════
# Arguments des outils
# ══════════════════════════════════════════════════════════════


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class ArrHealthArgs(_Args):
    service: Literal["radarr", "sonarr", "lidarr", "readarr", "prowlarr"] = Field(
        description="Application à interroger."
    )


class ManagerArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")


class CustomFormatsArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")
    search: str = Field(
        default="",
        description="Mots du nom du format. Vide : seulement la liste des noms. "
        "Renseigné : le détail des conditions des formats trouvés.",
    )


ConfigSection = Literal[
    "naming",
    "media_management",
    "download_clients",
    "download_client_config",
    "indexers",
    "indexer_config",
    "root_folders",
    "remote_path_mappings",
    "import_lists",
    "quality_definitions",
    "delay_profiles",
    "release_profiles",
    "notifications",
    "tags",
    "host",
    "applications",
]

_CONFIG_ENDPOINTS: dict[str, str] = {
    "naming": "/config/naming",
    "media_management": "/config/mediamanagement",
    "download_clients": "/downloadclient",
    "download_client_config": "/config/downloadclient",
    "indexers": "/indexer",
    "indexer_config": "/config/indexer",
    "root_folders": "/rootfolder",
    "remote_path_mappings": "/remotepathmapping",
    "import_lists": "/importlist",
    "quality_definitions": "/qualitydefinition",
    "delay_profiles": "/delayprofile",
    "release_profiles": "/releaseprofile",
    "notifications": "/notification",
    "tags": "/tag",
    "host": "/config/host",
    "applications": "/applications",
}


class ArrConfigArgs(_Args):
    service: Literal["radarr", "sonarr", "lidarr", "prowlarr"] = Field(
        description="Application dont lire la configuration."
    )
    section: ConfigSection = Field(
        description="Partie de la configuration. naming : schéma de nommage ; "
        "media_management : hardlinks, corbeille, permissions, import ; "
        "download_clients / download_client_config : clients et gestion des téléchargements "
        "terminés ou échoués ; indexers / indexer_config : indexeurs vus par l'application ; "
        "root_folders ; remote_path_mappings ; import_lists ; quality_definitions : tailles "
        "min / max par qualité ; delay_profiles ; release_profiles (Sonarr) ; notifications : "
        "webhooks et connexions ; tags ; host : port, authentification, mises à jour ; "
        "applications : applications reliées (Prowlarr seulement)."
    )


class TrashSearchArgs(_Args):
    service: ManagerType = Field(description="radarr (films) ou sonarr (séries).")
    kind: Literal["custom_formats", "quality_profiles", "cf_groups", "naming", "quality_sizes"] = (
        Field(description="Type de donnée TRaSH à chercher.")
    )
    query: str = Field(
        default="",
        description="Mots à trouver dans le nom (ex. « DV HDR10 », « Remux 2160p », « x265 »). "
        "Vide : la liste des noms disponibles.",
    )


class DockerLogsArgs(_Args):
    service: str = Field(
        default="", description="Nom (ou partie du nom) du conteneur. Vide : tous les conteneurs."
    )
    level: Literal["problems", "error", "warning", "all"] = Field(
        default="problems",
        description="problems = erreurs et avertissements (par défaut) ; all = toutes les lignes.",
    )
    search: str = Field(default="", description="Texte à trouver dans les messages.")
    limit: int = Field(default=60, ge=1, le=200, description="Nombre maximal de messages.")


class LibrarySearchArgs(_Args):
    query: str = Field(default="", description="Mots du titre. Vide : tous les titres.")
    type: Literal["all", "movie", "series"] = Field(default="all")
    only_missing: bool = Field(
        default=False, description="Seulement les titres surveillés qui n'ont aucun fichier."
    )
    limit: int = Field(default=25, ge=1, le=100)


class MediaDetailsArgs(_Args):
    type: Literal["movie", "series"] = Field(description="movie (Radarr) ou series (Sonarr).")
    id: int = Field(
        description="Identifiant du titre dans Radarr / Sonarr : le champ `external_id` "
        "renvoyé par search_library."
    )


class ActivityLogArgs(_Args):
    search: str = Field(default="", description="Texte à trouver dans le titre de l'événement.")
    category: str = Field(
        default="", description="Catégorie exacte (ex. download, import, subtitle, request)."
    )
    status: str = Field(default="", description="Statut exact (ex. error, success, warning).")
    limit: int = Field(default=40, ge=1, le=150)


class DocsSearchArgs(_Args):
    query: str = Field(description="Mots-clés de la question, en français.")


class DocsReadArgs(_Args):
    doc: str = Field(
        description="Identifiant du document (ex. « adr-012 », « changelog », « readme »)."
    )
    section: str = Field(
        default="",
        description="Extrait d'un titre de section pour ne lire que celle-ci. "
        "Indispensable pour le changelog, trop long pour être lu d'un bloc.",
    )


# ══════════════════════════════════════════════════════════════
# Outils
# ══════════════════════════════════════════════════════════════


async def get_overview(_: NoArgs) -> dict[str, Any]:
    async with session_factory() as db:
        services = list((await db.execute(select(Service))).scalars())
        try:
            library: list[dict[str, Any]] | None = await media_aggregator.cached_library(db)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Copilote : médiathèque indisponible : %s", exc)
            library = None

    # Kodi et amplis sont des APPAREILS rangés dans la même table : ils n'ont pas
    # d'API *arr, les sonder avec le client générique les donnerait « hors ligne »
    # ou « dégradés » à tort (même règle que health_checker.check_all_services).
    devices = [svc for svc in services if svc.type.lower() in health_checker._DEVICE_TYPES]
    services = [svc for svc in services if svc not in devices]
    enabled = [svc for svc in services if svc.is_enabled]
    checks = await asyncio.gather(
        *(health_checker.check_service(svc) for svc in enabled), return_exceptions=True
    )
    live = dict(zip((svc.id for svc in enabled), checks, strict=True))

    described = []
    for svc in services:
        entry: dict[str, Any] = {
            "name": svc.name,
            "type": svc.type.lower(),
            "url": svc.url,
            "enabled": svc.is_enabled,
        }
        check = live.get(svc.id)
        if isinstance(check, Exception):
            entry.update(status="offline", error=_error(check))
        elif check is not None:
            entry.update(status=check.status, version=check.version, latency_ms=check.latency_ms)
            if check.error:
                entry["error"] = check.error
        described.append(entry)

    overview: dict[str, Any] = {
        "now": datetime.now().astimezone().isoformat(timespec="minutes"),
        "arrmada_version": __version__,
        "services": described,
        "devices": [
            {"name": svc.name, "type": svc.type.lower(), "url": svc.url, "enabled": svc.is_enabled}
            for svc in devices
        ],
        "devices_note": "TV Kodi et amplis : simplement listés, leur état n'est pas testé ici.",
    }
    if library is not None:
        movies = [m for m in library if m.get("type") == "movie"]
        series = [m for m in library if m.get("type") == "series"]
        overview["library"] = {
            "movies": len(movies),
            "movies_monitored_without_file": sum(
                1 for m in movies if m.get("monitored") and not m.get("has_file")
            ),
            "series": len(series),
            "episodes_on_disk": sum(s.get("episodes_have") or 0 for s in series),
            "episodes_total": sum(s.get("episodes_total") or 0 for s in series),
            "size_on_disk": format_bytes(sum(m.get("size_bytes") or 0 for m in library)),
        }
    with contextlib.suppress(Exception):
        from app.services.trash_guides import get_trash_cache

        overview["trash_guides_cache"] = get_trash_cache().status
    return overview


async def get_arr_health(args: ArrHealthArgs) -> dict[str, Any]:
    status_keys = (
        "appName",
        "instanceName",
        "version",
        "branch",
        "isDocker",
        "osName",
        "osVersion",
        "runtimeVersion",
        "databaseType",
        "authentication",
        "urlBase",
        "startTime",
        "packageUpdateMechanism",
    )

    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        health = await client.get("/health")
        status = await client.get("/system/status")
        return {
            "health_warnings": [
                {k: item.get(k) for k in ("type", "source", "message", "wikiUrl")}
                for item in health or []
            ],
            "system": {k: status.get(k) for k in status_keys if k in status},
        }

    return await _per_service((args.service,), fetch)


async def get_quality_profiles(args: ManagerArgs) -> dict[str, Any]:
    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        profiles = await client.get("/qualityprofile")
        used_by: Counter[int] | None
        try:
            titles = await client.get("/movie" if args.service == "radarr" else "/series")
            used_by = Counter(t.get("qualityProfileId") for t in titles)
        except Exception as exc:  # noqa: BLE001 : le comptage est un plus
            logger.debug("Copilote : comptage par profil indisponible : %s", exc)
            used_by = None
        return {"profiles": [_profile_summary(p, used_by) for p in profiles]}

    return await _per_service((args.service,), fetch)


async def get_custom_formats(args: CustomFormatsArgs) -> dict[str, Any]:
    words = _words(args.search)

    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        formats = await client.get("/customformat")
        if not words:
            return {"count": len(formats), "names": sorted(cf.get("name", "") for cf in formats)}
        found = _find(formats, lambda cf: cf.get("name"), words)
        return {
            "count": len(formats),
            "matching": len(found),
            "formats": [
                {
                    "name": cf.get("name"),
                    "in_file_names": bool(cf.get("includeCustomFormatWhenRenaming")),
                    "conditions": [_spec_summary(s) for s in cf.get("specifications") or []],
                }
                for cf in found[:15]
            ],
        }

    return await _per_service((args.service,), fetch)


async def get_arr_config(args: ArrConfigArgs) -> dict[str, Any]:
    endpoint = _CONFIG_ENDPOINTS[args.section]

    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        data = await client.get(endpoint)
        if isinstance(data, list):
            data = [_compact_provider(item) for item in data]
        return {"section": args.section, "config": data}

    return await _per_service((args.service,), fetch)


def _expected_scores(cache: Any, profile: dict[str, Any], service: str) -> dict[str, int]:
    """Scores voulus par un profil TRaSH : {nom du format: score}."""
    from app.services.trash_apply import format_score

    score_set = profile.get("trash_score_set") or "default"
    items = profile.get("formatItems") or {}
    pairs = items.items() if isinstance(items, dict) else ((name, None) for name in items)
    expected: dict[str, int] = {}
    for name, trash_id in pairs:
        cf = (cache.get_cf_by_id(trash_id, service) if trash_id else None) or cache.get_cf_by_name(
            name, service
        )
        if cf:
            expected[cf["name"]] = format_score(cf, score_set)
    return expected


def _capped(items: list[Any], limit: int = 40) -> dict[str, Any]:
    """Liste bornée, avec son vrai total (le modèle sait ainsi qu'il en manque)."""
    return {"count": len(items), "items": items[:limit]}


async def audit_trash_guides(args: ManagerArgs) -> dict[str, Any]:
    from app.services.trash_apply import cf_matches, cf_payload
    from app.services.trash_guides import get_trash_cache

    cache = get_trash_cache()
    trash_formats = cache.get_custom_formats(args.service)
    if not trash_formats:
        return {"error": _TRASH_EMPTY}
    trash_by_name = {cf["name"].lower(): cf for cf in trash_formats}
    trash_profiles = {qp["name"].lower(): qp for qp in cache.get_quality_profiles(args.service)}

    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        current_formats = await client.get("/customformat")
        profiles = await client.get("/qualityprofile")
        current_names = {cf.get("name", "").lower() for cf in current_formats}

        drifted = [
            cf["name"]
            for cf in current_formats
            if cf.get("name", "").lower() in trash_by_name
            and not cf_matches(cf, cf_payload(trash_by_name[cf["name"].lower()]))
        ]
        own = [
            cf.get("name")
            for cf in current_formats
            if cf.get("name", "").lower() not in trash_by_name
        ]

        audited, unrecognised = [], []
        for profile in profiles:
            reference = trash_profiles.get(str(profile.get("name", "")).lower())
            if reference is None:
                unrecognised.append(profile.get("name"))
                continue
            expected = _expected_scores(cache, reference, args.service)
            current = {f.get("name"): f.get("score", 0) for f in profile.get("formatItems") or []}
            score_gaps = [
                {
                    "format": name,
                    "trash": score,
                    "current": current.get(name) if name.lower() in current_names else "absent",
                }
                for name, score in expected.items()
                if current.get(name) != score
            ]
            outside = [
                {"format": name, "score": score}
                for name, score in current.items()
                if score and name not in expected
            ]
            settings_gaps = {
                key: {"trash": reference.get(key), "current": profile.get(key)}
                for key in (
                    "upgradeAllowed",
                    "minFormatScore",
                    "cutoffFormatScore",
                    "minUpgradeFormatScore",
                )
                if key in reference and reference.get(key) != profile.get(key)
            }
            if str(reference.get("cutoff")) != str(_cutoff_name(profile)):
                settings_gaps["cutoff"] = {
                    "trash": reference.get("cutoff"),
                    "current": _cutoff_name(profile),
                }
            audited.append(
                {
                    "profile": profile.get("name"),
                    "trash_url": reference.get("trash_url"),
                    "score_set": reference.get("trash_score_set"),
                    "formats_expected": len(expected),
                    "score_gaps": _capped(score_gaps),
                    "scored_outside_base_profile": _capped(outside),
                    "settings_gaps": settings_gaps,
                }
            )
        return {
            "profiles_matching_a_trash_profile": audited,
            "profiles_not_in_trash_guides": unrecognised,
            "formats_whose_definition_differs_from_trash": _capped(drifted),
            "formats_not_from_trash": _capped(own),
            "note": "scored_outside_base_profile n'est pas forcément une erreur : ArrMada "
            "ajoute les groupes de formats optionnels choisis dans l'assistant TRaSH "
            "(écran, audio…), absents de la liste de base du profil.",
        }

    result = await _per_service((args.service,), fetch)
    result["trash_cache"] = cache.status
    return result


# Le copilote ne lance jamais la synchronisation lui-même : elle interroge
# GitHub (appels limités par heure) et c'est le planificateur d'ArrMada qui la
# tient à jour. L'âge du cache est renvoyé avec chaque résultat.
_TRASH_EMPTY = (
    "Données TRaSH absentes du cache : lance la synchronisation dans "
    "Maintenance › TRaSH Guides, puis redemande."
)


def _strip_html(text: Any) -> str:
    return re.sub(r"<br\s*/?>", "\n", str(text or "")).strip()


async def search_trash_guides(args: TrashSearchArgs) -> dict[str, Any]:
    from app.services.trash_guides import get_trash_cache

    cache = get_trash_cache()
    words = _words(args.query)
    if not cache.get_custom_formats(args.service):
        return {"error": _TRASH_EMPTY}

    if args.kind == "custom_formats":
        formats = cache.get_custom_formats(args.service)
        if not words:
            return {"count": len(formats), "names": sorted(cf.get("name", "") for cf in formats)}
        found = _find(formats, lambda cf: cf.get("name"), words)
        return {
            "matching": len(found),
            "formats": [
                {
                    "name": cf.get("name"),
                    "trash_id": cf.get("trash_id"),
                    "scores_by_score_set": cf.get("trash_scores") or {},
                    "file": cf.get("_source_file"),
                    "conditions": [_spec_summary(s) for s in (cf.get("specifications") or [])[:8]],
                }
                for cf in found[:12]
            ],
        }

    if args.kind == "quality_profiles":
        profiles = cache.get_quality_profiles(args.service)
        if not words:
            return {
                "count": len(profiles),
                "profiles": [
                    {"name": qp.get("name"), "url": qp.get("trash_url")} for qp in profiles
                ],
            }
        found = [
            qp
            for qp in profiles
            if _matches(f"{qp.get('name')} {qp.get('trash_description', '')}", words)
        ]
        return {
            "matching": len(found),
            "profiles": [
                {
                    "name": qp.get("name"),
                    "description": _strip_html(qp.get("trash_description")),
                    "url": qp.get("trash_url"),
                    "score_set": qp.get("trash_score_set"),
                    "upgrade_allowed": qp.get("upgradeAllowed"),
                    "cutoff": qp.get("cutoff"),
                    "min_format_score": qp.get("minFormatScore"),
                    "cutoff_format_score": qp.get("cutoffFormatScore"),
                    "min_upgrade_format_score": qp.get("minUpgradeFormatScore"),
                    "language": qp.get("language"),
                    "qualities": qp.get("items"),
                    "format_scores": _expected_scores(cache, qp, args.service),
                }
                for qp in found[:5]
            ],
        }

    if args.kind == "cf_groups":
        groups = cache.get_cf_groups(args.service)
        found = [g for g in groups if _matches(g.get("name"), words)] if words else groups
        if not words:
            return {"count": len(groups), "names": [g.get("name") for g in groups]}
        return {"matching": len(found), "groups": found[:6]}

    if args.kind == "naming":
        # Pas d'accesseur public : même cache, clé « <service>_naming ».
        return {"naming": cache._data.get(f"{args.service}_naming", [])}

    return {"quality_sizes": cache.get_quality_sizes(args.service), "trash_cache": cache.status}


_QUEUE_KEYS = (
    "title",
    "status",
    "tracked_state",
    "progress",
    "time_left",
    "source_service",
    "download_client",
    "protocol",
    "indexer",
    "quality",
    "error",
    "detail",
    "episode_count",
    "season_number",
    "movie_id",
    "series_id",
)


async def get_download_queue(_: NoArgs) -> dict[str, Any]:
    async with session_factory() as db:
        items = await media_aggregator.get_queue_items(db)
    queue = [
        {
            **{key: item.get(key) for key in _QUEUE_KEYS if item.get(key) not in (None, "")},
            "size": format_bytes(item.get("size_bytes")),
        }
        for item in items
    ]
    result: dict[str, Any] = {"arr_queue": _capped(queue, 60)}

    clients = []
    for svc in await _services("sabnzbd"):
        try:
            async with _client(svc) as client:
                sab_queue = await client.get_queue()
                history = await client.get_history(limit=40)
        except Exception as exc:  # noqa: BLE001
            clients.append({"service": svc.name, "error": _error(exc)})
            continue
        failed = [
            {
                "name": slot.get("name"),
                "category": slot.get("category"),
                "fail_message": slot.get("fail_message"),
            }
            for slot in history.get("slots") or []
            if str(slot.get("status", "")).lower() == "failed"
        ]
        clients.append(
            {
                "service": svc.name,
                "paused": sab_queue.get("paused"),
                "speed": sab_queue.get("speed"),
                "size_left": sab_queue.get("sizeleft"),
                "time_left": sab_queue.get("timeleft"),
                "free_space_download_gb": sab_queue.get("diskspace1"),
                "free_space_complete_gb": sab_queue.get("diskspace2"),
                "slots": [
                    {
                        key: slot.get(key)
                        for key in (
                            "filename",
                            "status",
                            "percentage",
                            "priority",
                            "cat",
                            "timeleft",
                        )
                    }
                    for slot in (sab_queue.get("slots") or [])[:40]
                ],
                "recent_failures": failed[:15],
            }
        )
    if clients:
        result["sabnzbd"] = clients
    return result


async def get_indexers(_: NoArgs) -> dict[str, Any]:
    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        indexers = await client.get_indexers()
        stats = {
            row.get("indexerId"): row
            for row in (await client.get_indexer_stats()).get("indexers") or []
        }
        rows = []
        for indexer in indexers:
            row = stats.get(indexer.get("id"), {})
            queries = row.get("numberOfQueries", 0)
            failed = row.get("numberOfFailedQueries", 0)
            rows.append(
                {
                    "name": indexer.get("name"),
                    "protocol": indexer.get("protocol"),
                    "privacy": indexer.get("privacy"),
                    "enabled": indexer.get("enable"),
                    "priority": indexer.get("priority"),
                    "status_messages": [
                        m.get("message") for m in indexer.get("statusMessages") or []
                    ],
                    "queries": queries,
                    "failed_queries": failed,
                    # Pas de taux pour un indexeur jamais interrogé (0 % serait faux)
                    "query_success_percent": round((queries - failed) / queries * 100, 1)
                    if queries
                    else None,
                    "grabs": row.get("numberOfGrabs", 0),
                    "failed_grabs": row.get("numberOfFailedGrabs", 0),
                    "average_response_ms": row.get("averageResponseTime"),
                }
            )
        return {"indexers": rows}

    return await _per_service(("prowlarr",), fetch)


_DIGITS_RE = re.compile(r"\d+")


async def get_docker_logs(args: DockerLogsArgs) -> dict[str, Any]:
    from app.services import docker_logs

    async with session_factory() as db:
        entries = await docker_logs.get_aggregated_logs(db, tail=400, limit=4000)
    if not entries:
        return {
            "error": "Aucun journal lisible : le socket Docker n'est pas monté dans le conteneur "
            "ArrMada (/var/run/docker.sock), ou aucun conteneur ne correspond aux services "
            "enregistrés."
        }

    wanted_service = _fold(args.service)
    words = _words(args.search)
    levels = {"problems": {"error", "warning"}, "error": {"error"}, "warning": {"warning"}}.get(
        args.level
    )
    # Mêmes messages répétés (aux chiffres près) : une ligne, avec le compte.
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:  # du plus récent au plus ancien
        if levels and entry["level"] not in levels:
            continue
        if wanted_service and wanted_service not in _fold(
            f"{entry['service']} {entry['container']}"
        ):
            continue
        if words and not _matches(entry["message"], words):
            continue
        key = (entry["service"], entry["level"], _DIGITS_RE.sub("#", entry["message"])[:200])
        if key in grouped:
            grouped[key]["count"] += 1
            grouped[key]["first_seen"] = entry["ts"]
        else:
            grouped[key] = {
                "last_seen": entry["ts"],
                "first_seen": entry["ts"],
                "service": entry["service"],
                "level": entry["level"],
                "count": 1,
                "message": entry["message"][:600],
            }
    messages = list(grouped.values())
    return {
        "containers": sorted({entry["service"] for entry in entries}),
        "distinct_messages": len(messages),
        "messages": messages[: args.limit],
    }


async def get_disk_space(_: NoArgs) -> dict[str, Any]:
    async def fetch(_svc: Service, client: Any) -> dict[str, Any]:
        disks = []
        for disk in await client.get("/diskspace"):
            total, free = disk.get("totalSpace") or 0, disk.get("freeSpace") or 0
            disks.append(
                {
                    "path": disk.get("path"),
                    "label": disk.get("label") or None,
                    "total": format_bytes(total),
                    "free": format_bytes(free),
                    "used_percent": round((total - free) / total * 100, 1) if total else None,
                }
            )
        return {"disks": disks}

    return await _per_service(("radarr", "sonarr"), fetch)


_LIBRARY_KEYS = (
    "external_id",
    "title",
    "type",
    "year",
    "has_file",
    "monitored",
    "status",
    "quality",
    "resolution",
    "video_codec",
    "video_dynamic_range",
    "audio_codec",
    "audio_channels",
    "seasons",
    "episodes_have",
    "episodes_total",
    "source_service",
    "path",
)


async def search_library(args: LibrarySearchArgs) -> dict[str, Any]:
    async with session_factory() as db:
        library = await media_aggregator.cached_library(db)
    words = _words(args.query)
    found = [
        item
        for item in library
        if (args.type == "all" or item.get("type") == args.type)
        and (not words or _matches(item.get("title"), words))
        and (not args.only_missing or (item.get("monitored") and not item.get("has_file")))
    ]
    return {
        "library_size": len(library),
        "matching": len(found),
        "items": [
            {
                **{key: item.get(key) for key in _LIBRARY_KEYS if item.get(key) is not None},
                "size": format_bytes(item.get("size_bytes")),
            }
            for item in found[: args.limit]
        ],
    }


def _history_event(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data") or {}
    event = {
        "date": record.get("date"),
        "event": record.get("eventType"),
        "release": record.get("sourceTitle"),
        "quality": (record.get("quality") or {}).get("quality", {}).get("name"),
        "custom_formats": [cf.get("name") for cf in record.get("customFormats") or []],
        "custom_format_score": record.get("customFormatScore"),
    }
    for key in ("indexer", "downloadClient", "reason", "message", "releaseGroup", "importedPath"):
        if data.get(key):
            event[key] = data[key]
    if record.get("episodeId"):
        event["episode_id"] = record["episodeId"]
    return event


async def get_media_details(args: MediaDetailsArgs) -> dict[str, Any]:
    service_type = "radarr" if args.type == "movie" else "sonarr"
    services = await _services(service_type)
    if not services:
        return {"error": f"Aucun {service_type} actif dans ArrMada."}
    async with _client(services[0]) as client:
        profiles = {p.get("id"): p.get("name") for p in await client.get("/qualityprofile")}
        if args.type == "movie":
            movie = await client.get(f"/movie/{args.id}")
            history = await client.get("/history/movie", {"movieId": args.id})
            file = movie.get("movieFile") or {}
            details: dict[str, Any] = {
                "title": movie.get("title"),
                "year": movie.get("year"),
                "monitored": movie.get("monitored"),
                "status": movie.get("status"),
                "minimum_availability": movie.get("minimumAvailability"),
                "is_available": movie.get("isAvailable"),
                "quality_profile": profiles.get(movie.get("qualityProfileId")),
                "path": movie.get("path"),
                "has_file": movie.get("hasFile"),
            }
            if file:
                details["file"] = {
                    "name": file.get("relativePath"),
                    "size": format_bytes(file.get("size")),
                    "quality": (file.get("quality") or {}).get("quality", {}).get("name"),
                    "custom_formats": [cf.get("name") for cf in file.get("customFormats") or []],
                    "custom_format_score": file.get("customFormatScore"),
                    "cutoff_not_met": file.get("qualityCutoffNotMet"),
                    "release_group": file.get("releaseGroup"),
                    "added": file.get("dateAdded"),
                    "media_info": file.get("mediaInfo"),
                }
        else:
            series = await client.get(f"/series/{args.id}")
            history = await client.get("/history/series", {"seriesId": args.id})
            details = {
                "title": series.get("title"),
                "year": series.get("year"),
                "monitored": series.get("monitored"),
                "status": series.get("status"),
                "series_type": series.get("seriesType"),
                "quality_profile": profiles.get(series.get("qualityProfileId")),
                "path": series.get("path"),
                "seasons": [
                    {
                        "season": season.get("seasonNumber"),
                        "monitored": season.get("monitored"),
                        "episodes_on_disk": (season.get("statistics") or {}).get(
                            "episodeFileCount"
                        ),
                        "episodes_aired": (season.get("statistics") or {}).get("episodeCount"),
                        "episodes_total": (season.get("statistics") or {}).get("totalEpisodeCount"),
                    }
                    for season in series.get("seasons") or []
                ],
            }
    records = history.get("records", []) if isinstance(history, dict) else history or []
    records = sorted(records, key=lambda r: str(r.get("date")), reverse=True)
    return {
        "service": services[0].name,
        "details": details,
        "history": _capped([_history_event(r) for r in records], 40),
    }


async def get_activity_log(args: ActivityLogArgs) -> dict[str, Any]:
    async with session_factory() as db:
        events = await activity_log.query_events(
            db,
            categories=[args.category] if args.category else None,
            statuses=[args.status] if args.status else None,
            search=args.search or None,
            limit=args.limit,
        )
        rows = [activity_log.to_dict(event) for event in events]
    return {
        "events": [
            {
                "date": datetime.fromtimestamp(row["ts"]).astimezone().isoformat(timespec="seconds")
                if row["ts"]
                else None,
                **{
                    key: row[key]
                    for key in (
                        "category",
                        "action",
                        "status",
                        "source",
                        "title",
                        "subtitle",
                        "detail",
                        "device",
                    )
                    if row.get(key)
                },
            }
            for row in rows
        ]
    }


async def get_setup_checklist(_: NoArgs) -> dict[str, Any]:
    from app.services.setup_checklist import build_checklist

    async with session_factory() as db:
        checklist = await build_checklist(db)
    # « credentials » (mots de passe générés à l'installation) n'est jamais transmis.
    return {
        "todo": checklist["todo"],
        "done": checklist["done"],
        "items": [
            {
                key: item.get(key)
                for key in ("title", "status", "detail", "why", "how", "service_type")
            }
            for item in checklist["items"]
        ],
    }


async def search_arrmada_docs(args: DocsSearchArgs) -> dict[str, Any]:
    results = knowledge.search(args.query)
    if not results:
        return {"results": [], "documents": knowledge.catalog()}
    return {"results": results}


async def read_arrmada_doc(args: DocsReadArgs) -> dict[str, Any]:
    return knowledge.read(args.doc, args.section)


# ══════════════════════════════════════════════════════════════
# Registre
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Tool:
    name: str
    label: str  # affiché dans l'interface pendant l'appel
    description: str
    args: type[BaseModel]
    handler: Callable[[Any], Awaitable[Any]]


TOOLS: tuple[Tool, ...] = (
    Tool(
        "get_overview",
        "Vue d'ensemble de l'installation",
        "État général de l'installation : date et heure du serveur, services reliés à ArrMada "
        "(type, adresse, activé ou non, en ligne ou non, version, latence), appareils du salon "
        "(TV Kodi, amplis : listés sans test de connexion), taille de la médiathèque, état du "
        "cache TRaSH. À appeler en premier dès qu'une question porte sur "
        "CETTE installation, pour savoir ce qui existe avant d'interroger un service.",
        NoArgs,
        get_overview,
    ),
    Tool(
        "get_arr_health",
        "Bilan de santé de l'application",
        "Avertissements que l'application affiche elle-même dans Système › État (indexeur en "
        "échec, client de téléchargement injoignable, dossier racine manquant, mise à jour…) "
        "avec le lien vers le wiki Servarr, plus sa version et son environnement. À appeler "
        "pour tout diagnostic d'un Radarr, Sonarr, Lidarr, Readarr ou Prowlarr.",
        ArrHealthArgs,
        get_arr_health,
    ),
    Tool(
        "get_quality_profiles",
        "Profils qualité",
        "Profils qualité de Radarr ou Sonarr tels qu'ils sont réglés : qualités autorisées "
        "(de la meilleure à la moins bonne), seuil (cutoff), mises à niveau, scores minimaux, "
        "score de chaque format personnalisé, et nombre de titres qui utilisent chaque profil. "
        "À appeler avant tout avis sur un profil ou sur l'effet d'un changement de profil.",
        ManagerArgs,
        get_quality_profiles,
    ),
    Tool(
        "get_custom_formats",
        "Formats personnalisés",
        "Formats personnalisés (custom formats) présents dans Radarr ou Sonarr. Sans `search` : "
        "la liste des noms. Avec `search` : les conditions (regex, source, résolution…) des "
        "formats trouvés. Les scores, eux, sont dans get_quality_profiles.",
        CustomFormatsArgs,
        get_custom_formats,
    ),
    Tool(
        "get_arr_config",
        "Configuration de l'application",
        "Lit une partie de la configuration d'un Radarr, Sonarr, Lidarr ou Prowlarr : nommage, "
        "gestion des médias (hardlinks, corbeille, permissions), clients de téléchargement, "
        "indexeurs, dossiers racine, correspondances de chemins distants, listes d'import, "
        "tailles par qualité, profils de délai, notifications… Les clés et mots de passe sont "
        "masqués. À appeler pour vérifier une bonne pratique ou expliquer un comportement.",
        ArrConfigArgs,
        get_arr_config,
    ),
    Tool(
        "audit_trash_guides",
        "Comparaison avec les TRaSH Guides",
        "Compare Radarr ou Sonarr aux TRaSH Guides : pour chaque profil qui porte le nom d'un "
        "profil TRaSH, les écarts de scores, de seuil et de réglages ; les formats dont la "
        "définition a divergé ; les formats et profils qui ne viennent pas de TRaSH. À appeler "
        "quand on demande si la configuration est conforme, à jour ou cohérente.",
        ManagerArgs,
        audit_trash_guides,
    ),
    Tool(
        "search_trash_guides",
        "Recherche dans les TRaSH Guides",
        "Cherche dans la copie locale des données TRaSH Guides (synchronisée depuis leur dépôt "
        "GitHub) : formats personnalisés avec leurs scores par jeu de scores, profils qualité "
        "recommandés avec leur description et leur lien, groupes de formats, schémas de "
        "nommage, tailles par qualité. C'est la référence chiffrée : à préférer à ta mémoire "
        "pour tout score ou réglage recommandé.",
        TrashSearchArgs,
        search_trash_guides,
    ),
    Tool(
        "get_download_queue",
        "File de téléchargement",
        "Téléchargements en cours vus par Radarr et Sonarr (état, état de suivi, message "
        "d'erreur ou raison d'un import en attente, client, indexeur) et état de SABnzbd "
        "(pause, vitesse, espace libre, file, échecs récents avec leur message). À appeler "
        "quand quelque chose est bloqué, lent ou n'arrive pas dans la médiathèque.",
        NoArgs,
        get_download_queue,
    ),
    Tool(
        "get_indexers",
        "Indexeurs Prowlarr",
        "Indexeurs de Prowlarr (protocole, activé ou non, messages d'état) et leurs "
        "statistiques : requêtes, récupérations, échecs, taux de succès, temps de réponse, "
        "liste des indexeurs peu fiables.",
        NoArgs,
        get_indexers,
    ),
    Tool(
        "get_docker_logs",
        "Journaux des conteneurs",
        "Messages récents des journaux Docker des services reliés, regroupés quand ils se "
        "répètent (avec le compte). Par défaut : erreurs et avertissements de tous les "
        "conteneurs. Filtres : conteneur, niveau, texte. À appeler pour comprendre une panne "
        "ou confirmer une hypothèse par ce que le service a réellement écrit.",
        DockerLogsArgs,
        get_docker_logs,
    ),
    Tool(
        "get_disk_space",
        "Espace disque",
        "Espace total et libre des disques vus par Radarr et Sonarr.",
        NoArgs,
        get_disk_space,
    ),
    Tool(
        "search_library",
        "Recherche dans la médiathèque",
        "Cherche des films et séries de la médiathèque par titre : fichier présent ou non, "
        "surveillé ou non, qualité, résolution, codec, HDR, audio, taille, dossier. Renvoie "
        "`external_id`, à passer à get_media_details. `only_missing` liste les titres "
        "surveillés sans fichier.",
        LibrarySearchArgs,
        search_library,
    ),
    Tool(
        "get_media_details",
        "Détail et historique d'un titre",
        "Détail d'un film (Radarr) ou d'une série (Sonarr) : profil, fichier actuel avec ses "
        "formats personnalisés et son score, seuil atteint ou non, saisons ; et son historique "
        "(releases récupérées, importées, échouées, supprimées, avec indexeur, score et raison). "
        "À appeler pour expliquer pourquoi un titre n'est pas téléchargé, reste bloqué, ou a "
        "été remplacé.",
        MediaDetailsArgs,
        get_media_details,
    ),
    Tool(
        "get_activity_log",
        "Journal d'activité d'ArrMada",
        "Journal persistant des actions d'ArrMada (demandes, téléchargements, imports, "
        "sous-titres, lectures, erreurs), du plus récent au plus ancien.",
        ActivityLogArgs,
        get_activity_log,
    ),
    Tool(
        "get_setup_checklist",
        "Vérification du câblage",
        "Vérifie, sur les vraies applications, que la chaîne est complète : indexeurs dans "
        "Prowlarr, fournisseur Usenet et catégories dans SABnzbd, client de téléchargement et "
        "dossier racine dans Radarr / Sonarr, bibliothèques Jellyfin, Bazarr. Chaque point est "
        "« done » ou « todo », avec la raison et la marche à suivre.",
        NoArgs,
        get_setup_checklist,
    ),
    Tool(
        "search_arrmada_docs",
        "Recherche dans la documentation d'ArrMada",
        "Cherche dans la documentation d'ArrMada : décisions d'architecture (ADR), journal des "
        "changements, README, guides d'installation. Renvoie les sections les plus proches, "
        "avec un extrait. À appeler pour toute question sur le fonctionnement d'ArrMada, la "
        "raison d'un choix, ou ce qui a changé récemment.",
        DocsSearchArgs,
        search_arrmada_docs,
    ),
    Tool(
        "read_arrmada_doc",
        "Lecture d'un document d'ArrMada",
        "Lit un document d'ArrMada (ou une de ses sections) trouvé par search_arrmada_docs.",
        DocsReadArgs,
        read_arrmada_doc,
    ),
)

_BY_NAME = {tool.name: tool for tool in TOOLS}

# Sites consultables par la recherche web : la documentation de référence de
# la stack, pas le web entier (réponses sourcées, moins de bruit, moins de risque).
WEB_DOMAINS = [
    "trash-guides.info",
    "wiki.servarr.com",
    "radarr.video",
    "sonarr.tv",
    "prowlarr.com",
    "lidarr.audio",
    "wiki.bazarr.media",
    "jellyfin.org",
    "sabnzbd.org",
    "docs.linuxserver.io",
    "docs.unraid.net",
    "recyclarr.dev",
    "github.com",
]

WEB_TOOL_LABELS = {
    "web_search": "Recherche web",
    "web_fetch": "Lecture d'une page web",
}


def _strip_titles(schema: Any, *, properties: bool = False) -> Any:
    """Retire les « title » que pydantic ajoute partout : du bruit pour le modèle.

    ``properties`` : on est dans la table des arguments, dont les clés sont des
    NOMS d'arguments (un argument peut s'appeler « title »), pas des mots-clés.
    """
    if isinstance(schema, dict):
        return {
            key: _strip_titles(value, properties=key == "properties" and not properties)
            for key, value in schema.items()
            if properties or key != "title"
        }
    if isinstance(schema, list):
        return [_strip_titles(item) for item in schema]
    return schema


def api_tools(*, web_search: bool) -> list[dict[str, Any]]:
    """Définitions envoyées à l'API. Liste STABLE : elle fait partie du préfixe mis en cache."""
    definitions: list[dict[str, Any]] = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": _strip_titles(tool.args.model_json_schema()),
            # Requête diffusée en continu : les arguments arrivent sans mise en
            # tampon côté API, donc sans validation ; `execute` les valide.
            "eager_input_streaming": True,
        }
        for tool in TOOLS
    ]
    if web_search:
        definitions += [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": 5,
                "allowed_domains": WEB_DOMAINS,
            },
            {
                "type": "web_fetch_20260209",
                "name": "web_fetch",
                "max_uses": 5,
                "allowed_domains": WEB_DOMAINS,
                "max_content_tokens": 20_000,
            },
        ]
    return definitions


def label_of(name: str) -> str:
    tool = resolve(name)
    return tool.label if tool else WEB_TOOL_LABELS.get(name, name)


def resolve(name: str) -> Tool | None:
    """Outil par son nom ; la casse est tolérée (le modèle écrit parfois « Get_Overview »)."""
    if name in _BY_NAME:
        return _BY_NAME[name]
    lowered = str(name).lower()
    matches = [tool for tool in TOOLS if tool.name.lower() == lowered]
    return matches[0] if len(matches) == 1 else None


# ══════════════════════════════════════════════════════════════
# Exécution
# ══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ToolOutcome:
    content: str  # ce que le modèle reçoit
    is_error: bool
    duration_ms: int


async def build_redactor() -> Redactor:
    """Masqueur chargé des secrets connus : clés des services et secrets du ``.env``."""
    secrets: set[str] = set()
    for svc in await _services(enabled_only=False):
        with contextlib.suppress(Exception):
            secrets.add(decrypt_api_key(svc.api_key))
    for name, value in settings.model_dump().items():
        if isinstance(value, str) and is_secret_name(name):
            secrets.add(value)
    credentials = re.search(r"://[^/\s:@]+:([^@\s/]+)@", settings.DATABASE_URL)
    if credentials:
        secrets.add(credentials.group(1))
    return Redactor(secrets)


def _serialise(result: Any, redactor: Redactor) -> str:
    text = json.dumps(redactor.data(result), ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        cut = len(text) - MAX_RESULT_CHARS
        text = (
            f"{text[:MAX_RESULT_CHARS]}\n[… résultat coupé : {cut} caractères de plus. "
            "Affine la demande (filtre, recherche, section) pour voir la suite.]"
        )
    return text


async def execute(name: str, raw_input: Any, redactor: Redactor) -> ToolOutcome:
    """Valide les arguments, exécute l'outil, renvoie un résultat sans secret et borné."""
    started = time.monotonic()

    def outcome(content: str, *, is_error: bool) -> ToolOutcome:
        return ToolOutcome(content, is_error, int((time.monotonic() - started) * 1000))

    tool = resolve(name)
    if tool is None:
        known = ", ".join(t.name for t in TOOLS)
        return outcome(f"Outil inconnu : {name!r}. Outils disponibles : {known}.", is_error=True)

    try:
        args = tool.args.model_validate(raw_input if raw_input is not None else {})
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'arguments'} : {err['msg']}"
            for err in exc.errors()
        )
        received = json.dumps(raw_input, ensure_ascii=False, default=str)[:500]
        return outcome(
            f"Arguments invalides pour {tool.name} ({problems}). Reçu : {received}", is_error=True
        )

    try:
        result = await asyncio.wait_for(tool.handler(args), timeout=TOOL_TIMEOUT_SECONDS)
    except TimeoutError:
        return outcome(
            f"{tool.name} n'a pas répondu en {TOOL_TIMEOUT_SECONDS} s (service lent ou injoignable).",
            is_error=True,
        )
    except Exception as exc:  # noqa: BLE001 : l'échec est renvoyé au modèle, qui s'adapte
        logger.warning("Copilote : outil %s en échec : %s", tool.name, exc)
        return outcome(redactor.text(f"{tool.name} a échoué : {_error(exc)}"), is_error=True)

    is_error = isinstance(result, dict) and set(result) == {"error"}
    return outcome(_serialise(result, redactor), is_error=is_error)

"""Outils du copilote (lecture) : vue d'ensemble, santé et configuration des *arr, TRaSH Guides."""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app import __version__
from app.models.service import Service
from app.services import health_checker, media_aggregator
from app.services.copilot.tools.args import (
    _CONFIG_ENDPOINTS,
    ArrConfigArgs,
    ArrHealthArgs,
    CustomFormatsArgs,
    ManagerArgs,
    NoArgs,
    TrashSearchArgs,
)
from app.services.copilot.tools.common import (
    _capped,
    _compact_provider,
    _cutoff_name,
    _error,
    _find,
    _matches,
    _per_service,
    _profile_summary,
    _spec_summary,
    _words,
    session_factory,
)
from app.utils.helpers import format_bytes
from app.utils.logger import get_logger

# Même journal que l'ancien fichier unique : mêmes lignes de log qu'avant.
logger = get_logger("app.services.copilot.tools")


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

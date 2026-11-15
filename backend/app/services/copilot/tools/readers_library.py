"""Outils du copilote (lecture) : bibliothèque, détail d'un média, journal d'activité, checklist, documentation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import activity_log, media_aggregator
from app.services.copilot import knowledge
from app.services.copilot.tools.args import (
    ActivityLogArgs,
    DocsReadArgs,
    DocsSearchArgs,
    LibrarySearchArgs,
    MediaDetailsArgs,
    NoArgs,
)
from app.services.copilot.tools.common import (
    _capped,
    _client,
    _matches,
    _services,
    _words,
    session_factory,
)
from app.utils.helpers import format_bytes

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

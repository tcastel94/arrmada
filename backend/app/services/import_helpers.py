"""Import helpers — build payloads and find candidates for ManualImport.

Extracted from media_mover.py following the Single Responsibility Principle.
"""

from __future__ import annotations

from typing import Any

from app.services.arr_client import ArrBaseClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def find_candidates(
    client: ArrBaseClient,
    folder: str,
    match_name: str,
) -> list[dict[str, Any]]:
    """Scan a folder via the manualimport endpoint and return matching items."""
    try:
        candidates = await client.get(
            "/manualimport",
            params={"folder": folder, "filterExistingFiles": "false"},
        )
    except Exception as exc:
        logger.warning("manualimport scan of %s failed: %s", folder, exc)
        return []

    if not isinstance(candidates, list):
        return []

    matched = []
    for item in candidates:
        item_name = (item.get("name") or item.get("folderName") or "").lower()
        item_path = (item.get("path") or "").lower()

        if match_name not in item_name and match_name not in item_path:
            continue

        # Skip permanent rejections (unknown series)
        rejections = item.get("rejections", [])
        if any(
            r.get("type") == "permanent" and "Unknown" in r.get("reason", "")
            for r in rejections
        ):
            logger.debug("Skipped %s — unknown series", item_name)
            continue

        matched.append(item)

    return matched


def _targets_already_have_files(item: dict[str, Any], service_type: str) -> bool:
    """True if importing this candidate would replace an existing file."""
    if service_type == "sonarr":
        episodes = item.get("episodes") or []
        # No target resolved → we cannot tell what it would replace.
        if not episodes:
            return True
        return any(
            ep.get("hasFile") or ep.get("episodeFileId")
            for ep in episodes
        )

    movie = item.get("movie")
    if not movie:
        return True
    return bool(movie.get("hasFile") or movie.get("movieFileId"))


def filter_safe_candidates(
    items: list[dict[str, Any]],
    service_type: str,
    allow_overwrite: bool = False,
) -> list[dict[str, Any]]:
    """Drop candidates that an unattended import must not touch.

    Two guards, in order of importance:

    1. *arr already told us it doesn't want the file — honour every
       rejection, not just "unknown series".  Overriding them is how a
       mis-parsed release gets imported over a good one.
    2. The destination already has a file.  A wrong parse (anime cour
       numbering is the classic case: "S03E03" of an arc mapping onto
       season 3 of the parent series) then destroys an unrelated
       episode.  Filling gaps is safe; replacing is not.

    ``allow_overwrite=True`` keeps guard 2 disabled for explicit,
    user-initiated imports where the user sees what they are doing.
    """
    safe = []
    for item in items:
        name = item.get("name") or item.get("relativePath") or item.get("path") or "?"

        rejections = item.get("rejections") or []
        if rejections:
            reasons = [r.get("reason", "?") for r in rejections]
            logger.info("Skipped %s — rejected by *arr: %s", name, reasons)
            continue

        if not allow_overwrite and _targets_already_have_files(item, service_type):
            logger.warning(
                "Skipped %s — destination already has a file (refusing to "
                "overwrite from an unattended import)", name,
            )
            continue

        safe.append(item)

    return safe


def build_import_payload(
    items: list[dict[str, Any]],
    service_type: str,
) -> list[dict[str, Any]]:
    """Build the files list for a ManualImport command."""
    files = []
    for item in items:
        entry: dict[str, Any] = {
            "path": item["path"],
            "folderName": item.get("folderName", ""),
            "quality": item.get("quality", {}),
            "languages": item.get("languages", []),
            "releaseGroup": item.get("releaseGroup", ""),
            "indexerFlags": item.get("indexerFlags", 0),
        }
        if service_type == "sonarr":
            series = item.get("series")
            if series:
                entry["seriesId"] = series["id"]
            entry["seasonNumber"] = item.get("seasonNumber")
            episodes = item.get("episodes", [])
            entry["episodeIds"] = [ep["id"] for ep in episodes]
            entry["releaseType"] = item.get("releaseType", "singleEpisode")
        else:
            movie = item.get("movie")
            if movie:
                entry["movieId"] = movie["id"]
        files.append(entry)
    return files


async def trigger_rename(
    client: ArrBaseClient,
    items: list[dict[str, Any]],
    service_type: str,
) -> None:
    """Trigger a rename command for the imported files."""
    try:
        if service_type == "sonarr":
            series_ids = set()
            for item in items:
                series = item.get("series")
                if series:
                    series_ids.add(series["id"])

            for sid in series_ids:
                await client.post("/command", data={
                    "name": "RenameSeries",
                    "seriesId": sid,
                })
                logger.info("Triggered RenameSeries for series %d", sid)
        else:
            movie_ids = set()
            for item in items:
                movie = item.get("movie")
                if movie:
                    movie_ids.add(movie["id"])

            for mid in movie_ids:
                await client.post("/command", data={
                    "name": "RenameMovie",
                    "movieId": mid,
                })
                logger.info("Triggered RenameMovie for movie %d", mid)
    except Exception as exc:
        logger.warning("Rename trigger failed: %s", exc)

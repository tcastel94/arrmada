"""Media file mover — relocate stuck downloads to proper media folders on the NAS.

Uses Unraid GraphQL API to understand volume mappings, then uses the Radarr/Sonarr
API to trigger a manual import (which moves and renames files properly).

Refactored: path mapping is in path_mapper.py, import helpers in import_helpers.py.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.import_helpers import build_import_payload, find_candidates, trigger_rename
from app.services.path_mapper import get_path_mappings  # noqa: F401 — re-export
from app.services.radarr import RadarrClient
from app.services.sonarr import SonarrClient
from app.services.sabnzbd import SabnzbdClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Words stripped from titles by Sonarr/Radarr's cleanTitle algorithm
_ARTICLES = frozenset({
    "of", "the", "and", "a", "an", "in", "on", "at", "to", "for",
    "le", "la", "les", "de", "du", "des",
})


# get_path_mappings is now imported from path_mapper.py and re-exported


async def get_stuck_downloads(db: AsyncSession) -> list[dict[str, Any]]:
    """Find SABnzbd downloads that are completed but NOT yet imported.

    Cross-references SABnzbd history with:
    1. Radarr movies library (hasFile check + path matching)
    2. Sonarr episode files (episodeFile check)
    3. Radarr/Sonarr import history (sourceTitle matching)

    Only returns downloads that are genuinely orphaned — NOT already
    present in the media library.
    """
    # ── 1. Get SABnzbd history ────────────────────────────────
    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == "sabnzbd",
    )
    result = await db.execute(stmt)
    sab_service = result.scalars().first()

    if not sab_service:
        return []

    api_key = decrypt_api_key(sab_service.api_key)
    sab = SabnzbdClient(url=sab_service.url, api_key=api_key)

    try:
        history = await sab.get_history(limit=200)
    finally:
        await sab.close()

    slots = history.get("slots", [])

    # Only keep completed downloads
    completed = []
    for slot in slots:
        if slot.get("status") != "Completed":
            continue
        completed.append(slot)

    if not completed:
        return []

    # ── 2. Build Radarr "already imported" set ────────────────
    radarr_imported: set[str] = set()  # lowercase clean names of imported media

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "radarr")  # noqa: E712
    result = await db.execute(stmt)
    radarr_service = result.scalars().first()

    if radarr_service:
        rk = decrypt_api_key(radarr_service.api_key)
        radarr = RadarrClient(url=radarr_service.url, api_key=rk)
        try:
            # Get all movies — those with hasFile are already imported
            movies = await radarr.get_movies()
            for m in movies:
                if m.get("hasFile"):
                    # Add the movie title (cleanTitle is used in folder names)
                    title = m.get("title", "")
                    clean = m.get("cleanTitle", "")
                    folder = (m.get("folderName") or "").rsplit("/", 1)[-1]
                    path = (m.get("path") or "").rsplit("/", 1)[-1]

                    if title:
                        radarr_imported.add(title.lower())
                    if clean:
                        radarr_imported.add(clean.lower())
                    if folder:
                        radarr_imported.add(folder.lower())
                    if path:
                        radarr_imported.add(path.lower())

            # Also get Radarr's import history — sourceTitle matches NZB names
            try:
                hist = await radarr.get("/history", params={"pageSize": 500, "sortKey": "date", "sortDirection": "descending"})
                for record in hist.get("records", []):
                    if record.get("eventType") in ("downloadFolderImported", "grabbed"):
                        source = record.get("sourceTitle", "")
                        if source:
                            radarr_imported.add(source.lower())
            except Exception as exc:
                logger.debug("Could not fetch Radarr history: %s", exc)

        finally:
            await radarr.close()

    # ── 3. Build Sonarr "already imported" set ────────────────
    sonarr_imported: set[str] = set()

    stmt = select(Service).where(Service.is_enabled == True, Service.type == "sonarr")  # noqa: E712
    result = await db.execute(stmt)
    sonarr_service = result.scalars().first()

    if sonarr_service:
        sk = decrypt_api_key(sonarr_service.api_key)
        sonarr = SonarrClient(url=sonarr_service.url, api_key=sk)
        try:
            # Get Sonarr import history
            try:
                hist = await sonarr.get("/history", params={"pageSize": 500, "sortKey": "date", "sortDirection": "descending"})
                for record in hist.get("records", []):
                    if record.get("eventType") in ("downloadFolderImported", "grabbed"):
                        source = record.get("sourceTitle", "")
                        if source:
                            sonarr_imported.add(source.lower())
            except Exception as exc:
                logger.debug("Could not fetch Sonarr history: %s", exc)

            # Get all series and their episode files — files that are already
            # in the library (even if imported via DownloadedEpisodesScan)
            try:
                series_list = await sonarr.get("/series")

                # Collect download name prefixes for targeted matching
                # Must strip articles to match Sonarr's cleanTitle format
                download_prefixes = set()
                for slot in completed:
                    sn = slot.get("name", "").lower()
                    # Extract title prefix before season marker
                    parts = re.split(r"\.s\d{2}", sn, flags=re.IGNORECASE)
                    if parts:
                        words = [w for w in parts[0].split(".") if w not in _ARTICLES]
                        prefix = "".join(words).lower()
                        download_prefixes.add(prefix)

                for s in series_list:
                    sid = s.get("id")
                    title = s.get("title", "")
                    clean = s.get("cleanTitle", "")
                    if title:
                        sonarr_imported.add(title.lower())
                    if clean:
                        sonarr_imported.add(clean.lower())

                    # Only fetch episode files for series that MIGHT match
                    # a download name (avoid N+1 API calls)
                    clean_stripped = "".join(
                        w for w in clean.split() if w not in _ARTICLES
                    ).lower() if clean else ""
                    title_stripped = "".join(
                        w for w in title.lower().replace(" ", ".").split(".")
                        if w not in _ARTICLES
                    ).lower() if title else ""

                    is_relevant = any(
                        clean_stripped in p or title_stripped in p
                        or p in clean_stripped or p in title_stripped
                        for p in download_prefixes
                    )
                    if not is_relevant:
                        continue

                    try:
                        ep_files = await sonarr.get("/episodefile", params={"seriesId": sid})
                        if isinstance(ep_files, list):
                            for ef in ep_files:
                                rel_path = ef.get("relativePath", "")
                                # e.g. "Godfather.of.Harlem.S03E01.1080p.x265-ELiTE/file.mkv"
                                folder_part = rel_path.split("/")[0] if "/" in rel_path else ""
                                if folder_part and not folder_part.lower().startswith("season"):
                                    sonarr_imported.add(folder_part.lower())
                                # Also add the filename minus extension
                                filename = rel_path.rsplit("/", 1)[-1]
                                if filename:
                                    name_no_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
                                    sonarr_imported.add(name_no_ext.lower())
                    except Exception:
                        pass
            except Exception as exc:
                logger.debug("Could not fetch Sonarr series/files: %s", exc)

        finally:
            await sonarr.close()

    # ── 4. Merge all imported names for quick lookup ──────────
    all_imported = radarr_imported | sonarr_imported
    logger.info(
        "Duplicate check: %d Radarr imported, %d Sonarr imported, %d total known",
        len(radarr_imported), len(sonarr_imported), len(all_imported),
    )

    # ── 5. Filter: only truly stuck downloads ─────────────────
    stuck = []
    for slot in completed:
        name = slot.get("name", "")
        name_lower = name.lower()
        category = (slot.get("category") or "*").lower()
        storage = slot.get("storage", "")
        path = slot.get("path", "")
        final_path = storage or path

        # Must be in downloads folder
        is_in_downloads = "/downloads" in final_path.lower() or "/data" in final_path.lower()
        if not is_in_downloads:
            continue

        # ── DUPLICATE CHECK ──
        # Check if this exact download name is in import history
        if name_lower in all_imported:
            continue

        # Check if any imported title/folder appears in this download name
        # e.g. "fightclub" appears in "Fight.Club.1999.BluRay..."
        already_exists = False
        for imported_name in all_imported:
            # Skip very short names to avoid false positives
            if len(imported_name) < 4:
                continue
            # Check bidirectional: imported name in download, or download contains imported
            if imported_name in name_lower or name_lower in imported_name:
                already_exists = True
                break

        if already_exists:
            continue

        # Determine type based on category
        media_type = "unknown"
        if category in ("radarr", "movies", "films"):
            media_type = "movie"
        elif category in ("sonarr", "tv", "series"):
            media_type = "series"

        stuck.append({
            "nzo_id": slot.get("nzo_id", ""),
            "name": name,
            "category": category,
            "media_type": media_type,
            "size_human": slot.get("size", "0 B"),
            "storage_path": final_path,
            "completed": slot.get("completed"),
        })

    logger.info(
        "Stuck downloads: %d completed, %d truly orphaned after duplicate check",
        len(completed), len(stuck),
    )
    return stuck


async def trigger_manual_import(
    db: AsyncSession,
    download_path: str,
    media_type: str,
) -> dict[str, Any]:
    """Import a stuck download into the media library.

    Strategy (3-phase):
    ───────────────────────────────────────────────────────────
    Phase 1 — ManualImport from /data
        Scan the download folder (/data, /data/sonarr, etc.) and
        find matching files.  Tell Sonarr/Radarr to move+rename
        them into the library using importMode=move.

    Phase 2 — ManualImport from the series/movie folder
        If Phase 1 fails (files may already have been moved into
        the library but NOT renamed/organized), scan the
        library folder and import from there.

    Phase 3 — Rename
        After a successful import, trigger Sonarr's
        RenameSeries / Radarr's RenameMovie so files land in the
        correct Season X subfolder with proper naming.
    """
    target_service = "radarr" if media_type == "movie" else "sonarr"

    stmt = select(Service).where(
        Service.is_enabled == True,  # noqa: E712
        Service.type == target_service,
    )
    result = await db.execute(stmt)
    service = result.scalars().first()

    if not service:
        return {"success": False, "error": f"No {target_service} service configured"}

    api_key = decrypt_api_key(service.api_key)

    if target_service == "radarr":
        client = RadarrClient(url=service.url, api_key=api_key, timeout=60)
    else:
        client = SonarrClient(url=service.url, api_key=api_key, timeout=60)

    try:
        # ── Build a match_name from the download path ────────
        path_parts = download_path.rstrip("/").split("/")
        match_name = ""
        scan_folder = "/data"

        for i, part in enumerate(path_parts):
            if part in ("sonarr", "radarr", "data", "complete"):
                if i + 1 < len(path_parts):
                    match_name = path_parts[i + 1].lower()
                    scan_folder = "/".join(path_parts[: i + 1])
                    break

        if not match_name:
            match_name = path_parts[-1].lower() if path_parts[-1] else path_parts[-2].lower()

        # Remove file extension for matching
        if "." in match_name and match_name.rsplit(".", 1)[-1] in ("mkv", "mp4", "avi", "srt", "nfo"):
            match_name = match_name.rsplit(".", 1)[0]

        logger.info(
            "Manual import [%s]: match_name='%s' scan_folder='%s'",
            target_service, match_name, scan_folder,
        )

        # ── PHASE 1: ManualImport from /data ─────────────────
        matched = await find_candidates(client, scan_folder, match_name)
        if not matched and scan_folder != "/data":
            matched = await find_candidates(client, "/data", match_name)

        if matched:
            files_payload = build_import_payload(matched, target_service)
            command = await client.post("/command", data={
                "name": "ManualImport",
                "files": files_payload,
                "importMode": "move",
            })
            logger.info(
                "Phase 1 OK: ManualImport of %d file(s) from /data",
                len(files_payload),
            )

            # Phase 3: trigger rename after import
            await trigger_rename(client, matched, target_service)

            return {
                "success": True,
                "service": target_service,
                "command_id": command.get("id"),
                "files_count": len(files_payload),
                "message": (
                    f"{len(files_payload)} fichier(s) importé(s) et renommage lancé"
                ),
            }

        # ── PHASE 2: Check in the library folder ─────────────
        logger.info("Phase 1 empty — trying library scan for '%s'", match_name)

        # Look up the series/movie in the *arr database to get the library path
        if target_service == "sonarr":
            series_list = await client.get("/series")
            library_path = None
            series_id = None

            # Find the series by matching the download name
            # Strip season/episode + quality from name to get just the title
            # "godfather.of.harlem.s03e01.1080p..." → "godfather.of.harlem"
            title_part = re.split(r"\.s\d{2}", match_name, flags=re.IGNORECASE)[0]
            # Normalize: remove dots and common articles (Sonarr strips these)
            download_words = [w for w in title_part.split(".") if w.lower() not in _ARTICLES]
            download_clean = "".join(download_words).lower()

            for s in series_list:
                clean = s.get("cleanTitle", "").lower()
                # Also try matching with articles stripped from both sides
                if download_clean in clean or clean in download_clean:
                    library_path = s.get("path")
                    series_id = s.get("id")
                    logger.info("Matched series: %s (id=%d, path=%s)", s.get("title"), series_id, library_path)
                    break

            if library_path and series_id:
                # ── PRIORITY 1: Check if files need renaming ─────
                # Files already tracked by Sonarr won't move with
                # ManualImport. The ONLY way to reorganize them into
                # Season X/ folders is via the Rename API.
                logger.info(
                    "Phase 2: checking rename for seriesId=%d ('%s')",
                    series_id, match_name,
                )
                renames = await client.get("/rename", params={"seriesId": series_id})
                if isinstance(renames, list) and renames:
                    matching_renames = [
                        r for r in renames
                        if match_name in (r.get("existingPath") or "").lower()
                    ]
                    if matching_renames:
                        file_ids = [r.get("episodeFileId") for r in matching_renames]
                        logger.info(
                            "Phase 2 (rename): %d file(s) to rename for series %d: %s",
                            len(file_ids), series_id,
                            [(r.get("existingPath"), r.get("newPath")) for r in matching_renames],
                        )
                        command = await client.post("/command", data={
                            "name": "RenameSeries",
                            "seriesId": series_id,
                            "files": file_ids,
                        })
                        return {
                            "success": True,
                            "service": target_service,
                            "command_id": command.get("id"),
                            "files_count": len(file_ids),
                            "message": (
                                f"{len(file_ids)} fichier(s) déjà importé(s) — "
                                f"renommage et déplacement vers Season X lancé"
                            ),
                        }

                # ── PRIORITY 2: ManualImport from library folder ──
                # Only for files NOT yet tracked by Sonarr (no rename
                # suggestion = file not in Sonarr's episode database).
                logger.info(
                    "Phase 2: no rename found, scanning library folder %s",
                    library_path,
                )
                candidates = await client.get(
                    "/manualimport",
                    params={
                        "folder": library_path,
                        "filterExistingFiles": "false",
                        "seriesId": series_id,
                    },
                )
                if isinstance(candidates, list):
                    logger.info(
                        "Phase 2: got %d candidates from library scan",
                        len(candidates),
                    )
                    matched_lib = []
                    for c in candidates:
                        c_path = (c.get("path") or "").lower()
                        if match_name in c_path:
                            rejections = c.get("rejections", [])
                            permanent = any(
                                r.get("type") == "permanent"
                                for r in rejections
                            )
                            if not permanent:
                                matched_lib.append(c)
                                logger.info(
                                    "Phase 2: matched candidate %s", c_path,
                                )

                    if matched_lib:
                        files_payload = build_import_payload(
                            matched_lib, target_service,
                        )
                        command = await client.post("/command", data={
                            "name": "ManualImport",
                            "files": files_payload,
                            "importMode": "move",
                        })
                        logger.info(
                            "Phase 2 OK: ManualImport of %d file(s) from library",
                            len(files_payload),
                        )
                        return {
                            "success": True,
                            "service": target_service,
                            "command_id": command.get("id"),
                            "files_count": len(files_payload),
                            "message": (
                                f"{len(files_payload)} fichier(s) importé(s) "
                                f"depuis la bibliothèque"
                            ),
                        }

        elif target_service == "radarr":
            movies = await client.get("/movie")
            # Reuse the same article-stripping logic
            title_part_r = re.split(r"\.\d{4}\.", match_name)[0]  # strip year and after
            download_words_r = [w for w in title_part_r.split(".") if w.lower() not in _ARTICLES]
            download_key = "".join(download_words_r).lower()
            for m in movies:
                clean = (m.get("cleanTitle") or "").lower()
                if download_key in clean or clean in download_key:
                    movie_id = m.get("id")
                    # Trigger rename
                    command = await client.post("/command", data={
                        "name": "RenameMovie",
                        "movieId": movie_id,
                    })
                    return {
                        "success": True,
                        "service": "radarr",
                        "command_id": command.get("id"),
                        "files_count": 1,
                        "message": "Renommage du film lancé",
                    }

        return {
            "success": False,
            "error": (
                f"Fichier non trouvé ni dans /data ni dans la bibliothèque {target_service}. "
                f"Vérifiez que la série/film existe dans {target_service}."
            ),
        }

    except Exception as exc:
        logger.error("Manual import failed for %s: %s", download_path, exc)
        return {"success": False, "error": str(exc)}

    finally:
        await client.close()


# _find_candidates, _build_import_payload, and _trigger_rename
# have been extracted to import_helpers.py



"""Background task to automatically import stuck completed downloads."""

from __future__ import annotations

import re
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import async_session_factory
from app.services.auto_import_reports import add_report
from app.services.media_mover import get_stuck_downloads, trigger_manual_import
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Downloads deliberately skipped (unsafe to import unattended) stay
# "stuck" forever, so without a memory the job would re-scan and re-log
# them every cycle.  Remember them for a while, but do re-check
# eventually: the library changes, and what is unsafe today (destination
# occupied) can become a legitimate gap tomorrow.
_SKIP_BACKOFF_SECONDS = 6 * 3600
_skipped_until: dict[str, float] = {}


def _is_backed_off(storage_path: str) -> bool:
    until = _skipped_until.get(storage_path)
    if until is None:
        return False
    if time.monotonic() >= until:
        del _skipped_until[storage_path]
        return False
    return True


def detect_media_type(name: str) -> str:
    """Guess whether a release name is a series or movie."""
    name_lower = name.lower()
    # Patterns suggesting a series: S01E02, S01, Season 1, etc.
    series_patterns = [
        r"\bs\d{1,2}e\d{1,3}\b",
        r"\bs\d{1,2}\b",
        r"\bseason\s*\d+\b",
        r"\bepisodes?\s*\d+\b",
        r"\bep\b\d+",
        r"\bs\d{2}\.e\d{2}\b",
    ]
    for pattern in series_patterns:
        if re.search(pattern, name_lower):
            return "series"
    return "movie"


async def auto_import_job() -> None:
    """Periodically scan for stuck downloads, import them and save a report."""
    logger.info("Starting scheduled auto-import scan...")
    start_time = time.monotonic()

    scanned_count = 0
    imported_count = 0
    failed_count = 0
    skipped_count = 0
    items_report = []

    async with async_session_factory() as db:
        try:
            stuck_items = await get_stuck_downloads(db)
            scanned_count = len(stuck_items)

            if stuck_items:
                logger.info("Found %d stuck download(s). Starting auto-import...", scanned_count)
                for item in stuck_items:
                    storage_path = item.get("storage_path")
                    name = item.get("name", "")
                    media_type = item.get("media_type")

                    if not storage_path:
                        continue

                    if _is_backed_off(storage_path):
                        skipped_count += 1
                        logger.debug(
                            "Skipping '%s' — already judged unsafe, next retry later",
                            name,
                        )
                        continue

                    if media_type == "unknown":
                        media_type = detect_media_type(name)
                        logger.info("Detected media type for '%s': %s", name, media_type)

                    try:
                        logger.info(
                            "Auto-importing '%s' (%s) from path '%s'",
                            name,
                            media_type,
                            storage_path,
                        )
                        res = await trigger_manual_import(
                            db,
                            storage_path,
                            media_type,
                            allow_overwrite=settings.AUTO_IMPORT_ALLOW_OVERWRITE,
                        )

                        if res.get("success"):
                            imported_count += 1
                            items_report.append(
                                {
                                    "name": name,
                                    "storage_path": storage_path,
                                    "media_type": media_type,
                                    "status": "success",
                                    "message": res.get("message", "Importé avec succès"),
                                }
                            )
                            logger.info("Successfully auto-imported '%s'", name)
                            _skipped_until.pop(storage_path, None)
                        elif res.get("skipped"):
                            skipped_count += 1
                            _skipped_until[storage_path] = time.monotonic() + _SKIP_BACKOFF_SECONDS
                            items_report.append(
                                {
                                    "name": name,
                                    "storage_path": storage_path,
                                    "media_type": media_type,
                                    "status": "skipped",
                                    "message": res.get("error", "Écarté par sécurité"),
                                }
                            )
                            logger.info(
                                "Skipped '%s' — %s (pas de nouvelle tentative avant %dh)",
                                name,
                                res.get("error"),
                                _SKIP_BACKOFF_SECONDS // 3600,
                            )
                        else:
                            failed_count += 1
                            items_report.append(
                                {
                                    "name": name,
                                    "storage_path": storage_path,
                                    "media_type": media_type,
                                    "status": "failed",
                                    "message": res.get("error", "Erreur lors de l'import"),
                                }
                            )
                            logger.warning("Failed to auto-import '%s': %s", name, res.get("error"))
                    except Exception as exc:
                        failed_count += 1
                        items_report.append(
                            {
                                "name": name,
                                "storage_path": storage_path,
                                "media_type": media_type,
                                "status": "failed",
                                "message": str(exc),
                            }
                        )
                        logger.error("Error auto-importing '%s': %s", name, exc)
            else:
                logger.info("No stuck downloads found.")

        except Exception as exc:
            logger.error("Auto-import task failed during scanning: %s", exc)

        # Packs de saison bloqués dans la file de Sonarr (torrents surtout) :
        # « 01. Titre.mkv » sans S01E01 → import manuel quand c'est sûr
        if settings.AUTO_IMPORT_BLOCKED_PACKS:
            try:
                from app.services.blocked_imports import resolve_blocked_packs

                packs = await resolve_blocked_packs(
                    db, allow_overwrite=settings.AUTO_IMPORT_ALLOW_OVERWRITE
                )
                scanned_count += len(packs)
                imported_count += sum(1 for p in packs if p["status"] == "success")
                skipped_count += sum(1 for p in packs if p["status"] == "skipped")
                failed_count += sum(1 for p in packs if p["status"] == "failed")
                items_report.extend(packs)
            except Exception as exc:
                logger.error("Auto-import des packs bloqués impossible : %s", exc)

    duration = time.monotonic() - start_time

    # Save the execution report (even if empty, to show the task ran!)
    try:
        add_report(
            duration_seconds=duration,
            scanned_count=scanned_count,
            imported_count=imported_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            items=items_report,
        )
    except Exception as exc:
        logger.error("Failed to write auto-import report: %s", exc)


def register(scheduler: AsyncIOScheduler) -> None:
    """Register the auto-import job with the scheduler."""
    if not settings.AUTO_IMPORT_ENABLED:
        logger.info("auto_import_downloads job NOT registered (AUTO_IMPORT_ENABLED=false)")
        return

    minutes = max(1, settings.AUTO_IMPORT_INTERVAL_MINUTES)
    scheduler.add_job(
        auto_import_job,
        trigger="interval",
        minutes=minutes,
        id="auto_import_downloads",
        name="Auto-import completed downloads",
        replace_existing=True,
    )
    logger.info(
        "Registered auto_import_downloads job (every %d minutes, overwrite=%s)",
        minutes,
        settings.AUTO_IMPORT_ALLOW_OVERWRITE,
    )

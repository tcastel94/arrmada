"""Auto-import execution reports manager."""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

REPORTS_FILE = "/app/data/auto_import_reports.json"


def get_reports() -> list[dict[str, Any]]:
    """Retrieve the latest auto-import reports."""
    if not os.path.exists(REPORTS_FILE):
        return []
    try:
        with open(REPORTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except Exception as exc:
        logger.error("Failed to load auto-import reports: %s", exc)
        return []


def add_report(
    duration_seconds: float,
    scanned_count: int,
    imported_count: int,
    failed_count: int,
    items: list[dict[str, Any]],
) -> None:
    """Save a new execution report, keeping only the 10 most recent ones."""
    reports = get_reports()
    
    # Create new report
    new_report = {
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": round(duration_seconds, 2),
        "scanned_count": scanned_count,
        "imported_count": imported_count,
        "failed_count": failed_count,
        "items": items,
    }
    
    reports.append(new_report)
    
    # Keep only last 10
    reports = reports[-10:]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(REPORTS_FILE), exist_ok=True)
    
    try:
        with open(REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.error("Failed to save auto-import report: %s", exc)

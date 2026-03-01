"""Utility / helper functions."""

from __future__ import annotations

import re
import unicodedata


def normalize_title(title: str) -> str:
    """Normalize a media title for duplicate comparison.

    - Lowercase
    - Strip diacritics
    - Remove non-alphanumeric (except spaces)
    - Collapse whitespace
    """
    # NFD decomposition → strip combining chars
    nfkd = unicodedata.normalize("NFKD", title)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", "", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def format_bytes(size_bytes: int | None) -> str:
    """Human-readable file size."""
    if size_bytes is None or size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    size = float(size_bytes)
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.1f} {units[idx]}"


def format_duration_ms(ms: int | None) -> str:
    """Format milliseconds to human-readable duration."""
    if ms is None:
        return "N/A"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"

"""TRaSH Guides data fetcher and cache manager.

Fetches Custom Format and Quality Profile JSON data from the
TRaSH-Guides GitHub repository. Results are cached locally on disk
with a configurable TTL (default 24 hours).
"""

import json
import time
from pathlib import Path
from typing import Any, Optional

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/TRaSH-Guides/Guides/master"
GITHUB_API_BASE = "https://api.github.com/repos/TRaSH-Guides/Guides/contents"

CACHE_DIR = Path("data/trash_cache")
CACHE_TTL_HOURS = 24

# Directories to fetch from the TRaSH Guides repo
FETCH_DIRS = {
    "sonarr_cf": "docs/json/sonarr/cf",
    "sonarr_qp": "docs/json/sonarr/quality-profiles",
    "sonarr_qs": "docs/json/sonarr/quality-size",
    "sonarr_naming": "docs/json/sonarr/naming",
    "radarr_cf": "docs/json/radarr/cf",
    "radarr_qp": "docs/json/radarr/quality-profiles",
    "radarr_qs": "docs/json/radarr/quality-size",
}


class TrashGuidesCache:
    """Manages fetching and caching of TRaSH Guides data."""

    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_hours: float = CACHE_TTL_HOURS):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self._data: dict[str, list[dict[str, Any]]] = {}
        self._last_sync: Optional[float] = None

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Try to load from disk cache on init
        self._load_from_disk()

    # ── Public API ────────────────────────────────────────────

    async def sync(self, force: bool = False) -> dict[str, int]:
        """Fetch all TRaSH Guides data from GitHub.

        Args:
            force: If True, ignore cache TTL and re-fetch.

        Returns:
            Dict with category → count of fetched items.
        """
        if not force and not self.is_stale:
            logger.info("TRaSH cache is fresh (%.1fh old), skipping sync", self.cache_age_hours)
            return {k: len(v) for k, v in self._data.items()}

        logger.info("Syncing TRaSH Guides data from GitHub...")
        results: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=30) as client:
            for category, path in FETCH_DIRS.items():
                try:
                    items = await self._fetch_directory(client, category, path)
                    self._data[category] = items
                    results[category] = len(items)
                    logger.info("  %s: %d items fetched", category, len(items))
                except Exception as e:
                    logger.error("  %s: fetch failed — %s", category, e)
                    results[category] = 0

        self._last_sync = time.time()
        self._save_to_disk()

        logger.info("TRaSH Guides sync complete: %s", results)
        return results

    def get_custom_formats(self, service: str = "sonarr") -> list[dict[str, Any]]:
        """Get all Custom Formats for a service."""
        key = f"{service}_cf"
        return self._data.get(key, [])

    def get_quality_profiles(self, service: str = "sonarr") -> list[dict[str, Any]]:
        """Get all Quality Profiles for a service."""
        key = f"{service}_qp"
        return self._data.get(key, [])

    def get_quality_sizes(self, service: str = "sonarr") -> list[dict[str, Any]]:
        """Get Quality Size definitions for a service."""
        key = f"{service}_qs"
        return self._data.get(key, [])

    def get_cf_by_id(self, trash_id: str, service: str = "sonarr") -> Optional[dict[str, Any]]:
        """Find a Custom Format by its trash_id."""
        for cf in self.get_custom_formats(service):
            if cf.get("trash_id") == trash_id:
                return cf
        return None

    def get_cf_by_name(self, name: str, service: str = "sonarr") -> Optional[dict[str, Any]]:
        """Find a Custom Format by name (case-insensitive)."""
        name_lower = name.lower()
        for cf in self.get_custom_formats(service):
            if cf.get("name", "").lower() == name_lower:
                return cf
        return None

    def search_cfs(self, query: str, service: str = "sonarr") -> list[dict[str, Any]]:
        """Search Custom Formats by name substring."""
        query_lower = query.lower()
        return [
            cf for cf in self.get_custom_formats(service)
            if query_lower in cf.get("name", "").lower()
        ]

    @property
    def is_stale(self) -> bool:
        """Whether the cache needs refreshing."""
        if self._last_sync is None:
            return True
        return (time.time() - self._last_sync) > self.ttl_seconds

    @property
    def cache_age_hours(self) -> Optional[float]:
        """Age of cache in hours, or None if never synced."""
        if self._last_sync is None:
            return None
        return (time.time() - self._last_sync) / 3600

    @property
    def status(self) -> dict[str, Any]:
        """Current cache status summary."""
        return {
            "last_sync": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._last_sync)
            ) if self._last_sync else None,
            "sonarr_cf_count": len(self._data.get("sonarr_cf", [])),
            "radarr_cf_count": len(self._data.get("radarr_cf", [])),
            "sonarr_qp_count": len(self._data.get("sonarr_qp", [])),
            "radarr_qp_count": len(self._data.get("radarr_qp", [])),
            "cache_age_hours": round(self.cache_age_hours, 1) if self.cache_age_hours else None,
            "is_stale": self.is_stale,
        }

    # ── Private helpers ───────────────────────────────────────

    async def _fetch_directory(
        self,
        client: httpx.AsyncClient,
        category: str,
        github_path: str,
    ) -> list[dict[str, Any]]:
        """Fetch all JSON files from a GitHub directory."""
        # List files in directory via GitHub API
        resp = await client.get(f"{GITHUB_API_BASE}/{github_path}")
        resp.raise_for_status()
        files = resp.json()

        items: list[dict[str, Any]] = []
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            if file_info.get("type") != "file":
                continue
            name = file_info.get("name", "")
            if not name.endswith(".json"):
                continue

            download_url = file_info.get("download_url")
            if not download_url:
                continue

            try:
                content_resp = await client.get(download_url)
                content_resp.raise_for_status()
                data = content_resp.json()

                # Add source metadata
                data["_source_file"] = name
                data["_category"] = category

                items.append(data)
            except Exception as e:
                logger.warning("Failed to fetch %s: %s", name, e)

        return items

    def _save_to_disk(self) -> None:
        """Persist cached data to disk."""
        try:
            cache_file = self.cache_dir / "trash_data.json"
            payload = {
                "last_sync": self._last_sync,
                "data": self._data,
            }
            cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.debug("TRaSH cache saved to %s", cache_file)
        except Exception as e:
            logger.error("Failed to save TRaSH cache: %s", e)

    def _load_from_disk(self) -> None:
        """Load cached data from disk if available."""
        cache_file = self.cache_dir / "trash_data.json"
        if not cache_file.exists():
            return

        try:
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            self._last_sync = payload.get("last_sync")
            self._data = payload.get("data", {})
            logger.info(
                "TRaSH cache loaded from disk (%.1fh old)",
                self.cache_age_hours or 0,
            )
        except Exception as e:
            logger.warning("Failed to load TRaSH cache from disk: %s", e)


# ── Singleton instance ────────────────────────────────────────
_cache: Optional[TrashGuidesCache] = None


def get_trash_cache() -> TrashGuidesCache:
    """Get or create the global TRaSH Guides cache instance."""
    global _cache
    if _cache is None:
        _cache = TrashGuidesCache()
    return _cache

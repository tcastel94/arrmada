"""In-memory TTL cache with pattern-based invalidation and event bus.

Provides:
- Per-key TTL caching with async-safe access
- Wildcard invalidation (e.g. invalidate_pattern("media:*"))
- Integration with the SSE event bus for real-time push
"""

from __future__ import annotations

import asyncio
import fnmatch
import time
from typing import Any, Callable, Coroutine

from app.utils.logger import get_logger

logger = get_logger(__name__)


class TTLCache:
    """Async-aware in-memory cache with per-key TTL and pattern invalidation."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Coroutine[Any, Any, Any]],
        ttl_seconds: int = 60,
    ) -> Any:
        """Return cached value or call *factory* to compute and cache it."""
        now = time.monotonic()

        # Fast path: check without lock
        cached = self._store.get(key)
        if cached and (now - cached[0]) < ttl_seconds:
            return cached[1]

        async with self._lock:
            # Double-check after acquiring lock
            cached = self._store.get(key)
            if cached and (now - cached[0]) < ttl_seconds:
                return cached[1]

            value = await factory()
            self._store[key] = (now, value)
            return value

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        """Remove all keys matching a glob pattern (e.g. 'media:*').

        Returns the number of keys invalidated.
        """
        keys_to_remove = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_remove:
            del self._store[k]
        if keys_to_remove:
            logger.debug("Cache invalidated %d keys matching '%s'", len(keys_to_remove), pattern)
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear the entire cache."""
        self._store.clear()

    @property
    def size(self) -> int:
        """Number of entries in the cache."""
        return len(self._store)

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        now = time.monotonic()
        return {
            "entries": len(self._store),
            "keys": list(self._store.keys()),
            "oldest_age_seconds": round(now - min((v[0] for v in self._store.values()), default=now), 1),
        }


# Global cache instance
cache = TTLCache()

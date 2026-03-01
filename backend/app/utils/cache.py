"""In-memory TTL cache for frequently requested data.

Simple, thread-safe cache that avoids hammering external *arr services
for data that rarely changes (dashboard stats, analytics, recommendations).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Coroutine


class TTLCache:
    """Async-aware in-memory cache with per-key TTL."""

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

    def clear(self) -> None:
        """Clear the entire cache."""
        self._store.clear()


# Global cache instance
cache = TTLCache()

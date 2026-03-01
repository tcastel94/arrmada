"""Tests for the TTL cache utility."""

from __future__ import annotations

import asyncio

import pytest

from app.utils.cache import TTLCache


@pytest.mark.asyncio
async def test_cache_returns_cached_value():
    """Factory should only be called once within TTL."""
    cache = TTLCache()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return {"data": call_count}

    result1 = await cache.get_or_set("key", factory, ttl_seconds=10)
    result2 = await cache.get_or_set("key", factory, ttl_seconds=10)

    assert result1 == result2
    assert call_count == 1


@pytest.mark.asyncio
async def test_cache_expires():
    """After TTL, factory should be called again."""
    cache = TTLCache()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return call_count

    result1 = await cache.get_or_set("key", factory, ttl_seconds=0)
    await asyncio.sleep(0.01)
    result2 = await cache.get_or_set("key", factory, ttl_seconds=0)

    assert call_count == 2
    assert result2 == 2


@pytest.mark.asyncio
async def test_cache_invalidate():
    """Invalidate should force re-computation."""
    cache = TTLCache()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return call_count

    await cache.get_or_set("key", factory, ttl_seconds=60)
    cache.invalidate("key")
    result = await cache.get_or_set("key", factory, ttl_seconds=60)

    assert call_count == 2
    assert result == 2


@pytest.mark.asyncio
async def test_cache_clear():
    """Clear should remove all entries."""
    cache = TTLCache()

    async def factory():
        return 42

    await cache.get_or_set("a", factory, ttl_seconds=60)
    await cache.get_or_set("b", factory, ttl_seconds=60)

    cache.clear()
    assert cache._store == {}


@pytest.mark.asyncio
async def test_cache_different_keys():
    """Different keys should have independent caches."""
    cache = TTLCache()

    async def factory_a():
        return "a_value"

    async def factory_b():
        return "b_value"

    result_a = await cache.get_or_set("a", factory_a, ttl_seconds=60)
    result_b = await cache.get_or_set("b", factory_b, ttl_seconds=60)

    assert result_a == "a_value"
    assert result_b == "b_value"

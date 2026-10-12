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

    assert result1 == 1
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


@pytest.mark.asyncio
async def test_nested_keys_do_not_deadlock():
    """Un calcul qui demande une AUTRE clé (tableau de bord → médiathèque).

    Avec l'ancien verrou unique, l'appel imbriqué attendait un verrou déjà
    tenu par l'appel parent : blocage définitif de la requête.
    """
    cache = TTLCache()

    async def library():
        return ["Dune"]

    async def dashboard():
        return {"library": await cache.get_or_set("media:all", library, ttl_seconds=60)}

    result = await asyncio.wait_for(cache.get_or_set("dashboard", dashboard, ttl_seconds=60), 2)
    assert result == {"library": ["Dune"]}


@pytest.mark.asyncio
async def test_same_key_is_computed_once_under_concurrency():
    """Deux demandes simultanées de la même clé : un seul calcul."""
    cache = TTLCache()
    calls = 0

    async def slow():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return calls

    results = await asyncio.gather(*(cache.get_or_set("k", slow, ttl_seconds=60) for _ in range(5)))
    assert results == [1] * 5
    assert calls == 1

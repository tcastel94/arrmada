"""Recherche IA : Ollama local d'abord, OpenRouter en secours."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import llm, media_aggregator

LIBRARY = [
    {"type": "movie", "title": "La Haine", "year": 1995, "has_file": True},
    {"type": "movie", "title": "Gothika", "year": 2003, "has_file": True},
    {"type": "series", "title": "Haine & Co", "year": 2020, "has_file": False},
]


@pytest.fixture
def engines(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Fake engines: each one answers ``replies[name]`` or raises it."""
    state: dict[str, Any] = {"calls": [], "replies": {}}

    def fake(name: str):
        async def _chat(system: str, user: str, **_: Any) -> str:
            state["calls"].append(name)
            reply = state["replies"].get(name, RuntimeError(f"{name} down"))
            if isinstance(reply, Exception):
                raise reply
            return reply

        return _chat

    monkeypatch.setattr(llm, "chat_ollama", fake("ollama"))
    monkeypatch.setattr(llm, "chat_openrouter", fake("openrouter"))
    monkeypatch.setattr(settings, "OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-test")

    async def _library(db: Any) -> list[dict]:
        return LIBRARY

    monkeypatch.setattr(media_aggregator, "cached_library", _library)
    return state


async def test_local_ollama_answers_first(
    client: AsyncClient, auth_headers: dict, engines: dict[str, Any]
) -> None:
    engines["replies"]["ollama"] = '{"type": "movie", "title_keywords": ["haine"]}'
    resp = await client.get("/api/search/ai", params={"q": "la haine"}, headers=auth_headers)
    body = resp.json()
    assert engines["calls"] == ["ollama"]
    assert body["engine"] == "ollama"
    assert [m["title"] for m in body["items"]] == ["La Haine"]


async def test_openrouter_is_the_fallback(
    client: AsyncClient, auth_headers: dict, engines: dict[str, Any]
) -> None:
    engines["replies"]["openrouter"] = '```json\n{"type": "series"}\n```'
    resp = await client.get("/api/search/ai", params={"q": "mes séries"}, headers=auth_headers)
    body = resp.json()
    assert engines["calls"] == ["ollama", "openrouter"]
    assert body["engine"] == "openrouter"
    assert [m["title"] for m in body["items"]] == ["Haine & Co"]


async def test_both_engines_down(
    client: AsyncClient, auth_headers: dict, engines: dict[str, Any]
) -> None:
    resp = await client.get("/api/search/ai", params={"q": "mes films"}, headers=auth_headers)
    body = resp.json()
    assert body["items"] == []
    assert body["ai_available"] is True
    assert "Ollama + OpenRouter" in body["error"]


async def test_not_configured(
    client: AsyncClient,
    auth_headers: dict,
    engines: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OLLAMA_URL", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    resp = await client.get("/api/search/ai", params={"q": "mes films"}, headers=auth_headers)
    body = resp.json()
    assert body["ai_available"] is False
    assert engines["calls"] == []

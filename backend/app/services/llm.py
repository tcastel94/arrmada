"""Shared LLM access — local Ollama first, OpenRouter as fallback.

Used by the AI search (natural language → library filters) and the Docker log
analysis. The local Ollama on the NAS costs nothing and keeps queries on the
LAN; OpenRouter only answers when Ollama is not configured or fails.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_OLLAMA_MODEL = "qwen2.5:3b-instruct-q4_K_M"


class LLMUnavailableError(RuntimeError):
    """No engine (Ollama nor OpenRouter) produced an answer."""


def ollama_cfg() -> tuple[str, str]:
    url = (getattr(settings, "OLLAMA_URL", "") or "").rstrip("/")
    model = getattr(settings, "OLLAMA_MODEL", "") or DEFAULT_OLLAMA_MODEL
    return url, model


def ai_configured() -> bool:
    """True when at least one engine is configured."""
    return bool(ollama_cfg()[0] or settings.OPENROUTER_API_KEY)


async def chat_ollama(
    system: str,
    user: str,
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    """Local Ollama on the NAS — primary engine (no cost, no external call)."""
    url, model = ollama_cfg()
    if not url:
        raise RuntimeError("OLLAMA_URL non défini")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "format": "json",  # force valid JSON output
                "keep_alive": "30m",  # keep the model warm for repeat queries
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


async def chat_openrouter(
    system: str,
    user: str,
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> str:
    """OpenRouter — fallback if the local Ollama is unavailable."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY manquante")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.AI_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def chat_json(
    system: str,
    user: str,
    *,
    temperature: float,
    ollama_max_tokens: int,
    ollama_timeout: float,
    openrouter_max_tokens: int,
    openrouter_timeout: float,
    purpose: str,
) -> tuple[str, str]:
    """Ask Ollama, then OpenRouter. Returns ``(content, engine_name)``.

    Raises :class:`LLMUnavailableError` (chained to the last engine error)
    when neither engine answered.
    """
    attempts = (
        ("ollama", chat_ollama, ollama_max_tokens, ollama_timeout),
        ("openrouter", chat_openrouter, openrouter_max_tokens, openrouter_timeout),
    )
    last_err: Exception | None = None
    for name, fn, max_tokens, timeout in attempts:
        try:
            content = await fn(
                system, user, temperature=temperature, max_tokens=max_tokens, timeout=timeout
            )
            return content, name
        except Exception as exc:  # noqa: BLE001 — try the next engine
            last_err = exc
            logger.warning("%s via %s échouée: %s", purpose, name, exc)
    raise LLMUnavailableError(
        f"{purpose} échouée (Ollama + OpenRouter) : {type(last_err).__name__}"
    ) from last_err


def parse_json_object(content: str) -> dict[str, Any]:
    """Parse an LLM reply into a dict, tolerating code fences / stray prose."""
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise

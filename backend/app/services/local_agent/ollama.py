"""Appel à Ollama : ``POST /api/chat`` avec la liste d'outils.

@author : Jeff Pomponne <jpomponne@gmail.com>

Pourquoi l'API native ``/api/chat`` plutôt que la couche compatible OpenAI
(``/v1/chat/completions``) : c'est la seule qui laisse régler ``num_ctx`` et
``keep_alive`` à chaque appel, sans toucher à la configuration du conteneur.

Les trois réglages qui comptent (voir ``config.py``) :

- ``num_ctx``    : taille du contexte. Trop petit, Ollama coupe le début de
  l'échange sans rien dire : le modèle « oublie » la consigne ou la question ;
- ``keep_alive`` : durée de maintien en VRAM. La carte est partagée ;
- ``temperature``: basse (0,1). Pour remplir un bon de commande, on veut la
  réponse la plus probable, pas de la créativité.

La réponse est lue en flux (une ligne JSON par fragment) : le texte s'affiche
au fil de l'eau dans l'interface, au lieu d'attendre la fin.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings

# Connexion : court (Ollama est sur le LAN). Lecture : long, le premier appel
# charge le modèle en VRAM (10 à 20 s) avant de produire le moindre jeton.
TIMEOUT = httpx.Timeout(300.0, connect=10.0)
TEMPERATURE = 0.1


class OllamaError(Exception):
    """Ollama injoignable, modèle absent, ou réponse illisible. Message lisible tel quel.

    ``retryable`` : l'erreur vient d'une réponse ratée du modèle (HTTP 5xx), pas
    d'une panne. Vu au banc : un appel d'outil mal formé par le modèle fait
    répondre 500 à Ollama ; la même demande, renvoyée, passe.
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class ChatResult:
    """Réponse complète d'un appel au modèle."""

    content: str = ""
    # [{"id": "...", "name": "get_queue", "arguments": {...}}]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0  # jetons lus (consigne + outils + historique)
    output_tokens: int = 0  # jetons écrits
    done_reason: str = ""


def base_url() -> str:
    return (settings.OLLAMA_URL or "").rstrip("/")


def is_configured() -> bool:
    return bool(base_url())


def _tool_calls(raw: Any, offset: int) -> list[dict[str, Any]]:
    """Met les appels d'outils d'Ollama dans une forme unique.

    Les arguments arrivent normalement en objet JSON ; certains modèles les
    renvoient en texte JSON : on tente la lecture, et sinon on garde le texte
    tel quel pour que la validation le rejette avec un message clair.
    """
    calls = []
    for index, call in enumerate(raw or []):
        function = (call or {}).get("function") or {}
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            with contextlib.suppress(ValueError):
                arguments = json.loads(arguments)
        calls.append(
            {
                "id": str(call.get("id") or f"call_{offset + index}"),
                "name": str(function.get("name") or ""),
                "arguments": arguments if arguments is not None else {},
            }
        )
    return calls


async def chat_stream(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    """Un appel au modèle. Émet ``("text", fragment)`` puis ``("final", ChatResult)``."""
    url = base_url()
    if not url:
        raise OllamaError("OLLAMA_URL n'est pas renseigné dans le .env.")
    model = model or settings.LOCAL_AGENT_MODEL
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "stream": True,
        "think": settings.LOCAL_AGENT_THINK,
        "keep_alive": settings.LOCAL_AGENT_KEEP_ALIVE,
        "options": {"num_ctx": settings.LOCAL_AGENT_NUM_CTX, "temperature": TEMPERATURE},
    }
    result = ChatResult()
    try:
        async with (
            httpx.AsyncClient(timeout=TIMEOUT) as client,
            client.stream("POST", f"{url}/api/chat", json=payload) as response,
        ):
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", "replace")
                try:
                    detail = json.loads(body).get("error") or body
                except ValueError:
                    detail = body
                raise OllamaError(
                    f"Ollama a refusé l'appel (HTTP {response.status_code}) : {detail[:300]}",
                    retryable=response.status_code >= 500,
                )
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise OllamaError(f"Erreur d'Ollama : {str(chunk['error'])[:300]}")
                message = chunk.get("message") or {}
                if message.get("content"):
                    result.content += message["content"]
                    yield ("text", message["content"])
                if message.get("tool_calls"):
                    result.tool_calls += _tool_calls(message["tool_calls"], len(result.tool_calls))
                if chunk.get("done"):
                    result.prompt_tokens = int(chunk.get("prompt_eval_count") or 0)
                    result.output_tokens = int(chunk.get("eval_count") or 0)
                    result.done_reason = str(chunk.get("done_reason") or "")
    except httpx.TimeoutException as exc:
        raise OllamaError(
            f"Ollama ne répond pas ({url}) : modèle en cours de chargement ou GPU saturé."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama injoignable ({url}) : {type(exc).__name__}.") from exc
    except ValueError as exc:
        raise OllamaError("Réponse d'Ollama illisible (JSON invalide).") from exc
    yield ("final", result)


async def probe() -> dict[str, Any]:
    """Ollama répond-il, et le modèle de l'agent est-il installé ? (page d'état)"""
    url = base_url()
    if not url:
        return {"reachable": False, "model_installed": False}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(f"{url}/api/tags")
            response.raise_for_status()
            names = {str(m.get("name")) for m in response.json().get("models") or []}
    except (httpx.HTTPError, ValueError, AttributeError):
        return {"reachable": False, "model_installed": False}
    wanted = settings.LOCAL_AGENT_MODEL
    return {
        "reachable": True,
        "model_installed": wanted in names or f"{wanted}:latest" in names,
    }

"""Boucle du copilote : le modèle lit, appelle des outils, lit encore, puis répond.

Un « tour » = un message de l'utilisateur et tout ce qu'il déclenche. Le tour
est une suite d'appels au modèle : tant que celui-ci demande des outils, on
les exécute (en parallèle, ils sont tous en lecture seule), on lui rend les
résultats, et on le rappelle. Chaque étape est émise en événement
(``text``, ``thinking``, ``tool_start``, ``tool_end``, ``usage``, ``error``,
``done``) : l'API les relaie au navigateur en SSE.

Pourquoi une boucle écrite à la main plutôt que le « tool runner » du SDK :
il faut relayer chaque fragment de texte ET chaque appel d'outil au
navigateur, garder l'historique exact côté serveur pour le tour suivant, et
pouvoir l'annuler proprement. Le reste suit la documentation du SDK
(``messages.stream`` + ``get_final_message``).

Règle d'or de l'historique : il n'est JAMAIS réécrit. Les blocs de réflexion
du modèle sont signés et liés au début de la conversation ; modifier un
message passé les invalide. On ajoute à la fin, ou, si un tour échoue ou est
interrompu, on retire ce tour entier (coupe par la fin, toujours valide).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.config import settings
from app.services.copilot import tools
from app.services.copilot.conversations import Conversation, Usage
from app.services.copilot.prompt import system_prompt
from app.services.copilot.redaction import Redactor
from app.utils.logger import get_logger

logger = get_logger(__name__)

Event = tuple[str, dict[str, Any]]

# Plafond de la réponse (réflexion comprise), pas une cible : le modèle
# s'arrête de lui-même. Trop bas, il serait coupé en pleine analyse.
MAX_TOKENS = 64_000
# Appels au modèle par tour : garde-fou contre une boucle d'outils sans fin.
MAX_MODEL_CALLS = 24
MAX_JSON_RETRIES = 2

# Repli côté serveur : si les garde-fous du modèle refusent une demande
# légitime (catégories « cyber » ou « frontier_llm »), l'API la rejoue sur le
# modèle précédent dans le même appel, au lieu de s'arrêter.
BETAS = ["server-side-fallback-2026-07-01"]

# $ par million de jetons : entrée, sortie, lecture du cache, écriture du cache (5 min).
# Tarifs API Anthropic relevés le 03/11/2026. Sert à l'ESTIMATION affichée
# dans l'interface ; la facture fait foi.
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.50),
    "claude-sonnet-5": (2.0, 10.0, 0.20, 2.50),
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-fable-5-2": (8.0, 40.0, 0.20, 10.0),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
}

_client: anthropic.AsyncAnthropic | None = None


def is_configured() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def get_client() -> Any:
    """Client de l'API Anthropic (un seul par processus : il garde ses connexions)."""
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _prices_for(model: str) -> tuple[float, float, float, float] | None:
    # Le plus long d'abord : « claude-sonnet-5-5 » ne doit pas être pris pour « claude-sonnet-5 ».
    for name in sorted(PRICES, key=len, reverse=True):
        if model.startswith(name):
            return PRICES[name]
    return None


def _usage_of(response: Any) -> Usage:
    """Jetons et coût estimé d'une réponse du modèle."""
    raw = getattr(response, "usage", None)

    def count(attribute: str) -> int:
        return int(getattr(raw, attribute, 0) or 0)

    usage = Usage(
        input_tokens=count("input_tokens"),
        output_tokens=count("output_tokens"),
        cache_read_tokens=count("cache_read_input_tokens"),
        cache_write_tokens=count("cache_creation_input_tokens"),
        web_searches=sum(
            1
            for block in getattr(response, "content", None) or []
            if getattr(block, "type", "") == "server_tool_use"
            and getattr(block, "name", "") == "web_search"
        ),
    )
    prices = _prices_for(str(getattr(response, "model", "") or ""))
    if prices is None:
        usage.cost_known = False
    else:
        price_in, price_out, price_read, price_write = prices
        usage.cost_usd = (
            usage.input_tokens * price_in
            + usage.output_tokens * price_out
            + usage.cache_read_tokens * price_read
            + usage.cache_write_tokens * price_write
        ) / 1_000_000
    return usage


def _server_result_failed(block: Any) -> bool:
    """Un outil côté serveur (recherche web…) ne lève pas d'erreur : il renvoie un bloc d'erreur."""
    content = getattr(block, "content", None)
    if isinstance(content, dict):
        return "error_code" in content
    return hasattr(content, "error_code") or str(getattr(content, "type", "")).endswith("_error")


def _api_error_message(exc: anthropic.APIError) -> str:
    """Message affiché à l'utilisateur pour une erreur de l'API, du plus précis au plus général."""
    if isinstance(exc, anthropic.AuthenticationError):
        return (
            "Clé d'API Anthropic refusée : vérifie ANTHROPIC_API_KEY dans le .env, "
            "puis redémarre le conteneur."
        )
    if isinstance(exc, anthropic.PermissionDeniedError):
        return f"Accès refusé par Anthropic pour cette clé : {exc.message}"
    if isinstance(exc, anthropic.NotFoundError):
        return f"Modèle « {settings.COPILOT_MODEL} » introuvable : vérifie COPILOT_MODEL."
    if isinstance(exc, anthropic.RateLimitError):
        return "Limite de débit de l'API Anthropic atteinte : réessaie dans une minute."
    if isinstance(exc, anthropic.BadRequestError):
        return f"Requête refusée par l'API Anthropic : {exc.message}"
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return (
                f"API Anthropic indisponible (HTTP {exc.status_code}) : réessaie dans un instant."
            )
        return f"Erreur de l'API Anthropic (HTTP {exc.status_code}) : {exc.message}"
    if isinstance(exc, anthropic.APIConnectionError):
        return "API Anthropic injoignable : vérifie l'accès Internet du conteneur ArrMada."
    return f"Erreur de l'API Anthropic : {exc}"


def _request_parameters() -> dict[str, Any]:
    """Tout ce qui ne change pas d'un appel à l'autre (et se met donc en cache)."""
    return {
        "model": settings.COPILOT_MODEL,
        "max_tokens": MAX_TOKENS,
        # Repère de cache sur la consigne : outils + consigne sont relus à bas prix.
        "system": [
            {"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}
        ],
        "tools": tools.api_tools(web_search=settings.COPILOT_WEB_SEARCH),
        # Réflexion décidée par le modèle ; son résumé est relayé à l'interface
        # (sinon, entre deux outils, l'écran reste muet).
        "thinking": {"type": "adaptive", "display": "summarized"},
        "output_config": {"effort": settings.COPILOT_EFFORT},
        # Cache automatique sur la fin de la conversation, qui grandit à chaque appel.
        "cache_control": {"type": "ephemeral"},
        "betas": BETAS,
        "fallbacks": "default",
    }


async def _run_tools(tool_uses: list[Any], redactor: Redactor) -> AsyncIterator[Event | list[Any]]:
    """Exécute les outils demandés en parallèle.

    Émet un ``tool_end`` dès qu'un outil a fini, puis, en dernier, la liste des
    blocs ``tool_result`` dans l'ordre des demandes (tous dans UN message : les
    répartir sur plusieurs apprendrait au modèle à ne plus paralléliser).
    """

    async def run(block: Any) -> tuple[str, tools.ToolOutcome]:
        return block.id, await tools.execute(block.name, block.input, redactor)

    tasks = [asyncio.create_task(run(block)) for block in tool_uses]
    outcomes: dict[str, tools.ToolOutcome] = {}
    try:
        for finished in asyncio.as_completed(tasks):
            tool_id, outcome = await finished
            outcomes[tool_id] = outcome
            yield (
                "tool_end",
                {"id": tool_id, "ok": not outcome.is_error, "duration_ms": outcome.duration_ms},
            )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()

    results = []
    for block in tool_uses:
        outcome = outcomes[block.id]
        result: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": outcome.content,
        }
        if outcome.is_error:
            result["is_error"] = True
        results.append(result)
    yield results


async def run_turn(
    conversation: Conversation,
    user_text: str,
    *,
    client: Any,
    redactor: Redactor | None = None,
) -> AsyncIterator[Event]:
    """Déroule un tour et émet ses événements. L'appelant tient ``conversation.lock``."""
    messages = conversation.messages
    start_length = len(messages)
    turn_usage = Usage()
    completed = False
    stop_reason: str | None = None
    served_by = settings.COPILOT_MODEL

    try:
        messages.append({"role": "user", "content": user_text})
        if redactor is None:
            redactor = await tools.build_redactor()
        parameters = _request_parameters()

        model_calls = 0
        json_retries = 0
        wrote_text = False
        failure: dict[str, Any] | None = None
        announced: set[str] = set()  # outils dont le début a été montré à l'interface

        while True:
            model_calls += 1
            if model_calls > MAX_MODEL_CALLS:
                yield (
                    "notice",
                    {
                        "message": f"Arrêt après {MAX_MODEL_CALLS} étapes sans conclusion : "
                        "reformule ou découpe la question."
                    },
                )
                completed = True
                break

            try:
                async with client.beta.messages.stream(**parameters, messages=messages) as stream:
                    async for event in stream:
                        kind = event.type
                        if kind == "text":
                            wrote_text = True
                            yield ("text", {"delta": event.text})
                        elif kind == "thinking":
                            yield ("thinking", {"delta": event.thinking})
                        elif kind == "content_block_start":
                            started = event.content_block.type
                            if started == "text" and wrote_text:
                                # Nouveau paragraphe après une série d'outils
                                yield ("text", {"delta": "\n\n"})
                            elif started == "thinking":
                                yield ("thinking", {"delta": "", "start": True})
                        elif kind == "content_block_stop":
                            block = event.content_block
                            if block.type == "tool_use" or (
                                # Côté serveur, seules la recherche et la lecture web sont
                                # montrées : le tri des résultats (code exécuté par l'API
                                # entre deux recherches) n'apprend rien à l'utilisateur.
                                block.type == "server_tool_use"
                                and block.name in tools.WEB_TOOL_LABELS
                            ):
                                announced.add(block.id)
                                yield (
                                    "tool_start",
                                    {
                                        "id": block.id,
                                        "name": block.name,
                                        "label": tools.label_of(block.name),
                                        "input": block.input,
                                        "server": block.type == "server_tool_use",
                                    },
                                )
                            elif (
                                block.type.endswith("_tool_result")
                                and getattr(block, "tool_use_id", None) in announced
                            ):
                                yield (
                                    "tool_end",
                                    {
                                        "id": block.tool_use_id,
                                        "ok": not _server_result_failed(block),
                                    },
                                )
                    response = await stream.get_final_message()
            except ValueError as exc:
                # Arguments d'outil que le SDK n'a pas su lire du tout (JSON
                # cassé) : le bloc n'existe pas, il n'y a rien à quoi répondre.
                # On rejoue l'appel, un nombre borné de fois.
                json_retries += 1
                if json_retries > MAX_JSON_RETRIES:
                    logger.warning("Copilote : arguments d'outil illisibles : %s", exc)
                    failure = {
                        "message": "Le modèle a produit un appel d'outil illisible : réessaie."
                    }
                    break
                continue
            except anthropic.APIError as exc:
                logger.warning("Copilote : erreur de l'API Anthropic : %s", exc)
                failure = {"message": _api_error_message(exc)}
                break
            json_retries = 0

            usage = _usage_of(response)
            turn_usage.add(usage)
            served_by = str(getattr(response, "model", "") or served_by)
            stop_reason = response.stop_reason

            if stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None)
                failure = {
                    "message": "Le modèle a décliné cette demande"
                    + (f" (catégorie « {category} »)" if category else "")
                    + ". Reformule-la ; ce tour n'est pas gardé en mémoire.",
                    "code": "refusal",
                }
                break

            if stop_reason == "pause_turn":
                # Outil côté serveur (recherche web) interrompu en cours de route :
                # on rend la main telle quelle, l'API reprend où elle en était.
                messages.append({"role": "assistant", "content": response.content})
                continue

            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if not tool_uses:
                messages.append({"role": "assistant", "content": response.content})
                if stop_reason == "max_tokens":
                    yield ("notice", {"message": "Réponse coupée : longueur maximale atteinte."})
                completed = True
                break

            if stop_reason == "max_tokens":
                # Des arguments tronqués se lisent comme un objet valide mais
                # incomplet : on n'exécute rien.
                failure = {"message": "Réponse coupée au milieu d'un appel d'outil : réessaie."}
                break

            messages.append({"role": "assistant", "content": response.content})
            async for item in _run_tools(tool_uses, redactor):
                if isinstance(item, list):
                    messages.append({"role": "user", "content": item})
                else:
                    yield item

        if failure is not None:
            yield ("error", failure)
        if turn_usage.input_tokens or turn_usage.output_tokens:
            yield (
                "usage",
                {
                    "turn": turn_usage.as_dict(),
                    "model": served_by,
                    "model_calls": min(model_calls, MAX_MODEL_CALLS),
                },
            )
        yield ("done", {"ok": completed, "stop_reason": stop_reason})
    finally:
        conversation.usage.add(turn_usage)
        if not completed:
            # Échec, refus ou interruption (navigateur parti, bouton Arrêter) :
            # le tour entier est retiré, la conversation reste dans son dernier
            # état valide.
            del messages[start_length:]

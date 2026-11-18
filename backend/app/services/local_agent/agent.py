"""Boucle de l'agent local : le modèle demande des outils, le code les exécute.

@author : Jeff Pomponne <jpomponne@gmail.com>

Un « tour » = un message de l'utilisateur et tout ce qu'il déclenche :

1. on envoie à Ollama la consigne, l'historique et la liste d'outils ;
2. le modèle répond soit par du texte (fin du tour), soit par un ou plusieurs
   « bons de commande » (appels d'outils) ;
3. chaque bon est validé puis exécuté par ``tools.execute`` ; le résultat est
   ajouté à l'historique et on retourne en 1.

Garde-fous de la boucle :

- ``MAX_MODEL_CALLS``   : nombre d'allers-retours par tour. Un modèle qui
  tourne en rond est arrêté, comme un ``timeout`` devant une commande ;
- ``MAX_INVALID_CALLS`` : un appel invalide (outil inconnu, paramètres
  refusés) est renvoyé au modèle avec l'erreur. Deux corrections sont
  tolérées ; à la troisième erreur, le tour s'arrête ;
- ``MAX_EMPTY_ANSWERS``  : une réponse vide est redemandée une fois, de même
  qu'un appel qu'Ollama rejette en erreur 5xx (réponse mal formée du modèle) ;
- pas d'action pendant un diagnostic : après un outil d'enquête (historique,
  indexeurs, disque), un outil d'écriture demandé dans le même tour est
  refusé sans être exécuté (voir ``NO_ACTION_DURING_DIAGNOSTIC``) ;
- bouton fantôme : si le modèle écrit « confirme avec le bouton » sans avoir
  appelé d'outil d'action, aucun bouton n'existe. Le code le lui signale une
  fois et le laisse se corriger (voir ``PHANTOM_BUTTON``) ;
- un tour qui échoue est retiré en entier de l'historique : la conversation
  reste dans son dernier état sain.

Les événements émis ont les mêmes noms que ceux de l'agent Claude
(``text``, ``tool_start``, ``tool_end``, ``notice``, ``error``, ``usage``,
``done``) : l'interface de chat existante les affiche sans modification.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.config import settings
from app.services.copilot import tools as copilot_tools
from app.services.copilot.redaction import Redactor
from app.services.local_agent import audit, ollama, tools
from app.services.local_agent.conversations import Conversation
from app.services.local_agent.prompt import system_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

Event = tuple[str, dict[str, Any]]
ChatBackend = Callable[..., AsyncIterator[tuple[str, Any]]]

MAX_MODEL_CALLS = 8
MAX_INVALID_CALLS = 2
MAX_EMPTY_ANSWERS = 1

# Vu au banc de test : le modèle annonce parfois une proposition « à confirmer
# avec le bouton » sans avoir appelé l'outil qui la crée. L'utilisateur
# chercherait un bouton qui n'existe pas. Ce contrôle ne dépend pas de la bonne
# volonté du modèle : c'est le code qui compare ce qui est dit à ce qui a été fait.
# « Un diagnostic propose une action sans l'exécuter seul » : garanti par le code.
# Dès que le modèle a consulté l'historique, les indexeurs ou le disque dans un
# tour, il enquête ; une action demandée ensuite dans ce même tour est refusée.
# L'utilisateur lit l'explication, puis demande l'action s'il la veut.
NO_ACTION_DURING_DIAGNOSTIC = (
    "REFUSÉ : pas d'action pendant un diagnostic. Rien n'est proposé à l'utilisateur. "
    "Termine ton enquête avec les outils de lecture, explique la cause, puis suggère "
    "l'action en une phrase : l'utilisateur la demandera s'il la veut."
)

PHANTOM_BUTTON = re.compile(r"\bbouton\b", re.IGNORECASE)
PHANTOM_BUTTON_CORRECTION = (
    "[Contrôle automatique] Tu parles d'un bouton de confirmation, mais tu n'as appelé aucun "
    "outil d'action : aucun bouton n'est affiché. Si l'utilisateur a demandé d'ajouter, de "
    "lancer une recherche ou de relancer, appelle l'outil maintenant. Sinon, réponds de "
    "nouveau sans parler de bouton."
)

# Remplacé par les tests (faux modèle qui rejoue un scénario).
chat_backend: ChatBackend = ollama.chat_stream

# Estimation prudente : 1 jeton ≈ 2,5 caractères (le JSON des résultats
# d'outils « coûte » plus de jetons que du texte courant).
CHARS_PER_TOKEN = 2.5
# Part du contexte réservée à la consigne, aux outils et à la réponse.
RESERVED_TOKENS = 4_000


def _history_budget_chars() -> int:
    return int(max(settings.LOCAL_AGENT_NUM_CTX - RESERVED_TOKENS, 2_000) * CHARS_PER_TOKEN)


def _size(message: dict[str, Any]) -> int:
    return len(json.dumps(message, ensure_ascii=False, default=str))


def fit_history(messages: list[dict[str, Any]], budget_chars: int) -> list[dict[str, Any]]:
    """Historique qui tient dans le contexte : les tours les plus anciens sautent.

    Sans cela, c'est Ollama qui coupe, sans prévenir et par le début : la
    consigne ou la question disparaît. On retire des tours ENTIERS (de la
    demande de l'utilisateur à la réponse) pour ne jamais laisser un résultat
    d'outil sans l'appel qui l'a provoqué. Le tour en cours est toujours gardé.
    """
    # Un message « auto » (correction injectée par le code) n'ouvre pas un tour.
    starts = [i for i, m in enumerate(messages) if m.get("role") == "user" and not m.get("auto")]
    kept = messages
    for start in starts:
        kept = messages[start:]
        if sum(_size(m) for m in kept) <= budget_chars:
            break
    return kept


async def run_turn(
    conversation: Conversation,
    user_text: str,
    *,
    redactor: Redactor | None = None,
) -> AsyncIterator[Event]:
    """Déroule un tour et émet ses événements. L'appelant tient ``conversation.lock``."""
    messages = conversation.messages
    start_length = len(messages)
    completed = False
    failure: str | None = None
    model_calls = 0
    invalid_calls = 0
    empty_answers = 0
    action_called = False  # un outil d'écriture a été appelé pendant ce tour
    button_corrected = False
    diagnostic_called = False  # historique, indexeurs ou disque consultés pendant ce tour
    server_retried = False
    prompt_tokens = 0
    output_tokens = 0
    wrote_text = False

    audit.record("request", conversation.id, text=user_text, model=settings.LOCAL_AGENT_MODEL)
    try:
        messages.append({"role": "user", "content": user_text})
        if redactor is None:
            # Même masqueur que l'agent Claude : clés des services et secrets
            # du .env sont remplacés par *** avant d'atteindre le modèle.
            redactor = await copilot_tools.build_redactor()
        definitions = tools.definitions()

        while True:
            model_calls += 1
            if model_calls > MAX_MODEL_CALLS:
                failure = (
                    f"Arrêt après {MAX_MODEL_CALLS} étapes sans conclusion : "
                    "reformule ou découpe la question."
                )
                break

            request = [
                {"role": "system", "content": system_prompt(writes=tools.writes_exposed())},
                *(
                    {key: value for key, value in message.items() if key != "auto"}
                    for message in fit_history(messages, _history_budget_chars())
                ),
            ]
            result: ollama.ChatResult | None = None
            try:
                async for kind, payload in chat_backend(request, definitions):
                    if kind == "text":
                        if not wrote_text:
                            payload = payload.lstrip()
                        if payload:
                            wrote_text = True
                            yield ("text", {"delta": payload})
                    elif kind == "final":
                        result = payload
            except ollama.OllamaError as exc:
                logger.warning("Agent local : %s", exc)
                # Réponse ratée du modèle (HTTP 5xx) et rien d'affiché : une seconde chance.
                if exc.retryable and not server_retried and result is None:
                    server_retried = True
                    continue
                failure = str(exc)
                break
            if result is None:
                failure = "Ollama n'a renvoyé aucune réponse."
                break
            prompt_tokens += result.prompt_tokens
            output_tokens += result.output_tokens
            if result.prompt_tokens >= settings.LOCAL_AGENT_NUM_CTX * 0.95:
                yield (
                    "notice",
                    {
                        "message": "Contexte du modèle presque plein : la réponse peut être "
                        "incomplète. Démarre une nouvelle conversation."
                    },
                )

            if not result.tool_calls:
                if not result.content.strip():
                    # Réponse vide (vu au banc, surtout avec le raisonnement
                    # activé) : on redemande une fois avant d'abandonner.
                    if empty_answers < MAX_EMPTY_ANSWERS:
                        empty_answers += 1
                        continue
                    failure = "Le modèle local n'a rien répondu : reformule la question."
                    break
                messages.append({"role": "assistant", "content": result.content})
                if (
                    tools.writes_exposed()
                    and not action_called
                    and not button_corrected
                    and PHANTOM_BUTTON.search(result.content)
                ):
                    button_corrected = True
                    audit.record("correction", conversation.id, reason="bouton sans outil")
                    messages.append(
                        {"role": "user", "content": PHANTOM_BUTTON_CORRECTION, "auto": True}
                    )
                    yield ("text", {"delta": "\n\n"})
                    continue
                if button_corrected and not action_called and PHANTOM_BUTTON.search(result.content):
                    # Le modèle s'entête : on dit la vérité à sa place.
                    yield (
                        "notice",
                        {
                            "message": "Aucune action n'a été préparée : il n'y a pas de bouton "
                            "à confirmer. Reformule, par exemple « ajoute le film Dune de 2021 »."
                        },
                    )
                audit.record("answer", conversation.id, text=result.content)
                completed = True
                break

            # Le modèle demande des outils : on garde sa demande dans l'historique…
            messages.append(
                {
                    "role": "assistant",
                    "content": result.content,
                    "tool_calls": [
                        {"function": {"name": c["name"], "arguments": c["arguments"]}}
                        for c in result.tool_calls
                    ],
                }
            )
            if wrote_text:
                yield ("text", {"delta": "\n\n"})
            # … puis on exécute, un par un (des lectures rapides : le parallélisme
            # n'apporterait que de la complexité).
            for call in result.tool_calls:
                yield (
                    "tool_start",
                    {
                        "id": call["id"],
                        "name": call["name"],
                        "label": tools.label_of(call["name"]),
                        "input": call["arguments"],
                        "server": False,
                    },
                )
                called = tools.resolve(call["name"])
                if called and called.write and diagnostic_called:
                    # Verrou : pas d'action au milieu d'une enquête. L'outil
                    # n'est pas exécuté, le modèle reçoit le refus et conclut.
                    outcome = tools.ToolOutcome(NO_ACTION_DURING_DIAGNOSTIC, True, False, 0)
                else:
                    outcome = await tools.execute(call["name"], call["arguments"], redactor)
                    action_called = action_called or bool(called and called.write)
                diagnostic_called = diagnostic_called or bool(called and called.diagnostic)
                if outcome.invalid:
                    invalid_calls += 1
                audit.record(
                    "tool_call",
                    conversation.id,
                    tool=call["name"],
                    arguments=call["arguments"],
                    valid=not outcome.invalid,
                )
                audit.record(
                    "tool_result",
                    conversation.id,
                    tool=call["name"],
                    ok=not outcome.is_error,
                    duration_ms=outcome.duration_ms,
                    result=outcome.content,
                )
                yield (
                    "tool_end",
                    {
                        "id": call["id"],
                        "ok": not outcome.is_error,
                        "duration_ms": outcome.duration_ms,
                    },
                )
                messages.append(
                    {"role": "tool", "tool_name": call["name"], "content": outcome.content}
                )

            if invalid_calls > MAX_INVALID_CALLS:
                failure = (
                    "Le modèle local s'est trompé plusieurs fois dans ses appels d'outils : "
                    "reformule la demande plus simplement."
                )
                break

        if failure is not None:
            audit.record("error", conversation.id, message=failure)
            yield ("error", {"message": failure})
        if prompt_tokens or output_tokens:
            yield (
                "usage",
                {
                    "turn": {
                        "input_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 0,
                        "cost_usd": None,  # local : pas de facturation
                        "web_searches": 0,
                    },
                    "model": settings.LOCAL_AGENT_MODEL,
                    "model_calls": min(model_calls, MAX_MODEL_CALLS),
                },
            )
        yield ("done", {"ok": completed, "stop_reason": "end_turn" if completed else None})
    finally:
        if not completed:
            # Échec ou interruption (navigateur parti, bouton Arrêter) : le tour
            # entier est retiré, la conversation reste dans son dernier état sain.
            del messages[start_length:]

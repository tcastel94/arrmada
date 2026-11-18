"""Boucle de l'agent local : le modèle demande des outils, le code les exécute.

@author : Jeff Pomponne <jpomponne@gmail.com>

Un « tour » = un message de l'utilisateur et tout ce qu'il déclenche :

1. on envoie à Ollama la consigne, l'historique et la liste d'outils ;
2. le modèle répond soit par du texte (fin du tour), soit par un ou plusieurs
   « bons de commande » (appels d'outils) ;
3. chaque bon est validé. Une LECTURE est exécutée tout de suite
   (``tools.execute``). Une ÉCRITURE passe par ``_run_action`` : le plan est
   montré à l'utilisateur et n'est exécuté que s'il dit oui. Le résultat est
   ajouté à l'historique et on retourne en 1.

Garde-fous de la boucle :

- ``MAX_MODEL_CALLS``   : nombre d'allers-retours par tour. Un modèle qui
  tourne en rond est arrêté, comme un ``timeout`` devant une commande ;
- ``MAX_INVALID_CALLS`` : un appel invalide (outil inconnu, paramètres
  refusés) est renvoyé au modèle avec l'erreur. Deux corrections sont
  tolérées ; à la troisième erreur, le tour s'arrête ;
- ``MAX_EMPTY_ANSWERS``  : une réponse vide est redemandée une fois ;
- ``MAX_SERVER_RETRIES`` : un appel qu'Ollama rejette en erreur 5xx (appel
  d'outil mal formé par le modèle) est retenté deux fois ;
- pas d'action pendant un diagnostic : après un outil d'enquête (historique,
  indexeurs, disque), un outil d'écriture demandé dans le même tour est
  refusé sans être exécuté (voir ``NO_ACTION_DURING_DIAGNOSTIC``) ;
- bouton fantôme : si le modèle écrit « confirme avec le bouton » sans avoir
  appelé d'outil d'action, aucun bouton n'existe. Le code le lui signale une
  fois et le laisse se corriger (voir ``PHANTOM_CONFIRMATION``) ;
- un tour qui échoue est retiré en entier de l'historique : la conversation
  reste dans son dernier état sain. Seule exception : un tour interrompu alors
  qu'une carte attendait une réponse laisse deux lignes (la demande, et « j'ai
  proposé ceci, rien n'a été fait »), pour que « plutôt en 4K » ait un sens.

Les événements émis ont les mêmes noms que ceux de l'agent Claude
(``text``, ``tool_start``, ``tool_end``, ``notice``, ``error``, ``usage``,
``done``) : l'interface de chat existante les affiche sans modification.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
import unicodedata
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.config import settings
from app.services import ai_actions
from app.services.activity_log import log_event
from app.services.copilot import actions as copilot_actions
from app.services.copilot import tools as copilot_tools
from app.services.copilot.redaction import Redactor
from app.services.copilot.tools.common import _error
from app.services.local_agent import audit, ollama, tools
from app.services.local_agent.conversations import Conversation
from app.services.local_agent.prompt import system_prompt
from app.utils.logger import get_logger

logger = get_logger(__name__)

Event = tuple[str, dict[str, Any]]
ChatBackend = Callable[..., AsyncIterator[tuple[str, Any]]]
# Demande la confirmation à l'utilisateur ailleurs que dans la web app (ligne
# de commande, banc de test). Reçoit la carte, rend True (oui) ou False (non).
Confirmer = Callable[[dict[str, Any]], Awaitable[bool]]

# Une action confirmée qui ne rend pas la main (Sonarr / Radarr bloqué) est abandonnée.
ACTION_TIMEOUT_SECONDS = 90

MAX_MODEL_CALLS = 8
MAX_INVALID_CALLS = 2
MAX_EMPTY_ANSWERS = 1
# Appel d'outil mal formé par le modèle (HTTP 5xx d'Ollama) : mesuré jusqu'à une
# fois sur trois sur certaines formulations, d'où deux nouvelles tentatives.
MAX_SERVER_RETRIES = 2
RETRY_TEMPERATURE = 0.6

# Vu au banc de test : le modèle écrit parfois « confirme et je l'ajoute » ou
# « confirme avec le bouton » sans avoir appelé d'outil d'action. Or c'est
# l'outil qui pose la question à l'utilisateur : sans appel, il n'y a rien à
# confirmer. Ce contrôle ne dépend pas de la bonne volonté du modèle : c'est le
# code qui compare ce qui est dit à ce qui a été fait.
PHANTOM_CONFIRMATION = re.compile(
    r"\bbouton\b|\bconfirm\w*|\b(tu veux|veux-tu) vraiment\b|\bes-tu s[uû]r\b",
    re.IGNORECASE,
)
PHANTOM_CONFIRMATION_CORRECTION = (
    "[Contrôle automatique] Tu demandes une confirmation, mais tu n'as appelé aucun outil "
    "d'action : rien n'est proposé à l'utilisateur. C'est l'outil qui lui demande de "
    "confirmer. Si l'utilisateur a demandé d'ajouter, de lancer une recherche ou de relancer, "
    "appelle l'outil maintenant. Sinon, réponds de nouveau sans demander de confirmation."
)


# « Un diagnostic propose une action sans l'exécuter seul » : garanti par le code.
# Dès que le modèle a consulté l'historique, les indexeurs ou le disque dans un
# tour, il enquête ; une action demandée ensuite dans ce même tour est refusée.
# L'utilisateur lit l'explication, puis demande l'action s'il la veut.
NO_ACTION_DURING_DIAGNOSTIC = (
    "REFUSÉ : pas d'action pendant un diagnostic. Rien n'est proposé à l'utilisateur. "
    "Termine ton enquête avec les outils de lecture, explique la cause, puis suggère "
    "l'action en une phrase : l'utilisateur la demandera s'il la veut."
)

# Trace laissée dans l'historique quand une carte est abandonnée sans réponse
# (bouton Arrêter, ou nouveau message tapé pendant qu'elle attendait).
ABANDONED_PROPOSAL = (
    "J'ai proposé : {summary}. Tu n'as pas validé : rien n'a été fait. Si tu veux autre "
    "chose pour ce titre, dis-le et je refais une proposition."
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


# ══════════════════════════════════════════════════════════════
# Blocages propres à l'action irréversible (suppression de la bibliothèque)
# ══════════════════════════════════════════════════════════════
#
# Ces contrôles sont faits par le CODE, avant même de préparer la carte. Ils ne
# dépendent ni de la consigne ni du modèle : un modèle manipulé peut demander
# la suppression, il ne peut pas la faire passer. Trois refus possibles :
# demande en masse, déjà une suppression dans le tour, plafond horaire atteint.

# « Supprime tous mes films », « vide la bibliothèque », « efface toutes les
# séries »… Le message de l'utilisateur est lu sans accents ni majuscules.
MASS_DELETION = re.compile(
    r"\b(supprim|efface|vire|degage|retire|enleve|nettoie|purge|vide|detrui|delete|remove)\w*\b"
    r".*\b(tous|toutes|tout|toute|ensemble|chaque|integralite|entiere?|all|everything)\b"
    r"|\b(vide|purge|nettoie|rase)\w*\b.*\b(bibliotheque|mediatheque|radarr|sonarr)\b"
)
MASS_DELETION_REFUSED = (
    "REFUSÉ PAR LE SYSTÈME : cette demande vise plusieurs titres ou toute la bibliothèque. "
    "L'agent ne supprime qu'UN film ou UNE série nommé, jamais en masse. Rien n'est proposé "
    "à l'utilisateur. Dis-le-lui en une phrase et n'appelle plus cet outil."
)
ONE_DELETION_PER_TURN = (
    "REFUSÉ PAR LE SYSTÈME : une seule suppression par message. Rien d'autre n'est proposé. "
    "Dis à l'utilisateur de redemander pour le titre suivant."
)
# Heures (horloge monotone) des suppressions réellement exécutées, toutes
# conversations confondues. En mémoire : remis à zéro au redémarrage.
_deletions: list[float] = []


def _destructive_refusal(user_text: str, cards_this_turn: int) -> str | None:
    """Raison de refuser une suppression avant toute carte, ou ``None`` si elle est permise."""
    folded = unicodedata.normalize("NFKD", user_text).encode("ascii", "ignore").decode().lower()
    if MASS_DELETION.search(folded):
        return MASS_DELETION_REFUSED
    if cards_this_turn:
        return ONE_DELETION_PER_TURN
    limit = settings.LOCAL_AGENT_MAX_DELETIONS_PER_HOUR
    recent = [moment for moment in _deletions if time.monotonic() - moment < 3600]
    _deletions[:] = recent
    if len(recent) >= limit:
        return (
            f"REFUSÉ PAR LE SYSTÈME : plafond de {limit} suppressions par heure atteint. Rien "
            "n'est proposé. Dis-le à l'utilisateur ; il pourra réessayer plus tard ou passer "
            "par l'interface de Sonarr / Radarr."
        )
    return None


async def _run_action(
    call: dict[str, Any],
    tool: tools.Tool,
    args: Any,
    conversation_id: str,
    redactor: Redactor,
    *,
    confirmer: Confirmer | None,
    dry_run: bool,
    why: str,
) -> AsyncIterator[Event | tools.ToolOutcome]:
    """Outil d'écriture : plan → confirmation de l'utilisateur → exécution.

    Émet les événements ``confirm`` (carte Valider / Annuler), ``confirm_result``
    et ``action_result`` (les mêmes que l'agent Claude : l'interface les connaît
    déjà), et termine par le ``ToolOutcome`` rendu au modèle.

    Le seul endroit du module qui exécute une écriture est ``plan.run()``,
    plus bas, et on n'y arrive que par ``approved is True``.
    """
    started = time.monotonic()

    def outcome(payload: dict[str, Any], *, is_error: bool = False) -> tools.ToolOutcome:
        text = redactor.text(json.dumps(payload, ensure_ascii=False, default=str))
        return tools.ToolOutcome(text, is_error, False, int((time.monotonic() - started) * 1000))

    try:
        plan = await asyncio.wait_for(tool.handler(args), timeout=tools.TOOL_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 : rendu au modèle, qui l'explique
        logger.warning("Agent local : préparation de %s impossible : %s", tool.name, exc)
        yield outcome(
            {"done": False, "reason": f"Impossible de préparer l'action : {_error(exc)}"},
            is_error=True,
        )
        return
    if not plan.actionable:
        yield outcome(plan.answer)
        return

    audit.record(
        "proposal",
        conversation_id,
        tool=tool.name,
        summary=plan.summary,
        call=plan.call,
        target=plan.target,
        dry_run=dry_run,
    )
    card = {
        "tool_id": call["id"],
        "label": tool.label,
        "summary": plan.summary,
        "details": plan.details,
        "warning": plan.warning,
        # Action irréversible : l'interface et la ligne de commande demandent
        # une validation plus appuyée qu'un simple oui.
        "destructive": tool.destructive,
        "auto": False,
    }

    if dry_run:
        # Simulation : on montre l'appel prévu, on ne demande rien, on n'exécute rien.
        simulation_id = secrets.token_urlsafe(12)
        yield (
            "confirm",
            {
                **card,
                "id": simulation_id,
                "summary": f"[Simulation] {plan.summary}",
                "details": [*plan.details, f"Appel prévu : {plan.call}"],
                "auto": True,
            },
        )
        yield ("confirm_result", {"id": simulation_id, "approved": True, "expired": False})
        message = "Simulation : rien n'a été exécuté."
        yield ("action_result", {"id": simulation_id, "ok": True, "message": message})
        audit.record("action_result", conversation_id, tool=tool.name, ok=True, dry_run=True)
        yield outcome(
            {
                "done": False,
                "dry_run": True,
                "message": "Mode simulation (dry-run) : RIEN n'a été exécuté. Dis à "
                f"l'utilisateur que c'est une simulation et ce qui aurait été fait : "
                f"{plan.summary}. Ne propose pas de le faire pour de vrai : tu ne peux pas "
                "quitter la simulation, c'est un réglage de l'utilisateur.",
            }
        )
        return

    confirmation_id, future = copilot_actions.open_confirmation()
    expired = False
    try:
        card["id"] = confirmation_id
        yield ("confirm", card)
        if confirmer is not None:
            approved = bool(await confirmer(card))
        else:
            try:
                approved = await asyncio.wait_for(
                    asyncio.shield(future), timeout=copilot_actions.CONFIRM_TIMEOUT_SECONDS
                )
            except TimeoutError:
                approved, expired = False, True
        yield ("confirm_result", {"id": confirmation_id, "approved": approved, "expired": expired})
    finally:
        copilot_actions.close_confirmation(confirmation_id)
    audit.record(
        "confirmation", conversation_id, tool=tool.name, approved=approved, expired=expired
    )

    if approved is not True:
        said = "Tu n'as pas répondu à temps" if expired else "Tu as refusé"
        yield outcome(
            {
                "done": False,
                # Ce qui était proposé reste dans l'historique : « plutôt en 4K » a un sens.
                "proposed": plan.summary,
                "reason": f"Rien n'a été fait. Réponds seulement : « {said} : rien n'a été "
                "fait. » N'ajoute rien et ne rappelle pas l'outil.",
            }
        )
        return

    # ── Exécution : uniquement après un « oui » explicite ────────
    failed = False
    try:
        message = await asyncio.wait_for(plan.run(), timeout=ACTION_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 : l'échec est rendu au modèle et à l'utilisateur
        logger.warning("Agent local : %s en échec : %s", tool.name, exc)
        failed, message = True, redactor.text(f"Échec : {_error(exc)}")
    if tool.destructive and not failed:
        _deletions.append(time.monotonic())
    yield ("action_result", {"id": confirmation_id, "ok": not failed, "message": message[:300]})
    audit.record("action_result", conversation_id, tool=tool.name, ok=not failed, message=message)
    # Même journal que l'agent Claude : l'action apparaît dans l'Activité d'ArrMada.
    await log_event(
        category="ai",
        action=tool.name,
        status="error" if failed else "ok",
        source="local-agent",
        title=plan.summary[:250],
        detail=message[:500],
        meta=ai_actions.journal_meta(why, None),
    )
    yield outcome({"done": not failed, "message": message}, is_error=failed)


async def run_turn(
    conversation: Conversation,
    user_text: str,
    *,
    redactor: Redactor | None = None,
    confirmer: Confirmer | None = None,
    dry_run: bool | None = None,
) -> AsyncIterator[Event]:
    """Déroule un tour et émet ses événements. L'appelant tient ``conversation.lock``.

    ``confirmer`` : comment demander la confirmation d'une action. ``None`` : par
    la web app (``POST /api/local-agent/actions/{id}``).
    ``dry_run`` : True force la simulation pour ce tour ; ``None`` suit le réglage
    ``LOCAL_AGENT_DRY_RUN``. Un tour ne peut pas désactiver un dry-run réglé.
    """
    dry_run = bool(dry_run) or settings.LOCAL_AGENT_DRY_RUN
    messages = conversation.messages
    start_length = len(messages)
    completed = False
    failure: str | None = None
    model_calls = 0
    invalid_calls = 0
    empty_answers = 0
    write_attempted = False  # un outil d'écriture a été appelé pendant ce tour
    destructive_cards = 0  # cartes de suppression montrées pendant ce tour
    button_corrected = False
    diagnostic_called = False  # historique, indexeurs ou disque consultés pendant ce tour
    server_retries = 0
    pending_summary: str | None = None  # carte affichée, réponse de l'utilisateur attendue
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
                # Seconde tentative après une réponse mal formée : un peu de hasard,
                # sinon le modèle refait exactement la même erreur.
                options = {"temperature": RETRY_TEMPERATURE} if server_retries else {}
                async for kind, payload in chat_backend(request, definitions, **options):
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
                if exc.retryable and server_retries < MAX_SERVER_RETRIES and result is None:
                    server_retries += 1
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
                    and not write_attempted
                    and not button_corrected
                    and PHANTOM_CONFIRMATION.search(result.content)
                ):
                    button_corrected = True
                    audit.record(
                        "correction", conversation.id, reason="confirmation demandée sans outil"
                    )
                    messages.append(
                        {"role": "user", "content": PHANTOM_CONFIRMATION_CORRECTION, "auto": True}
                    )
                    yield ("text", {"delta": "\n\n"})
                    continue
                if (
                    button_corrected
                    and not write_attempted
                    and PHANTOM_CONFIRMATION.search(result.content)
                ):
                    # Le modèle s'entête : on dit la vérité à sa place.
                    yield (
                        "notice",
                        {
                            "message": "Aucune action n'a été préparée : il n'y a rien à "
                            "confirmer. Reformule, par exemple « ajoute le film Dune de 2021 »."
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
                checked = tools.validate(call["name"], call["arguments"])
                called = None if isinstance(checked, tools.ToolOutcome) else checked[0]
                if called is not None and called.write:
                    write_attempted = True
                    blocked = (
                        _destructive_refusal(user_text, destructive_cards)
                        if called.destructive
                        else None
                    )
                    if diagnostic_called:
                        # Verrou : pas d'action au milieu d'une enquête. L'outil
                        # n'est pas exécuté, le modèle reçoit le refus et conclut.
                        outcome = tools.ToolOutcome(NO_ACTION_DURING_DIAGNOSTIC, True, False, 0)
                    elif blocked:
                        audit.record(
                            "blocked", conversation.id, tool=called.name, reason=blocked[:120]
                        )
                        outcome = tools.ToolOutcome(blocked, True, False, 0)
                    else:
                        async for item in _run_action(
                            call,
                            called,
                            checked[1],  # type: ignore[index]
                            conversation.id,
                            redactor,
                            confirmer=confirmer,
                            dry_run=dry_run,
                            why=user_text,
                        ):
                            if isinstance(item, tools.ToolOutcome):
                                outcome = item
                            else:
                                if item[0] == "confirm" and called.destructive:
                                    destructive_cards += 1
                                if item[0] == "confirm" and not item[1].get("auto"):
                                    pending_summary = str(item[1].get("summary") or "")
                                    conversation.waiting_for_user = True
                                elif item[0] == "confirm_result":
                                    pending_summary = None
                                    conversation.waiting_for_user = False
                                yield item
                else:
                    outcome = await tools.execute(call["name"], call["arguments"], redactor)
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
        conversation.waiting_for_user = False
        if not completed:
            # Échec ou interruption (navigateur parti, bouton Arrêter) : le tour
            # entier est retiré, la conversation reste dans son dernier état sain.
            del messages[start_length:]
            if pending_summary:
                # Interrompu devant une carte : on garde de quoi comprendre la suite
                # (« laisse-moi choisir la qualité » parle de CE titre).
                note = ABANDONED_PROPOSAL.format(summary=pending_summary)
                messages.append({"role": "user", "content": user_text})
                messages.append({"role": "assistant", "content": note})
                audit.record("confirmation", conversation.id, approved=False, abandoned=True)

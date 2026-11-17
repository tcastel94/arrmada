"""Agent local : chat en langage naturel sur l'IA du NAS (Ollama).

@author : Jeff Pomponne <jpomponne@gmail.com>

Mêmes routes et même flux SSE que l'agent Claude (``api/copilot.py``), sous un
autre préfixe : l'interface de chat sert les deux, seul le préfixe change.

- ``GET  /api/local-agent/status``              : configuré ? Ollama répond ? modèle installé ?
- ``POST /api/local-agent/chat``                : un message, réponse en flux SSE ;
- ``DELETE /api/local-agent/conversations/{id}``: oublie une conversation ;
- ``GET  /api/local-agent/audit``               : dernières lignes du journal d'audit.

SSE (« Server-Sent Events ») : une seule requête HTTP qui reste ouverte, le
serveur y pousse des lignes au fil de l'eau. Analogie : un ``tail -f`` par
HTTP. C'est ce qui permet d'afficher le texte pendant que le modèle l'écrit.

Réservé à l'administrateur : refusé aux TV appairées.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.config import settings
from app.services.local_agent import agent, audit, conversations, ollama, tools
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/local-agent",
    tags=["local-agent"],
    dependencies=[Depends(require_admin)],
)

# Sous le délai d'inactivité des proxys (60 s pour nginx) : pendant que le
# modèle se charge en VRAM, un battement garde la connexion ouverte.
SSE_HEARTBEAT_SECONDS = 15


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.get("/status", summary="L'agent local est-il utilisable ?")
async def local_agent_status() -> dict[str, Any]:
    probe = await ollama.probe()
    return {
        "configured": ollama.is_configured(),
        "model": settings.LOCAL_AGENT_MODEL,
        "num_ctx": settings.LOCAL_AGENT_NUM_CTX,
        "keep_alive": settings.LOCAL_AGENT_KEEP_ALIVE,
        "tools": [tool.name for tool in tools.TOOLS],
        **probe,
    }


async def _stream(
    conversation: conversations.Conversation, message: str, *, restarted: bool
) -> AsyncIterator[str]:
    """Relaie les événements du tour en SSE, avec un battement quand rien ne sort."""
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def pump() -> None:
        try:
            async with conversation.lock:
                async for event in agent.run_turn(conversation, message):
                    await queue.put(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Agent local : tour interrompu par une erreur inattendue")
            await queue.put(
                ("error", {"message": "Erreur interne de l'agent local (détail dans les logs)."})
            )
            await queue.put(("done", {"ok": False, "stop_reason": None}))
        finally:
            await queue.put(None)

    task = asyncio.create_task(pump())
    try:
        yield _sse("conversation", {"id": conversation.id, "restarted": restarted})
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=SSE_HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"  # commentaire SSE : ignoré par le client, tient la connexion
                continue
            if item is None:
                break
            yield _sse(*item)
    finally:
        # Navigateur parti ou bouton « Arrêter » : on coupe l'appel au modèle
        # (le GPU est libéré) ; le tour inachevé est retiré de l'historique.
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


@router.post("/chat", summary="Envoie un message à l'agent local (réponse en flux SSE)")
async def chat(body: ChatRequest) -> StreamingResponse:
    if not ollama.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent local non configuré : renseigne OLLAMA_URL dans le .env, "
            "puis redémarre le conteneur.",
        )

    conversation = conversations.get(body.conversation_id)
    # Identifiant inconnu : le serveur a redémarré (historique en mémoire) ou la
    # conversation a expiré. On repart d'une neuve et l'interface le dit.
    restarted = conversation is None and bool(body.conversation_id)
    if conversation is None:
        conversation = conversations.create()
    elif conversation.lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une réponse est déjà en cours pour cette conversation.",
        )

    return StreamingResponse(
        _stream(conversation, body.message.strip(), restarted=restarted),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # pas de mise en tampon par nginx
        },
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Oublie une conversation",
)
async def forget_conversation(conversation_id: str) -> None:
    conversations.drop(conversation_id)


@router.get("/audit", summary="Dernières lignes du journal d'audit de l'agent local")
async def audit_tail(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
    return {"path": str(audit.path()), "entries": audit.tail(limit)}

"""Copilote : assistant IA qui lit l'installation avant de conseiller (ADR-017).

``POST /api/copilot/chat`` répond en flux SSE : le texte arrive au fil de
l'eau, avec les outils que le modèle consulte. L'historique reste côté
serveur (``services/copilot/conversations.py``) ; le navigateur n'envoie que
le nouveau message et l'identifiant de la conversation.

Réservé à l'administrateur (web app, clé API) : refusé aux TV appairées.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import require_admin
from app.config import settings
from app.services.copilot import agent, conversations, knowledge
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/copilot",
    tags=["copilot"],
    dependencies=[Depends(require_admin)],
)

# Sous le délai d'inactivité des proxys (30 s pour Next.js en développement,
# 60 s pour nginx) : un outil lent ou une longue réflexion ne coupe pas le flux.
SSE_HEARTBEAT_SECONDS = 15


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = Field(default=None, max_length=64)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.get("/status", summary="Le copilote est-il configuré ?")
async def copilot_status() -> dict[str, Any]:
    return {
        "configured": agent.is_configured(),
        "model": settings.COPILOT_MODEL,
        "effort": settings.COPILOT_EFFORT,
        "web_search": settings.COPILOT_WEB_SEARCH,
        "documents": len(knowledge.catalog()),
    }


async def _stream(
    conversation: conversations.Conversation, message: str, *, restarted: bool
) -> AsyncIterator[str]:
    """Relaie les événements du tour en SSE, avec un battement quand rien ne sort."""
    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def pump() -> None:
        try:
            async with conversation.lock:
                async for event in agent.run_turn(conversation, message, client=agent.get_client()):
                    await queue.put(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Copilote : tour interrompu par une erreur inattendue")
            await queue.put(
                ("error", {"message": "Erreur interne du copilote (détail dans les journaux)."})
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
        # (et sa facturation) ; le tour inachevé est retiré de l'historique.
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


@router.post("/chat", summary="Envoie un message au copilote (réponse en flux SSE)")
async def chat(body: ChatRequest) -> StreamingResponse:
    if not agent.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Copilote non configuré : renseigne ANTHROPIC_API_KEY dans le .env, "
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

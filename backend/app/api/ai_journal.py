"""Journal de l'agent IA (page Agent IA › Journal).

- ``GET  /api/copilot/journal``             ses dernières actions : quoi, quand,
                                            pourquoi (la demande d'origine) ;
- ``POST /api/copilot/journal/{id}/undo``   défaire une action annulable.

Réservé aux administrateurs, comme l'agent lui-même. La logique est dans
``app/services/ai_journal.py``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.services import ai_journal

router = APIRouter(
    prefix="/api/copilot/journal",
    tags=["copilot"],
    dependencies=[Depends(require_admin)],
)


@router.get("", summary="Dernières actions de l'agent IA")
async def journal(
    limit: int = Query(100, ge=1, le=ai_journal.MAX_ENTRIES), db: AsyncSession = Depends(get_db)
) -> dict:
    return {"entries": await ai_journal.list_entries(db, limit)}


@router.post("/{event_id}/undo", summary="Annule une action de l'agent (si elle s'annule)")
async def undo(event_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return await ai_journal.undo(db, event_id)

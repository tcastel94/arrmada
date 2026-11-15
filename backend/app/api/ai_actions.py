"""Assistant IA qui agit (ADR-018) : demande en clair → actions confirmées.

- ``POST /api/ai/act``                 une demande → réponse + propositions ;
- ``POST /api/ai/act/{id}/confirm``    exécuter une proposition ;
- ``POST /api/ai/act/{id}/cancel``     l'écarter ;
- ``GET|PUT /api/ai/settings``         « confirm » (chaque action validée) ou « auto ».

Le réglage ne se change que par un administrateur (web app, Paramètres).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.services import ai_actions, telegram_alerts
from app.services.llm import LLMUnavailableError, ai_configured

router = APIRouter(prefix="/api/ai", tags=["ai-actions"], dependencies=[Depends(get_current_user)])


class AskBody(BaseModel):
    message: str = Field(..., min_length=2, max_length=500)


@router.post("/act")
async def act(
    body: AskBody, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Demande en clair : l'IA propose des actions du catalogue, le serveur vérifie la cible."""
    if not ai_configured():
        raise HTTPException(status_code=400, detail="Aucune IA configurée (Ollama ou OpenRouter)")
    source = "tv" if user.get("device_id") else "web"
    try:
        return await ai_actions.ask(db, body.message, source)
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=502, detail="L'IA ne répond pas (Ollama et OpenRouter)"
        ) from exc


def _proposal(proposal_id: str) -> ai_actions.Proposal:
    p = ai_actions.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Proposition expirée : refais la demande")
    return p


@router.post("/act/{proposal_id}/confirm")
async def confirm(
    proposal_id: str, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
) -> dict:
    """Exécute une proposition en attente (une seule fois)."""
    p = _proposal(proposal_id)
    if p.status != "pending":
        raise HTTPException(status_code=409, detail="Déjà traitée")
    await ai_actions.execute(db, p, "tv" if user.get("device_id") else "web")
    return p.public()


@router.post("/act/{proposal_id}/cancel")
async def cancel(proposal_id: str) -> dict:
    p = _proposal(proposal_id)
    if p.status == "pending":
        p.status, p.message = "cancelled", "Annulée"
    return p.public()


def _settings() -> dict:
    return {
        "mode": ai_actions.get_mode(),
        "configured": ai_configured(),
        # Alertes Telegram des téléchargements bloqués (boutons Débloquer / Ignorer)
        "telegram": {
            "configured": telegram_alerts.configured(),
            "alerts": telegram_alerts.is_enabled(),
        },
    }


@router.get("/settings")
async def get_settings() -> dict:
    return _settings()


class ModeBody(BaseModel):
    mode: str | None = Field(default=None, pattern="^(confirm|auto)$")
    telegram_alerts: bool | None = None


@router.put("/settings", dependencies=[Depends(require_admin)])
async def put_settings(body: ModeBody) -> dict:
    """« confirm » : chaque action attend un clic ; « auto » : l'IA agit seule et rend compte.

    ``telegram_alerts`` : alerter (ou non) sur Telegram des téléchargements bloqués.
    """
    if body.mode is not None:
        ai_actions.set_mode(body.mode)
    if body.telegram_alerts is not None:
        telegram_alerts.set_enabled(body.telegram_alerts)
    return _settings()

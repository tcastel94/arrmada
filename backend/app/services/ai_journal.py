"""Journal de l'agent IA : ce qu'il a fait, quand, pourquoi, et le bouton « Annuler ».

Les actions de l'agent (copilot/agent.py) et de l'assistant (ai_actions.py)
sont déjà inscrites au journal d'activité, catégorie « ai ». Ce module les
relit pour la page Agent IA › Journal et ajoute deux informations rangées
dans ``meta`` au moment de l'action :

- ``why`` : la demande de l'utilisateur qui l'a provoquée (« la série X ne
  se télécharge plus ») ;
- ``undo`` : comment la défaire, quand c'est possible et sûr (catalogue
  ``UNDO`` ci-dessous). Une fois annulée, ``undone`` garde la date et le
  résultat : on n'annule qu'une fois.

Analogie exploitation : un ``auditd`` sur le compte de service de l'agent,
avec pour chaque ligne le ticket d'origine et la commande de retour arrière
quand il y en a une.

Garde-fou : une annulation ne supprime jamais rien. Un titre ajouté par
l'agent n'est pas retiré de Radarr / Sonarr : il n'est plus suivi (plus de
recherche ni de téléchargement automatique), ce qu'on peut rétablir d'un clic
dans l'*arr.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.activity import ActivityEvent
from app.models.service import Service
from app.services.activity_log import log_event
from app.services.encryption import decrypt_api_key
from app.services.radarr import RadarrClient
from app.services.sabnzbd import SabnzbdClient
from app.services.sonarr import SonarrClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

CATEGORY = "ai"
MAX_ENTRIES = 200

# Annulations connues : type → libellé du bouton (ce que fera le clic)
UNDO: dict[str, str] = {
    "radarr_unmonitor": "Ne plus suivre le film",
    "sonarr_unmonitor": "Ne plus suivre la série",
    "sab_resume_queue": "Reprendre la file SABnzbd",
    "sab_pause_queue": "Remettre la file SABnzbd en pause",
}


# ─────────────────────────────────────────────────────────────────────────────
# Lecture
# ─────────────────────────────────────────────────────────────────────────────


def _ts(event: ActivityEvent) -> int:
    ts = event.ts
    if ts is None:
        return 0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return int(ts.timestamp())


def entry(event: ActivityEvent) -> dict[str, Any]:
    """Une ligne du journal, telle que la page l'affiche."""
    meta = event.meta or {}
    undo = meta.get("undo") if isinstance(meta.get("undo"), dict) else None
    undone = meta.get("undone") if isinstance(meta.get("undone"), dict) else None
    can_undo = bool(undo and undo.get("kind") in UNDO and not undone and event.status == "ok")
    return {
        "id": event.id,
        "ts": _ts(event),
        "action": event.action,
        "status": event.status,
        "source": event.source,
        "title": event.title or "",
        "detail": event.detail or "",
        "why": str(meta.get("why") or ""),
        "undo_label": UNDO[undo["kind"]] if can_undo and undo else None,
        "undone": undone,
    }


async def list_entries(db: AsyncSession, limit: int = 100) -> list[dict[str, Any]]:
    """Les dernières actions de l'agent, la plus récente d'abord."""
    rows = await db.execute(
        select(ActivityEvent)
        .where(ActivityEvent.category == CATEGORY)
        .order_by(ActivityEvent.ts.desc(), ActivityEvent.id.desc())
        .limit(max(1, min(limit, MAX_ENTRIES)))
    )
    return [entry(e) for e in rows.scalars()]


# ─────────────────────────────────────────────────────────────────────────────
# Annulation
# ─────────────────────────────────────────────────────────────────────────────


async def _service(db: AsyncSession, kind: str) -> Service:
    res = await db.execute(
        select(Service).where(Service.type == kind, Service.is_enabled == True)  # noqa: E712
    )
    svc = res.scalars().first()
    if svc is None:
        raise HTTPException(status_code=400, detail=f"{kind.capitalize()} n'est pas configuré")
    return svc


async def _unmonitor(db: AsyncSession, kind: str, item_id: int) -> str:
    """Radarr / Sonarr : le titre reste, mais n'est plus suivi (aucune suppression)."""
    svc = await _service(db, kind)
    cls = RadarrClient if kind == "radarr" else SonarrClient
    client = cls(url=svc.url, api_key=decrypt_api_key(svc.api_key), timeout=30)
    try:
        if isinstance(client, RadarrClient):
            item = await client.get_movie_by_id(item_id)
            item["monitored"] = False
            await client.update_movie(item_id, item)
        else:
            item = await client.get_series_by_id(item_id)
            item["monitored"] = False
            await client.update_series(item_id, item)
    finally:
        await client.close()
    name = item.get("title") or "Titre"
    return f"{name} n'est plus suivi : plus de recherche automatique (rien n'est supprimé)"


async def _sab(db: AsyncSession, pause: bool) -> str:
    svc = await _service(db, "sabnzbd")
    client = SabnzbdClient(url=svc.url, api_key=decrypt_api_key(svc.api_key))
    try:
        await (client.pause() if pause else client.resume())
    finally:
        await client.close()
    return "File SABnzbd remise en pause" if pause else "File SABnzbd reprise"


async def _run(db: AsyncSession, undo: dict[str, Any]) -> str:
    kind = undo.get("kind")
    if kind in ("radarr_unmonitor", "sonarr_unmonitor"):
        return await _unmonitor(db, str(kind).split("_")[0], int(undo["id"]))
    if kind == "sab_pause_queue":
        return await _sab(db, pause=True)
    if kind == "sab_resume_queue":
        return await _sab(db, pause=False)
    raise HTTPException(status_code=400, detail="Cette action ne s'annule pas")


async def undo(db: AsyncSession, event_id: int) -> dict[str, Any]:
    """Défait une action du journal (une seule fois) ; rend la ligne à jour.

    Le résultat est gardé sur la ligne (``meta.undone``) et inscrit au
    journal comme une action à part (« undo »), pour garder la trace.
    """
    event = await db.get(ActivityEvent, event_id)
    if event is None or event.category != CATEGORY:
        raise HTTPException(status_code=404, detail="Action introuvable dans le journal")
    current = entry(event)
    if current["undone"]:
        raise HTTPException(status_code=409, detail="Déjà annulée")
    if not current["undo_label"]:
        raise HTTPException(status_code=400, detail="Cette action ne s'annule pas")

    meta = dict(event.meta or {})
    try:
        message = await _run(db, meta["undo"])
    except HTTPException:
        raise
    except Exception as exc:  # service injoignable : on le dit, la ligne reste annulable
        logger.warning("Journal IA : annulation de %s impossible (%s)", event_id, exc)
        raise HTTPException(status_code=502, detail="Le service n'a pas répondu") from exc

    meta["undone"] = {"at": int(datetime.now(UTC).timestamp()), "message": message}
    event.meta = meta
    flag_modified(event, "meta")  # colonne JSON : la modifier en place ne suffit pas
    await db.commit()
    await log_event(
        category=CATEGORY,
        action="undo",
        status="ok",
        source="web",
        title=f"Annulé : {event.title or event.action}"[:300],
        detail=message[:500],
    )
    return entry(event)

"""Conversations de l'agent local, gardées en mémoire.

@author : Jeff Pomponne <jpomponne@gmail.com>

Ollama est sans état : à chaque message, tout l'échange lui est renvoyé.
L'historique reste côté serveur ; le navigateur n'envoie que le nouveau
message et l'identifiant de la conversation.

Registre SÉPARÉ de celui de l'agent Claude (``copilot/conversations.py``) :
les deux moteurs n'écrivent pas les messages dans le même format, un
identifiant de l'un ne doit jamais ouvrir une conversation de l'autre.

En mémoire seulement : un redémarrage du conteneur vide les conversations.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

IDLE_TTL_SECONDS = 6 * 3600
MAX_CONVERSATIONS = 30


@dataclass
class Conversation:
    id: str
    # Messages au format d'Ollama (rôles user / assistant / tool), dans l'ordre.
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_used_at: float = field(default_factory=time.time)
    # Un seul tour à la fois : deux réponses mêlées donneraient un historique faux.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_conversations: dict[str, Conversation] = {}


def _prune() -> None:
    """Oublie les conversations inactives, puis les plus anciennes au-delà du plafond."""
    now = time.time()
    for conv_id, conv in list(_conversations.items()):
        if now - conv.last_used_at > IDLE_TTL_SECONDS and not conv.lock.locked():
            del _conversations[conv_id]
    overflow = len(_conversations) - MAX_CONVERSATIONS
    if overflow > 0:
        idle = sorted(
            (c for c in _conversations.values() if not c.lock.locked()),
            key=lambda c: c.last_used_at,
        )
        for conv in idle[:overflow]:
            del _conversations[conv.id]


def create() -> Conversation:
    _prune()
    conv = Conversation(id=uuid.uuid4().hex)
    _conversations[conv.id] = conv
    return conv


def get(conversation_id: str | None) -> Conversation | None:
    if not conversation_id:
        return None
    conv = _conversations.get(conversation_id)
    if conv is not None:
        conv.last_used_at = time.time()
    return conv


def drop(conversation_id: str) -> bool:
    return _conversations.pop(conversation_id, None) is not None


def clear() -> None:
    """Vide tout (tests)."""
    _conversations.clear()

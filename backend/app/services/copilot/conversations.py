"""Conversations du copilote, gardées en mémoire.

L'API d'Anthropic est sans état : à chaque message, tout l'échange est
renvoyé (texte, appels d'outils, résultats, blocs de réflexion signés). Cet
historique reste côté serveur : le navigateur n'envoie que le nouveau message
et l'identifiant de la conversation, et ne voit jamais les résultats bruts.

En mémoire seulement (V1) : un redémarrage du conteneur vide les conversations,
l'interface le signale et repart d'une conversation neuve.
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
class Usage:
    """Jetons consommés (et coût estimé) d'un tour ou d'une conversation."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    cost_known: bool = True
    web_searches: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.cost_usd += other.cost_usd
        self.cost_known = self.cost_known and other.cost_known
        self.web_searches += other.web_searches

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost_usd": round(self.cost_usd, 4) if self.cost_known else None,
            "web_searches": self.web_searches,
        }


@dataclass
class Conversation:
    id: str
    # Messages au format de l'API, dans l'ordre. Jamais réécrits : seulement
    # complétés, ou raccourcis par la fin quand un tour échoue (voir agent.py).
    messages: list[Any] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    # Un seul tour à la fois : deux réponses mêlées donneraient un historique invalide.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_conversations: dict[str, Conversation] = {}


def _prune() -> None:
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

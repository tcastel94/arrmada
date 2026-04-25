"""Server-Sent Events (SSE) event bus for real-time push to frontend.

Architecture:
  - EventBus is a global singleton holding connected SSE clients
  - Backend services call `event_bus.publish(...)` to push events
  - The `/api/events/stream` endpoint yields events to the browser
  - Webhooks, health checks, and scheduled tasks all publish to the bus

Event types:
  - service_status  : health state change (online/offline/degraded)
  - download_update : download progress / completion
  - new_import      : new media imported (grab/download from *arr)
  - cache_invalidated : cache was busted (for frontend refetch)
  - health_alert    : critical health event
  - notification    : new in-app notification
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SSEEvent:
    """A single Server-Sent Event."""
    type: str
    data: dict[str, Any]
    id: str | None = None
    timestamp: float = field(default_factory=time.time)

    def format(self) -> str:
        """Format as SSE wire protocol."""
        lines = []
        if self.id:
            lines.append(f"id: {self.id}")
        lines.append(f"event: {self.type}")
        lines.append(f"data: {json.dumps(self.data, default=str)}")
        lines.append("")  # Blank line terminates the event
        return "\n".join(lines) + "\n"


class EventBus:
    """Global event bus for SSE clients.

    Thread-safe via asyncio.Queue per subscriber.
    """

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[SSEEvent]] = []
        self._event_counter = 0
        self._lock = asyncio.Lock()
        self._history: list[SSEEvent] = []  # Keep last 50 events for reconnection
        self._max_history = 50

    async def subscribe(self) -> AsyncGenerator[SSEEvent, None]:
        """Subscribe to events. Yields SSEEvent objects."""
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.append(queue)

        logger.info("SSE client connected (total: %d)", len(self._subscribers))

        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                self._subscribers.remove(queue)
            logger.info("SSE client disconnected (total: %d)", len(self._subscribers))

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to all connected clients."""
        self._event_counter += 1
        event = SSEEvent(
            type=event_type,
            data=data,
            id=str(self._event_counter),
        )

        # Add to history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Distribute to all subscribers
        async with self._lock:
            dead_queues = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
                    logger.warning("SSE queue full, dropping client")

            for q in dead_queues:
                self._subscribers.remove(q)

    @property
    def client_count(self) -> int:
        """Number of connected SSE clients."""
        return len(self._subscribers)

    def get_recent_events(self, since_id: int = 0) -> list[SSEEvent]:
        """Return events since the given ID (for reconnection)."""
        return [e for e in self._history if e.id and int(e.id) > since_id]


# Global event bus singleton
event_bus = EventBus()

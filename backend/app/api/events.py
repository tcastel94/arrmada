"""SSE Events API — real-time event stream for the frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user
from app.utils.event_bus import event_bus

router = APIRouter(
    prefix="/api/events",
    tags=["events"],
)


@router.get("/stream")
async def event_stream(request: Request, _user=Depends(get_current_user)):
    """SSE endpoint — streams real-time events to the browser.

    Usage (frontend):
        const es = new EventSource('/api/events/stream?token=...');
        es.addEventListener('download_update', (e) => { ... });
        es.addEventListener('service_status', (e) => { ... });
    """
    async def generate():
        # Send initial connection event
        yield f"event: connected\ndata: {{\"clients\": {event_bus.client_count + 1}}}\n\n"

        async for event in event_bus.subscribe():
            # Check if client disconnected
            if await request.is_disconnected():
                break
            yield event.format()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/recent")
async def recent_events(
    since_id: int = 0,
    _user=Depends(get_current_user),
):
    """Fetch recent events (for reconnection / catch-up)."""
    events = event_bus.get_recent_events(since_id)
    return {
        "events": [
            {"id": e.id, "type": e.type, "data": e.data, "timestamp": e.timestamp}
            for e in events
        ],
        "clients": event_bus.client_count,
    }

"""Stack auto-configuration API — read keys from appdata, then wire the apps.

  POST /api/stack/plan    what is found, what is missing (read-only)
  POST /api/stack/apply   run the selected actions, return results + new plan

Both require a session: the plan handles API keys and passwords (they never
leave the server — the browser only sees whether a key was found).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services.stack.wiring import apply_plan, build_plan
from app.utils.cache import cache
from app.utils.event_bus import event_bus

router = APIRouter(
    prefix="/api/stack",
    tags=["stack"],
    dependencies=[Depends(get_current_user)],
)


class DownloaderCredentials(BaseModel):
    """Password (and URL when the app was not found in appdata)."""

    url: str | None = Field(default=None, max_length=500)
    username: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, max_length=500)


class PlanRequest(BaseModel):
    hosts: list[str] = Field(
        default_factory=list, max_length=20, description="Extra hosts to probe (LAN IPs)"
    )
    credentials: dict[str, DownloaderCredentials] = Field(
        default_factory=dict, description="Keys: deluge, qbittorrent"
    )

    def creds(self) -> dict[str, dict[str, str]]:
        return {k: v.model_dump(exclude_none=True) for k, v in self.credentials.items()}


class ApplyRequest(PlanRequest):
    action_ids: list[str] = Field(min_length=1, max_length=200)


@router.post("/plan", summary="Scan appdata + services and list the wiring actions")
async def stack_plan(body: PlanRequest, db: AsyncSession = Depends(get_db)) -> dict:
    plan = await build_plan(db, user_hosts=body.hosts, credentials=body.creds())
    return plan.public()


@router.post("/apply", summary="Apply the selected wiring actions")
async def stack_apply(body: ApplyRequest, db: AsyncSession = Depends(get_db)) -> dict:
    results, _ = await apply_plan(
        db, body.action_ids, user_hosts=body.hosts, credentials=body.creds()
    )
    await db.commit()
    if any(r.ok for r in results):
        cache.clear()
        await event_bus.publish("cache_invalidated", {"reason": "stack_wiring"})
    # Fresh plan: shows the applied actions as "done".
    plan = await build_plan(db, user_hosts=body.hosts, credentials=body.creds())
    return {"results": [asdict(r) for r in results], "plan": plan.public()}

"""Kodi : couche JSON-RPC partagée (authentification, choix de l'instance, appel)."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key


# ── Shared JSON-RPC layer ─────────────────────────────────────
def _auth_of(kodi: Service):
    """Return (user, pass) tuple from the stored 'user:pass' api_key, or None."""
    if kodi.api_key:
        creds = decrypt_api_key(kodi.api_key)
        if creds and ":" in creds:
            return tuple(creds.split(":", 1))
    return None


async def _unique_enabled(db: AsyncSession) -> list[Service]:
    """Enabled Kodi services, deduplicated by URL."""
    stmt = select(Service).where(Service.type == "kodi", Service.is_enabled == True)  # noqa: E712
    kodis = (await db.execute(stmt)).scalars().all()
    seen: set[str] = set()
    out: list[Service] = []
    for k in kodis:
        if k.url in seen:
            continue
        seen.add(k.url)
        out.append(k)
    return out


async def _pick(db: AsyncSession, service_id: int | None) -> Service | None:
    kodis = await _unique_enabled(db)
    if not kodis:
        return None
    if service_id is not None:
        return next((k for k in kodis if k.id == service_id), kodis[0])
    return kodis[0]


async def _rpc(
    client: httpx.AsyncClient, base_url: str, auth, method: str, params: dict | None = None
):
    """Perform one Kodi JSON-RPC call; raise on Kodi-level error."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    resp = await client.post(f"{base_url}/jsonrpc", json=payload, auth=auth)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return data.get("result")

"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.api.auth import verify_token
from app.database import get_db as _get_db

# Re-export for convenience
get_db = _get_db


async def get_current_user(request: Request) -> dict:
    """Verify JWT from Authorization header, cookie, or query param, or API key from header/param.

    Returns the decoded token payload.
    """
    from app.config import settings

    # 0. Try X-Api-Key header or apikey query param
    api_key = request.headers.get("X-Api-Key") or request.query_params.get("apikey")
    if api_key and api_key == settings.ARRMADA_AUTH_SECRET:
        return {"sub": "api_client", "role": "admin"}

    token: str | None = None

    # 1. Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Try cookie
    if not token:
        token = request.cookies.get("arrmada_token")

    # 3. Try query param (needed for SSE EventSource which can't set headers)
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return verify_token(token)

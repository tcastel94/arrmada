"""Auth endpoints and JWT utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings
from app.main import limiter
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── JWT helpers ───────────────────────────────────────────────
def create_access_token(expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    payload = {"sub": "arrmada_user", "exp": expire}
    return jwt.encode(
        payload,
        settings.effective_jwt_secret,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token. Raises on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.effective_jwt_secret,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


# ── Endpoints ─────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with password",
    description="Authenticate with a PIN/password and receive a JWT token. "
    "Rate limited to 5 attempts per minute to prevent brute force.",
    responses={
        200: {"description": "Successful authentication"},
        401: {"description": "Invalid password"},
        429: {"description": "Too many attempts — rate limited"},
    },
)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Authenticate with a PIN / password and receive a JWT."""
    if body.password != settings.ARRMADA_AUTH_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    token = create_access_token()
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
    )

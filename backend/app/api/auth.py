"""Auth endpoints and JWT utilities."""


from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import settings
from app.main import limiter
from app.schemas.auth import (
    ChangePasswordRequest,
    CreatePasswordRequest,
    LoginRequest,
    TokenResponse,
)
from app.services import auth_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── JWT helpers ───────────────────────────────────────────────
def create_access_token(expires_delta: "timedelta | None" = None) -> str:
    """Create a signed JWT token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    payload = {"sub": "arrmada_user", "exp": expire}
    return jwt.encode(
        payload,
        auth_store.jwt_secret(),
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token. Raises on failure."""
    try:
        payload = jwt.decode(
            token,
            auth_store.jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def _token_response() -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(),
        expires_in=settings.JWT_EXPIRATION_HOURS * 3600,
    )


async def _require_user(request: Request) -> dict:
    # Imported lazily: app.api.deps imports this module.
    from app.api.deps import get_current_user

    return await get_current_user(request)


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
        409: {"description": "No admin password yet — create one first"},
        429: {"description": "Too many attempts — rate limited"},
    },
)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Authenticate with a PIN / password and receive a JWT."""
    if not auth_store.is_password_set():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No admin password configured yet",
        )
    if not auth_store.verify_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )
    return _token_response()


@router.post(
    "/password",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the admin password (first run only)",
    description="Claims an unconfigured instance: only works while NO password "
    "exists yet, then returns a JWT so the wizard continues logged in. "
    "Does NOT require authentication.",
    responses={409: {"description": "A password already exists"}},
)
@limiter.limit("5/minute")
async def create_password(request: Request, body: CreatePasswordRequest) -> TokenResponse:
    """Set the very first admin password."""
    if auth_store.is_password_set():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An admin password already exists",
        )
    auth_store.set_password(body.password)
    return _token_response()


@router.put(
    "/password",
    response_model=TokenResponse,
    summary="Change the admin password",
    description="Requires a valid session AND the current password.",
    # 403 (not 401) on a wrong current password: the session itself is
    # valid, and the UI logs the user out on any 401.
    responses={403: {"description": "Current password is wrong"}},
)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    _user: dict = Depends(_require_user),
) -> TokenResponse:
    """Replace the admin password (also migrates a legacy .env password)."""
    if not auth_store.verify_password(body.current_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current password is incorrect",
        )
    auth_store.set_password(body.new_password)
    return _token_response()

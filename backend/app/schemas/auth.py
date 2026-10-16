"""Auth schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request — simple PIN/password."""

    password: str = Field(min_length=1, description="Authentication password or PIN")

    model_config = {
        "json_schema_extra": {
            "examples": [{"password": "my_secure_password"}]
        }
    }


class CreatePasswordRequest(BaseModel):
    """First-run admin password creation."""

    password: str = Field(min_length=8, max_length=256, description="New admin password")


class ChangePasswordRequest(BaseModel):
    """Admin password change (requires the current one)."""

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str = Field(description="JWT bearer token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(description="Token validity in seconds")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIs...",
                    "token_type": "bearer",
                    "expires_in": 86400,
                }
            ]
        }
    }

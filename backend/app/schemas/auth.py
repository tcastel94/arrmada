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

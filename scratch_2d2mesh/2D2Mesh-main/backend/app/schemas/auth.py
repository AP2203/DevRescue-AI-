"""Authentication schemas."""
from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.common import ApiModel


class RegisterRequest(ApiModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(ApiModel):
    email: EmailStr
    password: str


class RefreshRequest(ApiModel):
    refresh_token: str


class TokenPair(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(ApiModel):
    user: "UserPublic"
    tokens: TokenPair


from app.schemas.user import UserPublic  # noqa: E402

AuthResponse.model_rebuild()

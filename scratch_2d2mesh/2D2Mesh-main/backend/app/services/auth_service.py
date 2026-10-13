"""Authentication and account service."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.object_id import to_object_id
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.repositories.user_repo import UserRepository
from app.schemas.auth import AuthResponse, TokenPair
from app.schemas.common import normalize_doc

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    async def register(self, email: str, username: str, password: str) -> AuthResponse:
        validate_password_strength(password)
        email = email.lower().strip()

        if await self.users.find_by_email(email) is not None:
            raise ConflictError("An account with this email already exists")
        if await self.users.find_by_username(username) is not None:
            raise ConflictError("This username is already taken")

        user_doc = await self.users.insert_one(
            {
                "email": email,
                "username": username,
                "password_hash": hash_password(password),
                "role": "user",
                "is_active": True,
                "preferences": {"theme": "system", "default_model": "mock"},
                "metrics": {
                    "projects_created": 0,
                    "generations_completed": 0,
                    "generations_failed": 0,
                    "total_model_size_bytes": 0,
                    "total_upload_bytes": 0,
                },
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        user = normalize_doc(user_doc)
        logger.info("Registered user %s (%s)", user["id"], email)
        return AuthResponse(
            user=user,
            tokens=self._issue_pair(
                str(user["id"]), user.get("role", "user"), user["username"]
            ),
        )

    async def login(self, email: str, password: str) -> AuthResponse:
        email = email.lower().strip()
        user_doc = await self.users.find_by_email(email)
        if user_doc is None:
            raise AuthenticationError("Invalid email or password")
        user = normalize_doc(user_doc)
        if not user.get("is_active", True):
            raise AuthenticationError("Account is disabled")
        if not verify_password(password, user["password_hash"]):
            raise AuthenticationError("Invalid email or password")
        logger.info("User logged in: %s", user["id"])
        return AuthResponse(
            user=user,
            tokens=self._issue_pair(user["id"], user.get("role", "user"), user["username"]),
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = decode_refresh_token(refresh_token)
        user_doc = await self.users.find_by_id(payload["sub"])
        if user_doc is None:
            raise AuthenticationError("Account no longer exists")
        user = normalize_doc(user_doc)
        if not user.get("is_active", True):
            raise AuthenticationError("Account is disabled")
        return self._issue_pair(user["id"], user.get("role", "user"), user["username"])

    def _issue_pair(self, user_id: str, role: str, username: str) -> TokenPair:
        settings_holder = __import__("app.config", fromlist=["get_settings"]).get_settings()
        return TokenPair(
            access_token=create_access_token(user_id, role, username),
            refresh_token=create_refresh_token(user_id),
            expires_in=settings_holder.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        user_doc = await self.users.find_by_id(to_object_id(user_id))
        if user_doc is None:
            raise NotFoundError("User not found")
        user = normalize_doc(user_doc)
        if not verify_password(current_password, user["password_hash"]):
            raise ValidationError("Current password is incorrect")
        validate_password_strength(new_password)
        await self.users.update_by_id(to_object_id(user_id), {"password_hash": hash_password(new_password)})

    async def delete_account(self, user_id: str, password: str) -> None:
        user_doc = await self.users.find_by_id(to_object_id(user_id))
        if user_doc is None:
            raise NotFoundError("User not found")
        user = normalize_doc(user_doc)
        if not verify_password(password, user["password_hash"]):
            raise ValidationError("Password is incorrect")
        await self.users.delete_by_id(to_object_id(user_id))

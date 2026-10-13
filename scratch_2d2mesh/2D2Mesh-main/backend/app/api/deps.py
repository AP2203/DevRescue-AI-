"""FastAPI dependencies: services, current user, admin guard."""
from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.exceptions import AuthenticationError, AuthorizationError
from app.logging_config import set_request_context
from app.services import Services

_bearer = HTTPBearer(auto_error=False)


def get_services(request: Request) -> Services:
    return request.app.state.services


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    token = credentials.credentials if credentials else request.query_params.get("token")
    if not token:
        raise AuthenticationError("Missing bearer token")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token subject")
    return user_id


async def get_current_user_async(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    user_id = get_current_user(request, credentials)
    user = await request.app.state.services.users.get_public(user_id)
    if not user.get("is_active", True):
        raise AuthenticationError("Account is disabled")
    set_request_context(user_id=str(user.get("id", user_id)))
    return user


def get_current_admin(user: dict = Depends(get_current_user_async)) -> dict:
    if user.get("role") != "admin":
        raise AuthorizationError("Admin privileges required")
    return user

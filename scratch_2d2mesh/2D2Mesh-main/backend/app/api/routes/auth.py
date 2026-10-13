"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_services
from app.config import get_settings
from app.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.services import Services

router = APIRouter(prefix="/auth", tags=["authentication"])
public_limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    services: Services = Depends(get_services),
) -> AuthResponse:
    return await services.auth.register(payload.email, payload.username, payload.password)


@router.post("/login", response_model=AuthResponse)
@public_limiter.limit(lambda: get_settings().RATE_LIMIT_AUTH)
async def login(
    request: Request,
    payload: LoginRequest,
    services: Services = Depends(get_services),
) -> AuthResponse:
    return await services.auth.login(payload.email, payload.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    services: Services = Depends(get_services),
) -> TokenPair:
    return await services.auth.refresh(payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout() -> None:
    # Stateless JWT: the client simply discards tokens.
    return None

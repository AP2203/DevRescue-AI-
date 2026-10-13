"""User profile and account routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_async, get_services
from app.schemas.user import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    UpdateProfileRequest,
    UserPublic,
    UserStats,
)
from app.services import Services

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
async def get_me(user: dict = Depends(get_current_user_async)) -> dict:
    return user


@router.patch("/me", response_model=UserPublic)
async def update_me(
    payload: UpdateProfileRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    return await services.users.update_profile(user["id"], **fields)


@router.post("/me/password", status_code=204)
async def change_password(
    payload: ChangePasswordRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> None:
    await services.auth.change_password(
        user["id"], payload.current_password, payload.new_password
    )


@router.get("/me/stats", response_model=UserStats)
async def my_stats(
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.users.get_statistics(user["id"])


@router.delete("/me", status_code=204)
async def delete_me(
    payload: DeleteAccountRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> None:
    await services.auth.delete_account(user["id"], payload.password)
    await services.projects.delete_all_for_user(user["id"])

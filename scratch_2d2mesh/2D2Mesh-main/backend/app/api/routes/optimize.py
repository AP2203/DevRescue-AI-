"""Model optimization API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_async, get_services
from app.services import Services

router = APIRouter(tags=["optimization"])


class OptimizeRequest(BaseModel):
    profile: str = Field(
        default="web",
        description="Optimization profile: 'web' | 'game' | 'print'",
    )
    set_active: bool = Field(
        default=False,
        description="Whether to set this optimized model as the active project model",
    )


@router.post(
    "/projects/{project_id}/optimize",
    status_code=status.HTTP_201_CREATED,
)
async def optimize_model(
    project_id: str,
    payload: OptimizeRequest = OptimizeRequest(),
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Optimize the project's model with the selected profile.

    Profiles:
    - **web**: Reduce polygons by 60%, suitable for web display.
    - **game**: Reduce polygons by 75%, recompute normals, game engine ready.
    - **print**: Watertight repair, scale to mm, STL export included.
    """
    return await services.optimization.optimize_project(
        user["id"], project_id, payload.profile, set_active=payload.set_active
    )

"""Auto-repair API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.deps import get_current_user_async, get_services
from app.services import Services

router = APIRouter(tags=["repair"])


class RepairRequest(BaseModel):
    fill_holes: bool = True
    fix_normals: bool = True
    remove_duplicates: bool = True
    remove_degenerate: bool = True


@router.post(
    "/projects/{project_id}/repair",
    status_code=status.HTTP_201_CREATED,
)
async def repair_model(
    project_id: str,
    payload: RepairRequest = RepairRequest(),
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Run automatic mesh repair on the project's current model.

    Returns a new asset with before/after statistics.
    """
    return await services.repair.repair_project(
        user["id"],
        project_id,
        fill_holes=payload.fill_holes,
        fix_normals=payload.fix_normals,
        remove_duplicates=payload.remove_duplicates,
        remove_degenerate=payload.remove_degenerate,
    )

"""Natural-language 3D editing API routes.

Pipeline: User Command → LLM → Structured JSON → Validation → Editing Service
→ Quality Check → Save New Version, with version history + undo/redo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_async, get_services
from app.services import Services

router = APIRouter(tags=["edit"])


class EditRequest(BaseModel):
    command: str = Field(..., min_length=2, max_length=500, description="Natural-language editing command")


@router.post(
    "/projects/{project_id}/edit",
    status_code=status.HTTP_201_CREATED,
)
async def apply_edit(
    project_id: str,
    payload: EditRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Apply a natural-language edit command to the project's current model.

    Examples:
    - "Make the car red."
    - "Change the material to metal."
    - "Reduce the polygon count by 50%."
    - "Prepare this model for 3D printing."
    """
    return await services.edit.apply_nl_edit(user["id"], project_id, payload.command)


@router.post("/projects/{project_id}/edit/undo")
async def undo_edit(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Undo the latest edit, restoring the previous version's model."""
    return await services.edit.undo_edit(user["id"], project_id)


@router.post("/projects/{project_id}/edit/redo")
async def redo_edit(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Redo the previously undone edit, restoring the next version's model."""
    return await services.edit.redo_edit(user["id"], project_id)


@router.get("/projects/{project_id}/edit/versions")
async def get_edit_versions(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Return the full version timeline (Original, Edit 1, Edit 2, …)."""
    return await services.edit.get_versions(user["id"], project_id)


@router.get("/projects/{project_id}/edit-history")
async def get_edit_history(
    project_id: str,
    limit: int = 20,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> list:
    """Return the full edit history for a project."""
    return await services.edit.get_edit_history(user["id"], project_id, limit=limit)

"""Project routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_current_user_async, get_services
from app.schemas.common import Page
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectPublic,
    ProjectRenameRequest,
    ProjectUpdateRequest,
)
from app.services import Services

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectPublic])
async def list_projects(
    query: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Page[ProjectPublic]:
    total, items = await services.projects.list_for_user(
        user["id"], query, status_filter, page, page_size, sort_by, sort_dir
    )
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.projects.create(user["id"], payload.name, payload.description)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.projects.get_detail(user["id"], project_id)


@router.patch("/{project_id}", response_model=ProjectPublic)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
    return await services.projects.update(user["id"], project_id, **fields)


@router.patch("/{project_id}/rename", response_model=ProjectPublic)
async def rename_project(
    project_id: str,
    payload: ProjectRenameRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.projects.rename(user["id"], project_id, payload.name)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    await services.projects.delete(user["id"], project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

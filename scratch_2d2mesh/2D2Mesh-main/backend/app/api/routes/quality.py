"""Quality analysis API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user_async, get_services
from app.services import Services

router = APIRouter(tags=["quality"])


@router.post(
    "/projects/{project_id}/quality-analysis",
    status_code=status.HTTP_201_CREATED,
)
async def run_quality_analysis(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Trigger a quality analysis on the project's current model."""
    return await services.quality.analyze_project(user["id"], project_id)


@router.get("/projects/{project_id}/quality-report")
async def get_quality_report(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    """Fetch the most recent quality report for a project."""
    return await services.quality.get_latest_report(user["id"], project_id)

"""Generation job routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user_async, get_services
from app.schemas.common import Page
from app.schemas.job import GenerateRequest, JobPublic, RetryRequest, RetryResponse
from app.services import Services

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=Page[JobPublic])
async def list_jobs(
    job_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Page[JobPublic]:
    total, items = await services.jobs.list_for_user(
        user["id"], job_status, page, page_size
    )
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/projects/{project_id}/generate", response_model=JobPublic, status_code=status.HTTP_201_CREATED)
async def create_generation(
    project_id: str,
    payload: GenerateRequest,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.jobs.create_generation(
        user["id"], project_id, payload.upload_id, payload.settings
    )


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.jobs.get_owned(user["id"], job_id)


@router.post("/{job_id}/retry", response_model=RetryResponse)
async def retry_job(
    job_id: str,
    payload: RetryRequest = RetryRequest(),
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> RetryResponse:
    job = await services.jobs.retry(
        user["id"], job_id, payload.settings, payload.use_same_upload
    )
    return RetryResponse(job=job, message="Generation retried")


@router.post("/{job_id}/cancel", response_model=JobPublic)
async def cancel_job(
    job_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.jobs.cancel(user["id"], job_id)

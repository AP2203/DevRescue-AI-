"""Project schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import ApiModel


class ProjectCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)


class ProjectRenameRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectUpdateRequest(ApiModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)


class ProjectPublic(ApiModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    image_upload_id: Optional[str] = None
    model_asset_id: Optional[str] = None
    last_job_id: Optional[str] = None
    edit_version: int = 0
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectPublic):
    image_url: Optional[str] = None
    model_summary: Optional["ModelSummary"] = None
    last_job: Optional["JobPublic"] = None


class ProjectFilter(ApiModel):
    query: Optional[str] = None
    status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=100)
    sort_by: str = "created_at"
    sort_dir: str = "desc"


from app.schemas.job import JobPublic  # noqa: E402
from app.schemas.model import ModelSummary  # noqa: E402

ProjectDetail.model_rebuild()

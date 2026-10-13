"""Admin dashboard schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.schemas.common import ApiModel


class JobStatusCount(ApiModel):
    status: str
    count: int = 0


class StorageCount(ApiModel):
    kind: str
    count: int = 0
    bytes: int = 0


class AdminStats(ApiModel):
    users: int = 0
    projects: int = 0
    jobs: int = 0
    uploads: int = 0
    models: int = 0
    storage_total_bytes: int = 0
    jobs_by_status: List[JobStatusCount] = []
    storage_by_kind: List[StorageCount] = []
    active_in_last_24h: int = 0


class AdminUserList(ApiModel):
    items: List["AdminUserRow"]
    total: int
    page: int
    page_size: int


class AdminUserRow(ApiModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool
    metrics: dict = Field(default_factory=dict)
    created_at: datetime


class AdminUpdateUserRequest(ApiModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class AdminUsersFilter(ApiModel):
    query: Optional[str] = None
    page: int = 1
    page_size: int = 20


class AdminJobsFilter(ApiModel):
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20

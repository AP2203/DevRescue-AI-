"""User and profile schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from app.schemas.common import ApiModel


class UserMetrics(ApiModel):
    projects_created: int = 0
    generations_completed: int = 0
    generations_failed: int = 0
    total_model_size_bytes: int = 0
    total_upload_bytes: int = 0


class UserPreferences(ApiModel):
    theme: str = "system"
    default_model: str = "mock"


class UserPublic(ApiModel):
    id: str
    email: EmailStr
    username: str
    role: str
    avatar_url: Optional[str] = None
    preferences: UserPreferences = UserPreferences()
    metrics: UserMetrics = UserMetrics()
    created_at: datetime


class UpdateProfileRequest(ApiModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_]+$")
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    preferences: Optional[UserPreferences] = None


class ChangePasswordRequest(ApiModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserStats(ApiModel):
    usage: UsageSummary
    metrics: UserMetrics = UserMetrics()


class UsageSummary(ApiModel):
    uploads: int = 0
    generations: int = 0
    completed_generations: int = 0
    failed_generations: int = 0
    downloads: int = 0
    total_upload_bytes: int = 0
    total_model_bytes: int = 0
    by_day: list["DailyUsage"] = []


class DailyUsage(ApiModel):
    date: str
    kind: str
    count: int
    bytes: int


class DeleteAccountRequest(ApiModel):
    password: str

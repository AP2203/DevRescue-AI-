"""Generation job schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import Field

from app.schemas.common import ApiModel


class GenerationSettings(ApiModel):
    model: str = "auto"
    resolution: int = Field(default=512, ge=256, le=2048)
    texture_quality: str = "medium"
    remesh: bool = True
    simplify_target: Optional[int] = None


class JobPublic(ApiModel):
    id: str
    project_id: str
    upload_id: str
    status: str
    stage: Optional[str] = None
    progress: float
    message: Optional[str] = None
    error: Optional[str] = None
    ai_model: str
    settings: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class GenerateRequest(ApiModel):
    upload_id: str
    name: Optional[str] = Field(default=None, max_length=200)
    settings: GenerationSettings = GenerationSettings()


class RetryRequest(ApiModel):
    settings: Optional[GenerationSettings] = None
    use_same_upload: bool = True


class RetryResponse(ApiModel):
    job: JobPublic
    message: str

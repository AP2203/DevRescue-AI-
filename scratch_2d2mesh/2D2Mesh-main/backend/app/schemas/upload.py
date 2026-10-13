"""Upload schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.common import ApiModel


class UploadPublic(ApiModel):
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    url: Optional[str] = None
    created_at: datetime = Field(description="Upload creation timestamp")

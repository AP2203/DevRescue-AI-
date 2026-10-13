"""Upload and model asset schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.schemas.common import ApiModel


class UploadPublic(ApiModel):
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime
    url: Optional[str] = None


class ModelStats(ApiModel):
    vertices: int = 0
    faces: int = 0
    edges: int = 0
    triangles: int = 0
    bounds: Optional[list] = None
    has_texture: bool = False
    texture_size: Optional[int] = None
    watertight: bool = False


class ModelSummary(ApiModel):
    filename: str
    size_bytes: int
    mime_type: str
    stats: Optional[ModelStats] = None
    created_at: datetime
    download_glb_url: Optional[str] = None
    download_gltf_url: Optional[str] = None
    download_obj_url: Optional[str] = None
    preview_url: Optional[str] = None


class ModelDownload(ApiModel):
    url: str
    filename: str
    content_type: str
    expires_in: Optional[int] = None


class ModelMetadata(ApiModel):
    id: str
    project_id: str
    job_id: Optional[str] = None
    filename: str
    size_bytes: int
    mime_type: str
    provider: str
    stats: Optional[dict] = None
    created_at: datetime
    model_url: Optional[str] = None
    thumbnail_url: Optional[str] = None

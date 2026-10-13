"""Common schema helpers and shared response envelopes."""
from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int


def normalize_doc(doc: dict) -> dict:
    """Convert a Mongo doc into a JSON-ready dict with a string `id`."""
    normalized = dict(doc)
    if "_id" in normalized:
        normalized["id"] = str(normalized.pop("_id"))
    for key in (
        "user_id",
        "project_id",
        "job_id",
        "image_upload_id",
        "last_job_id",
        "upload_id",
        "model_asset_id",
        "original_asset_id",
        "result_asset_id",
    ):
        if key in normalized and normalized[key] is not None:
            normalized[key] = str(normalized[key])
    return normalized

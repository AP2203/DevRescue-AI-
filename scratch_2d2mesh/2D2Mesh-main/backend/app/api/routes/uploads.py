"""Image upload routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request
from fastapi import UploadFile as FastAPIUploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user_async, get_services
from app.config import get_settings
from app.schemas.upload import UploadPublic
from app.services import Services

router = APIRouter(prefix="/uploads", tags=["uploads"])
uploads_limiter = Limiter(key_func=get_remote_address)


@router.post("", response_model=UploadPublic, status_code=201)
@uploads_limiter.limit(lambda: get_settings().RATE_LIMIT_UPLOAD)
async def create_upload(
    request: Request,
    file: FastAPIUploadFile = File(...),
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.uploads.create(user["id"], file)


@router.get("/{upload_id}", response_model=UploadPublic)
async def get_upload(
    upload_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.uploads.get_owned(user["id"], upload_id)

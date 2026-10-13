"""Authenticated file streaming for the local storage backend."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, Response

from app.api.deps import get_current_user_async, get_services
from app.exceptions import AuthorizationError, NotFoundError
from app.services import Services

files_router = APIRouter(prefix="/files", tags=["files"])


@files_router.get("/{storage_key:path}", response_model=None)
async def stream_file(
    storage_key: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    # Enforce ownership: keys embed the owner's user id in `kind/{user_id}/...`
    parts = storage_key.split("/")
    if len(parts) < 2 or parts[1] != user["id"]:
        raise AuthorizationError("You do not have access to this file")

    if services.storage.provider == "s3":
        url = services.storage.public_url(storage_key)
        if not url:
            raise NotFoundError("File not found")
        return RedirectResponse(url=url)

    try:
        data = await services.storage.load(storage_key)
    except NotFoundError:
        raise
    except Exception as exc:
        raise NotFoundError("File not found") from exc

    lower = storage_key.lower()
    if lower.endswith(".glb"):
        content_type = "model/gltf-binary"
    elif lower.endswith(".gltf"):
        content_type = "model/gltf+json"
    elif lower.endswith(".png"):
        content_type = "image/png"
    elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif lower.endswith(".webp"):
        content_type = "image/webp"
    else:
        content_type = "application/octet-stream"

    filename = storage_key.rsplit("/", 1)[-1]
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=3600",
        },
    )

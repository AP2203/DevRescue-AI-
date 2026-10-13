"""Model fetch, insurance, and download routes.

Model files are streamed (or presigned) with ownership verified first. For the
local storage backend a generic authenticated file route serves any stored key.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.api.deps import get_current_user_async, get_services
from app.exceptions import NotFoundError
from app.schemas.model import ModelDownload, ModelMetadata
from app.services import Services

router = APIRouter(tags=["models"])


async def _load_asset(services: Services, user_id: str, project_id: str) -> dict:
    detail = await services.projects.get_detail(user_id, project_id)
    if not detail.get("model_summary"):
        raise NotFoundError("This project has no generated model yet")
    asset = await services.projects.get_model_asset(user_id, project_id)
    return asset


def _stream(data: bytes, content_type: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/projects/{project_id}/model", response_model=None)
async def download_glb(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    asset = await _load_asset(services, user["id"], project_id)
    data = await services.storage.load(asset["glb_key"])
    if not data:
        raise NotFoundError("GLB file missing in storage")
    await services.usage.record(user["id"], "download", payload_bytes=len(data), project_id=project_id)
    return _stream(data, "model/gltf-binary", asset.get("filename", "model.glb"))


@router.get("/projects/{project_id}/model/gltf", response_model=None)
async def download_gltf(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    asset = await _load_asset(services, user["id"], project_id)
    if not asset.get("gltf_key"):
        raise NotFoundError("GLTF export is not available for this model")
    data = await services.storage.load(asset["gltf_key"])
    if not data:
        raise NotFoundError("GLTF file missing in storage")
    await services.usage.record(user["id"], "download", payload_bytes=len(data), project_id=project_id)
    return _stream(data, "model/gltf+json", "model.gltf")


@router.get("/projects/{project_id}/model/obj", response_model=None)
async def download_obj(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    asset = await _load_asset(services, user["id"], project_id)
    if not asset.get("obj_key"):
        raise NotFoundError("OBJ export is not available for this model")
    data = await services.storage.load(asset["obj_key"])
    if not data:
        raise NotFoundError("OBJ file missing in storage")
    await services.usage.record(user["id"], "download", payload_bytes=len(data), project_id=project_id)
    return _stream(data, "text/plain", "model.obj")


@router.get("/projects/{project_id}/model/preview", response_model=None)
async def download_preview(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    asset = await _load_asset(services, user["id"], project_id)
    if not asset.get("preview_key"):
        raise NotFoundError("Preview image is not available for this model")
    data = await services.storage.load(asset["preview_key"])
    if not data:
        raise NotFoundError("Preview image missing in storage")
    await services.usage.record(user["id"], "download", payload_bytes=len(data), project_id=project_id)
    return _stream(data, "image/png", "preview.png")


@router.get("/projects/{project_id}/model/stl", response_model=None)
async def download_stl(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    """Convert the GLB to STL on-the-fly and stream it for download."""
    from app.ai.optimizer import export_stl

    asset = await _load_asset(services, user["id"], project_id)
    data = await services.storage.load(asset["glb_key"])
    if not data:
        raise NotFoundError("GLB file missing in storage")

    try:
        stl_bytes = export_stl(data)
    except Exception as exc:
        raise NotFoundError(f"STL conversion failed: {exc}") from exc

    await services.usage.record(
        user["id"], "export_stl", payload_bytes=len(stl_bytes), project_id=project_id
    )
    return _stream(stl_bytes, "model/stl", f"{project_id}.stl")


@router.get("/models/{model_id}", response_model=ModelMetadata)
async def get_model_metadata(
    model_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> dict:
    return await services.projects.get_model_metadata(user["id"], model_id)


@router.get("/models/{model_id}/download", response_model=None)
async def download_model_by_id(
    model_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> Response:
    asset = await services.projects.get_model_asset_by_id(user["id"], model_id)
    data = await services.storage.load(asset["glb_key"])
    if not data:
        raise NotFoundError("GLB file missing in storage")
    await services.usage.record(
        user["id"], "download", payload_bytes=len(data), project_id=str(asset["project_id"])
    )
    return _stream(data, "model/gltf-binary", asset.get("filename", "model.glb"))


@router.get("/projects/{project_id}/model/download-urls", response_model=ModelDownload)
async def model_download_url(
    project_id: str,
    user: dict = Depends(get_current_user_async),
    services: Services = Depends(get_services),
) -> ModelDownload:
    asset = await _load_asset(services, user["id"], project_id)
    public = services.storage.public_url(asset["glb_key"])
    return ModelDownload(
        url=public,
        filename=asset.get("filename", "model.glb"),
        content_type="model/gltf-binary",
    )

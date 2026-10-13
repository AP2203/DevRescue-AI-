"""Tests for AI model lifecycle, custom model service, and model metadata routes."""
from __future__ import annotations

import asyncio

from app.ai.base import ImageTo3DModel, ModelState
from app.ai.custom_model_adapter import Custom3DModelService
from app.ai.factory import create_ai_model, get_registered_models

# -- AI lifecycle ----------------------------------------------------------


def test_model_lifecycle_states():
    model = create_ai_model("mock")
    assert isinstance(model, ImageTo3DModel)

    status = model.get_status()
    assert status["name"] == "mock"
    assert status["state"] == ModelState.UNLOADED
    assert status["loaded"] is False

    model.load_model()
    status = model.get_status()
    assert status["state"] == ModelState.LOADED
    assert status["loaded"] is True
    assert status["loaded_at"] is not None

    # Load is idempotent
    model.load_model()
    assert model.get_status()["state"] == ModelState.LOADED

    model.unload_model()
    status = model.get_status()
    assert status["state"] == ModelState.UNLOADED
    assert status["loaded"] is False
    assert status["loaded_at"] is None


def test_factory_registers_custom_model():
    assert "custom" in get_registered_models()
    model = create_ai_model("custom")
    assert isinstance(model, Custom3DModelService)
    assert model.get_status()["name"] == "custom"
    assert model.get_status()["state"] == ModelState.UNLOADED


def test_factory_rejects_unknown_model():
    from app.ai.factory import ModelNotAvailableError

    try:
        create_ai_model("does-not-exist")
    except ModelNotAvailableError:
        return
    raise AssertionError("expected ModelNotAvailableError")


# -- Custom model service --------------------------------------------------


def test_custom_model_without_command_still_loads():
    model = Custom3DModelService(command=None)
    model.load_model()
    assert model.get_status()["state"] == ModelState.LOADED


def test_custom_model_command_failure(tmp_path):
    """A failing external command should surface as a RuntimeError."""
    import sys

    from tests.conftest import make_test_image

    script = tmp_path / "fail.py"
    script.write_text(
        "import sys\n"
        "input_path, output_dir = sys.argv[1], sys.argv[2]\n"
        "sys.stderr.write('boom')\n"
        "sys.exit(1)\n"
    )
    model = Custom3DModelService(
        command=f'"{sys.executable}" "{script}" {{input}} {{output}}'
    )

    img = tmp_path / "in.png"
    img.write_bytes(make_test_image("PNG"))

    async def run():
        await model.generate(img, tmp_path / "out", model_settings())

    try:
        asyncio.run(run())
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected generation to fail")


def model_settings():
    from app.ai.types import GenerationSettings

    return GenerationSettings(resolution=256)


# -- Model metadata endpoint ------------------------------------------------


def test_model_metadata_endpoint_requires_auth(client):
    assert client.get("/api/v1/models/000000000000000000000000").status_code == 401


def _insert_model_asset(client, auth_headers, upload):
    """Create a project + tiny GLB asset in DB + local storage (no slow pipeline)."""
    from app.core.object_id import make_object_id, to_object_id
    from app.models.model_asset import ModelAssetDocument
    from app.services.storage_service import get_storage

    created = client.post(
        "/api/v1/projects", headers=auth_headers, json={"name": "meta project"}
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    # Build a small valid GLB directly with trimesh.
    import trimesh

    glb_bytes = trimesh.creation.box(extents=[0.5, 0.5, 0.5]).export(file_type="glb")

    async def _seed():
        from app.db.mongodb import client as mongo_client
        from app.repositories.project_repo import ProjectRepository

        storage = get_storage()
        user_id = client.get("/api/v1/users/me", headers=auth_headers).json()["id"]
        glb_key = f"models/{user_id}/{project_id}/seed/model.glb"
        await storage.save(glb_key, glb_bytes, "model/gltf-binary")
        asset = ModelAssetDocument(
            user_id=to_object_id(user_id),
            project_id=to_object_id(project_id),
            job_id=make_object_id(),
            glb_key=glb_key,
            size_bytes=len(glb_bytes),
            stats={"vertices": 8, "faces": 12, "watertight": True},
        )

        _id = to_object_id(asset.id)
        result = await mongo_client["vision3d_test"]["models"].insert_one(
            asset.model_dump(by_alias=True) | {"_id": _id}
        )
        await ProjectRepository(mongo_client["vision3d_test"]).update_by_id(
            to_object_id(project_id),
            {
                "model_asset_id": _id,
                "status": "ready",
                "image_upload_id": to_object_id(upload["id"]),
            },
        )
        return project_id, str(result.inserted_id), user_id

    project_id, model_id, user_id = asyncio.run(_seed())
    return project_id, model_id, user_id


def test_model_metadata_and_download_by_id(client, auth_headers, second_user_headers, upload):
    project_id, model_id, _ = _insert_model_asset(client, auth_headers, upload)

    meta = client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
    assert meta.status_code == 200, meta.text
    body = meta.json()
    assert body["id"] == model_id
    assert body["project_id"] == project_id
    assert body["size_bytes"] > 0
    assert body["provider"] == "local"
    assert body["model_url"].startswith("http")
    assert body["stats"]["vertices"] == 8
    assert body["thumbnail_url"]  # project has an upload attached

    # Download by model id streams the GLB.
    glb = client.get(f"/api/v1/models/{model_id}/download", headers=auth_headers)
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"

    # Ownership: second user gets 404.
    assert client.get(f"/api/v1/models/{model_id}", headers=second_user_headers).status_code == 404
    assert (
        client.get(f"/api/v1/models/{model_id}/download", headers=second_user_headers).status_code
        == 404
    )


def test_model_metadata_not_found(client, auth_headers):
    bogus = "0123456789abcdef01234567"
    assert client.get(f"/api/v1/models/{bogus}", headers=auth_headers).status_code == 404

"""Tests for the AI 3D Quality Analyzer and its persistence + API surface."""

from __future__ import annotations

import asyncio
import io

import numpy as np

from app.ai.factory import create_ai_model
from app.ai.quality_analyzer import analyze_glb
from app.ai.types import GenerationSettings


def _glb(mesh) -> bytes:
    return mesh.export(file_type="glb")


def _codes(result) -> set:
    return {p.code for p in result.problems}


# ── Pure analyzer unit tests ───────────────────────────────────────────────


def test_watertight_box_scores_perfect_geometry():
    import trimesh

    result = analyze_glb(_glb(trimesh.creation.box(extents=[1, 1, 1])))
    by_name = {d.name: d.score for d in result.dimensions}
    assert by_name["geometry"] == 100.0
    assert by_name["normals"] == 100.0
    assert by_name["topology"] == 100.0
    # Watertight box: no holes / no non-manifold edges.
    assert "open_boundary_holes" not in _codes(result)
    assert "non_manifold_edges" not in _codes(result)
    assert "disconnected_components" not in _codes(result)
    assert result.stats_snapshot["boundary_edges"] == 0
    assert result.stats_snapshot["non_manifold_edges"] == 0
    assert result.stats_snapshot["disconnected_components"] == 1
    # Untextured box is flagged for missing texture, not for geometry.
    assert "no_texture" in _codes(result)


def test_holed_box_detects_open_boundary():
    import trimesh

    box = trimesh.creation.box(extents=[1, 1, 1])
    faces = np.array(list(box.faces)[:-2])
    holed = trimesh.Trimesh(vertices=box.vertices.copy(), faces=faces, process=False)
    result = analyze_glb(_glb(holed))

    assert "open_boundary_holes" in _codes(result)
    assert result.stats_snapshot["boundary_edges"] > 0
    by_name = {d.name: d.score for d in result.dimensions}
    assert by_name["geometry"] < 100.0


def test_non_manifold_edges_are_detected():
    import trimesh

    # Edge (0, 1) shared by 4 faces -> non-manifold.
    vertices = np.array(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]],
        dtype=float,
    )
    faces = np.array([[0, 1, 2], [0, 1, 3], [0, 1, 4], [0, 1, 5]])
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    result = analyze_glb(_glb(mesh))

    assert "non_manifold_edges" in _codes(result)
    assert result.stats_snapshot["non_manifold_edges"] > 0
    by_name = {d.name: d.score for d in result.dimensions}
    assert by_name["topology"] < 100.0
    assert by_name["mesh_errors"] < 100.0


def test_disconnected_components_are_counted():
    import trimesh

    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box().apply_translation([0, 0, 0]))
    scene.add_geometry(trimesh.creation.box().apply_translation([5, 5, 5]))
    result = analyze_glb(_glb(scene))

    assert result.stats_snapshot["disconnected_components"] == 2
    assert "disconnected_components" in _codes(result)


def test_empty_scene_scores_zero():
    result = analyze_glb(b"not-a-glb")
    assert result.overall_score == 0.0
    assert "load_failed" in _codes(result)


# ── Analyzer on a generated GLB model ──────────────────────────────────────


def _test_image(tmp_path) -> str:
    from tests.conftest import make_test_image

    p = tmp_path / "in.png"
    p.write_bytes(make_test_image("PNG", width=48, height=48))
    return str(p)


def test_analyzer_on_mock_generated_glb(tmp_path):
    """End-to-end: mock pipeline generates a GLB, analyzer reports on it."""
    import trimesh

    model = create_ai_model("mock")
    settings = GenerationSettings(resolution=48, formats=["glb"])
    result = asyncio.run(model.generate(_test_image(tmp_path), tmp_path / "out", settings))

    assert result.glb_bytes[:4] == b"glTF"
    report = analyze_glb(result.glb_bytes)

    # The mock model is watertight, textured, with valid normals.
    assert report.overall_score >= 80.0
    assert report.stats_snapshot["has_texture"] is True
    assert report.stats_snapshot["has_uvs"] is True
    assert report.stats_snapshot["has_normals"] is True
    assert report.stats_snapshot["watertight_count"] == report.stats_snapshot["mesh_count"]
    by_name = {d.name: d.score for d in report.dimensions}
    assert by_name["geometry"] == 100.0
    assert by_name["texture"] == 100.0
    assert "non_manifold_edges" not in _codes(report)
    assert "open_boundary_holes" not in _codes(report)

    # Round-trip: the GLB is parseable by trimesh too.
    loaded = trimesh.load(io.BytesIO(result.glb_bytes), file_type="glb", force="scene")
    assert len(loaded.geometry) > 0


# ── Persistence + API surface ──────────────────────────────────────────────


def _seed_model_asset(client, auth_headers, upload, glb_bytes):
    """Create a project + GLB asset in DB + local storage (mirrors test_models.py)."""
    from app.core.object_id import make_object_id, to_object_id
    from app.models.model_asset import ModelAssetDocument
    from app.services.storage_service import get_storage

    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "quality project"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

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
        await mongo_client["vision3d_test"]["models"].insert_one(
            asset.model_dump(by_alias=True) | {"_id": _id}
        )
        await ProjectRepository(mongo_client["vision3d_test"]).update_by_id(
            to_object_id(project_id),
            {"model_asset_id": _id, "status": "ready", "image_upload_id": to_object_id(upload["id"])},
        )
        return project_id

    return asyncio.run(_seed())


def test_quality_analysis_persists_report(client, auth_headers, second_user_headers, upload):
    import trimesh

    glb_bytes = trimesh.creation.box(extents=[1, 1, 1]).export(file_type="glb")
    project_id = _seed_model_asset(client, auth_headers, upload, glb_bytes)

    # No report yet.
    missing = client.get(f"/api/v1/projects/{project_id}/quality-report", headers=auth_headers)
    assert missing.status_code == 404

    # Run analysis -> persists a report.
    ran = client.post(f"/api/v1/projects/{project_id}/quality-analysis", headers=auth_headers)
    assert ran.status_code == 201, ran.text
    body = ran.json()
    assert body["project_id"] == project_id
    assert body["overall_score"] > 0
    assert {d["name"] for d in body["dimensions"]} >= {
        "geometry",
        "texture",
        "topology",
        "completeness",
    }
    assert isinstance(body["recommendations"], list)
    assert "stats_snapshot" in body

    # Report is retrievable.
    fetched = client.get(f"/api/v1/projects/{project_id}/quality-report", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == body["id"]

    # Ownership enforced.
    assert (
        client.get(f"/api/v1/projects/{project_id}/quality-report", headers=second_user_headers).status_code
        == 404
    )


def test_quality_report_missing_model_is_404(client, auth_headers):

    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "no model project"})
    assert created.status_code == 201
    project_id = created.json()["id"]

    ran = client.post(f"/api/v1/projects/{project_id}/quality-analysis", headers=auth_headers)
    assert ran.status_code == 404

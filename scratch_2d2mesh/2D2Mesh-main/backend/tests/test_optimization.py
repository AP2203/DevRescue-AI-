"""Tests for Model Optimization pipeline and API."""
from __future__ import annotations

import io
import trimesh
from app.ai.optimizer import optimize_glb
from tests.test_projects import _process_next_job


def _create_sample_glb() -> bytes:
    mesh = trimesh.creation.box(extents=[1.0, 1.0, 1.0])
    for _ in range(3):
        mesh = mesh.subdivide()
    buf = io.BytesIO()
    mesh.export(buf, file_type="glb")
    return buf.getvalue()


def test_optimize_glb_profiles():
    glb_bytes = _create_sample_glb()
    assert len(glb_bytes) > 0

    # 1. Web profile
    web_res = optimize_glb(glb_bytes, profile="web")
    assert web_res.profile == "web"
    assert web_res.after_stats["faces"] < web_res.before_stats["faces"]
    assert "reduce_polygons_60pct" in web_res.operations
    assert len(web_res.optimized_glb_bytes) > 0

    # 2. Game profile
    game_res = optimize_glb(glb_bytes, profile="game")
    assert game_res.profile == "game"
    assert game_res.after_stats["faces"] < web_res.after_stats["faces"]
    assert "reduce_polygons_75pct" in game_res.operations

    # 3. Print profile
    print_res = optimize_glb(glb_bytes, profile="print")
    assert print_res.profile == "print"
    assert print_res.stl_bytes is not None
    assert len(print_res.stl_bytes) > 0
    assert "scaled_to_mm" in print_res.operations
    assert "stl_export" in print_res.operations


def test_optimize_api_end_to_end(client, auth_headers, upload, db_client):
    # 1. Create project & generate model
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "opt project"})
    assert created.status_code == 201
    project_id = created.json()["id"]

    job_response = client.post(
        f"/api/v1/jobs/projects/{project_id}/generate",
        headers=auth_headers,
        json={"upload_id": upload["id"], "settings": {"model": "mock", "resolution": 256}},
    )
    assert job_response.status_code == 201
    _process_next_job(client.app)

    # 2. Call optimize endpoint for web
    res = client.post(
        f"/api/v1/projects/{project_id}/optimize",
        headers=auth_headers,
        json={"profile": "web", "set_active": True},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["profile"] == "web"
    assert "asset_id" in data
    assert "before_stats" in data
    assert "after_stats" in data
    assert "download_url" in data
    assert data["download_url"] is not None

    # Verify project model was set to active
    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project["model_asset_id"] == data["asset_id"]

    # 3. Call optimize endpoint for print profile
    print_res = client.post(
        f"/api/v1/projects/{project_id}/optimize",
        headers=auth_headers,
        json={"profile": "print", "set_active": False},
    )
    assert print_res.status_code == 201, print_res.text
    print_data = print_res.json()
    assert print_data["profile"] == "print"
    assert "stl_download_url" in print_data
    assert print_data["stl_download_url"] is not None

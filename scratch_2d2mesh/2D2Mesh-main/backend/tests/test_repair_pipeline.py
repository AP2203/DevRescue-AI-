"""Integration tests for the AI Auto Repair pipeline."""
from __future__ import annotations

import asyncio
from bson import ObjectId

from tests.conftest import make_test_image
from tests.test_projects import _process_next_job


def test_repair_pipeline_end_to_end(client, auth_headers, upload, db_client):
    # 1. Create a project
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "repair project"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    # 2. Trigger model generation
    job_response = client.post(
        f"/api/v1/jobs/projects/{project_id}/generate",
        headers=auth_headers,
        json={"upload_id": upload["id"], "settings": {"model": "mock", "resolution": 256}},
    )
    assert job_response.status_code == 201, job_response.text
    job_id = _process_next_job(client.app)

    # Verify project is ready
    project_before = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project_before["status"] == "ready"
    original_asset_id = project_before["model_asset_id"]
    assert original_asset_id is not None

    # 3. Trigger a quality analysis first (optional but ensures a starting report exists)
    qa_response = client.post(
        f"/api/v1/projects/{project_id}/quality-analysis",
        headers=auth_headers,
    )
    assert qa_response.status_code == 201, qa_response.text
    assert qa_response.json()["overall_score"] is not None

    # 4. Trigger the Auto Repair endpoint
    repair_response = client.post(
        f"/api/v1/projects/{project_id}/repair",
        headers=auth_headers,
        json={
            "fill_holes": True,
            "fix_normals": True,
            "remove_duplicates": True,
            "remove_degenerate": True,
        }
    )
    assert repair_response.status_code == 201, repair_response.text
    repair_data = repair_response.json()

    # 5. Verify the repair response structure
    assert "asset_id" in repair_data
    assert "before_stats" in repair_data
    assert "after_stats" in repair_data
    assert "operations_applied" in repair_data
    assert "before_score" in repair_data
    assert "after_score" in repair_data
    assert "problems_found" in repair_data
    assert "problems_fixed" in repair_data

    repaired_asset_id = repair_data["asset_id"]
    assert repaired_asset_id != original_asset_id

    # 6. Verify project model reference has mutated
    project_after = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project_after["model_asset_id"] == repaired_asset_id

    # 7. Check edit history
    history_response = client.get(f"/api/v1/projects/{project_id}/edit-history", headers=auth_headers)
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 1
    repair_log = [item for item in history if item["operation_type"] == "repair"][0]
    assert repair_log["original_asset_id"] == original_asset_id
    assert repair_log["result_asset_id"] == repaired_asset_id
    assert "before_score" in repair_log["meta"]
    assert "after_score" in repair_log["meta"]

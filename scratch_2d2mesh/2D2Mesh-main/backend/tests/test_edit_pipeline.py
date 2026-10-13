"""Integration tests for the NL-Edit pipeline: version history + undo/redo."""
from __future__ import annotations

from tests.test_projects import _process_next_job


def _create_ready_project(client, auth_headers, upload) -> str:
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "edit project"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    job_response = client.post(
        f"/api/v1/jobs/projects/{project_id}/generate",
        headers=auth_headers,
        json={"upload_id": upload["id"], "settings": {"model": "mock", "resolution": 256}},
    )
    assert job_response.status_code == 201, job_response.text
    _process_next_job(client.app)

    detail = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert detail["status"] == "ready"
    assert detail["edit_version"] == 0
    return project_id


def _edit(client, auth_headers, project_id, command):
    resp = client.post(f"/api/v1/projects/{project_id}/edit", headers=auth_headers, json={"command": command})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_edit_pipeline_versioning_and_undo_redo(client, auth_headers, upload):
    project_id = _create_ready_project(client, auth_headers, upload)
    project_before = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    original_asset_id = project_before["model_asset_id"]

    # 1. First edit → version 1
    edit1 = _edit(client, auth_headers, project_id, "Make it red")
    assert edit1["version"] == 1
    assert edit1["parsed_command"]["operations"][0]["type"] == "change_material"
    assert "quality_score" in edit1

    after1 = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert after1["edit_version"] == 1
    assert after1["model_asset_id"] == edit1["asset_id"]
    assert after1["model_asset_id"] != original_asset_id

    # 2. Second edit → version 2
    edit2 = _edit(client, auth_headers, project_id, "Make it blue")
    assert edit2["version"] == 2

    # 3. Versions timeline
    versions = client.get(f"/api/v1/projects/{project_id}/edit/versions", headers=auth_headers).json()
    assert versions["current_version"] == 2
    assert versions["max_version"] == 2
    assert versions["can_undo"] is True
    assert versions["can_redo"] is False
    assert versions["versions"][0]["label"] == "Original"
    assert [v["label"] for v in versions["versions"]] == ["Original", "Edit 1", "Edit 2"]

    # 4. Undo twice → back to Original (version 0, model = original asset)
    undo1 = client.post(f"/api/v1/projects/{project_id}/edit/undo", headers=auth_headers).json()
    assert undo1["version"] == 1
    undo2 = client.post(f"/api/v1/projects/{project_id}/edit/undo", headers=auth_headers).json()
    assert undo2["version"] == 0

    at_original = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert at_original["edit_version"] == 0
    assert at_original["model_asset_id"] == original_asset_id

    # 5. Undo at version 0 → rejected
    resp = client.post(f"/api/v1/projects/{project_id}/edit/undo", headers=auth_headers)
    assert resp.status_code == 400

    # 6. Redo twice → back to version 2
    redo1 = client.post(f"/api/v1/projects/{project_id}/edit/redo", headers=auth_headers).json()
    assert redo1["version"] == 1
    redo2 = client.post(f"/api/v1/projects/{project_id}/edit/redo", headers=auth_headers).json()
    assert redo2["version"] == 2
    assert redo2["can_redo"] is False

    at_latest = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert at_latest["edit_version"] == 2
    assert at_latest["model_asset_id"] == edit2["asset_id"]

    # 7. Redo at latest → rejected
    resp = client.post(f"/api/v1/projects/{project_id}/edit/redo", headers=auth_headers)
    assert resp.status_code == 400

    # 8. Edit history shows all entries with version numbers
    history = client.get(f"/api/v1/projects/{project_id}/edit-history", headers=auth_headers).json()
    ai_edits = [h for h in history if h["operation_type"] == "ai_edit"]
    assert len(ai_edits) == 2
    assert {h["version"] for h in ai_edits} == {1, 2}
    assert all(h["original_asset_id"] and h["result_asset_id"] for h in ai_edits)


def test_new_edit_truncates_redo_stack(client, auth_headers, upload):
    project_id = _create_ready_project(client, auth_headers, upload)

    _edit(client, auth_headers, project_id, "Make it red")   # v1
    _edit(client, auth_headers, project_id, "Make it blue")  # v2

    # Undo to v1
    undo = client.post(f"/api/v1/projects/{project_id}/edit/undo", headers=auth_headers).json()
    assert undo["version"] == 1

    # New edit while v1 is active → v2 gets replaced, no redo target remains
    edit3 = _edit(client, auth_headers, project_id, "Make it green")
    assert edit3["version"] == 2

    versions = client.get(f"/api/v1/projects/{project_id}/edit/versions", headers=auth_headers).json()
    assert versions["current_version"] == 2
    assert versions["max_version"] == 2
    assert versions["can_redo"] is False

    # The old v2 entry was deleted; a fresh v2 exists
    history = client.get(f"/api/v1/projects/{project_id}/edit-history", headers=auth_headers).json()
    ai_edits = [h for h in history if h["operation_type"] == "ai_edit"]
    assert len(ai_edits) == 2
    assert all(h["version"] in (1, 2) for h in ai_edits)


def test_edit_requires_generated_model(client, auth_headers):
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "no model yet"})
    project_id = created.json()["id"]

    resp = client.post(f"/api/v1/projects/{project_id}/edit", headers=auth_headers, json={"command": "Make it red"})
    assert resp.status_code == 404

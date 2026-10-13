"""Integration tests for files, ownership, and the full generation pipeline."""
from __future__ import annotations

import asyncio

from tests.conftest import make_test_image


def test_upload_validation(client, auth_headers):
    assert (
        client.post(
            "/api/v1/uploads",
            headers=auth_headers,
            files={"file": ("evil.txt", b"not an image", "text/plain")},
        ).status_code
        in (400, 415, 422)
    )
    bad_mime = client.post(
        "/api/v1/uploads",
        headers=auth_headers,
        files={"file": ("photo.jpg", make_test_image("PNG"), "image/jpeg")},
    )
    assert bad_mime.status_code in (400, 415)


def test_webp_upload_supported(client, auth_headers, sample_webp):
    response = client.post(
        "/api/v1/uploads",
        headers=auth_headers,
        files={"file": ("photo.webp", sample_webp, "image/webp")},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "image/webp"
    assert response.json()["width"] == 64
    assert response.json()["url"]


def test_project_creation_and_rename(client, auth_headers):
    created = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": "My first project", "description": "A test project"},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    assert created.json()["status"] == "no_model"

    renamed = client.patch(
        f"/api/v1/projects/{project_id}/rename", headers=auth_headers, json={"name": "Renamed"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Renamed"

    listed = client.get("/api/v1/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


def test_project_ownership_enforced(client, auth_headers, second_user_headers):
    created = client.post(
        "/api/v1/projects", headers=auth_headers, json={"name": "private project"}
    )
    project_id = created.json()["id"]

    assert (
        client.get(f"/api/v1/projects/{project_id}", headers=second_user_headers).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/projects/{project_id}/rename",
            headers=second_user_headers,
            json={"name": "hacked"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/projects/{project_id}", headers=second_user_headers).status_code
        == 404
    )
    # Owner can still delete it
    assert client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers).status_code == 204


def test_delete_project(client, auth_headers):
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "to delete"})
    project_id = created.json()["id"]
    assert client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).status_code == 404


def _process_next_job(app):
    from app.services.storage_service import get_storage
    from app.workers.processor import JobProcessor

    db = app.state.db

    async def run():
        processor = JobProcessor(db, get_storage(), poll_interval=1.0, stale_minutes=30)
        job = await processor.jobs.claim_next("test-worker", 30)
        assert job is not None, "expected a queued job"
        await processor._process(job)
        return str(job["_id"])

    return asyncio.run(run())


def test_end_to_end_generation_pipeline(client, auth_headers, upload, second_user_headers, db_client):
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "gen project"})
    project_id = created.json()["id"]

    job_response = client.post(
        f"/api/v1/jobs/projects/{project_id}/generate",
        headers=auth_headers,
        json={"upload_id": upload["id"], "settings": {"model": "mock", "resolution": 256}},
    )
    assert job_response.status_code == 201, job_response.text
    job = job_response.json()
    assert job["status"] == "queued"
    assert job["ai_model"] == "mock"

    # Run the (normally background) worker step synchronously.
    job_id = _process_next_job(client.app)

    done = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
    assert done.status_code == 200
    assert done.json()["status"] == "succeeded"
    assert done.json()["metrics"]["vertices"] > 0

    project = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers).json()
    assert project["status"] == "ready"
    assert project["model_summary"]["size_bytes"] > 0
    assert project["model_summary"]["stats"]["vertices"] > 0

    # Download GLB and GLTF
    glb = client.get(f"/api/v1/projects/{project_id}/model", headers=auth_headers)
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"

    gltf = client.get(f"/api/v1/projects/{project_id}/model/gltf", headers=auth_headers)
    assert gltf.status_code == 200
    assert b'"asset"' in gltf.content

    # Ownership: second user cannot download the model
    assert client.get(f"/api/v1/projects/{project_id}/model", headers=second_user_headers).status_code == 404


def test_retry_generation(client, auth_headers, upload):
    created = client.post("/api/v1/projects", headers=auth_headers, json={"name": "retry project"})
    project_id = created.json()["id"]
    job = client.post(
        f"/api/v1/jobs/projects/{project_id}/generate",
        headers=auth_headers,
        json={"upload_id": upload["id"], "settings": {"resolution": 256}},
    ).json()
    retried = client.post(f"/api/v1/jobs/{job['id']}/retry", headers=auth_headers)
    assert retried.status_code == 200
    assert retried.json()["job"]["id"] != job["id"]
    assert retried.json()["job"]["status"] == "queued"


def test_upload_ownership_enforced(client, auth_headers, second_user_headers, upload):
    assert (
        client.get(f"/api/v1/uploads/{upload['id']}", headers=second_user_headers).status_code
        == 400
    )


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["ai_model"] == "mock"

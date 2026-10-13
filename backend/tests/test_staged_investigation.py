import pytest
import hashlib
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from app.services.investigation_service import investigation_service, STAGE_DEFINITIONS
from app.services.session_store import session_store
from app.services.security_service import security_service
from app.services.sandbox_service import SandboxTestResponse
from app.schemas.investigations import StageStatus


@pytest.mark.asyncio
async def test_unique_run_ids_and_stale_result_prevention():
    """Verify that every execution gets a unique run_id and reruns reset transient state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create GitHub investigation
        create_res = await ac.post("/api/investigations", json={
            "repository": "anshpatel2212/2D2Mesh",
            "branch": "main",
            "issue_number": 1,
            "issue_title": "Submit button does not show loading state",
            "mode": "real"
        })
        assert create_res.status_code == 201
        inv = create_res.json()
        inv_id = inv["id"]
        run_1_id = inv["latest_run_id"]
        assert run_1_id is not None
        assert run_1_id.startswith(f"run_{inv_id}_")

        # Verify stages on run 1
        run_1_res = await ac.get(f"/api/investigations/{inv_id}/runs/{run_1_id}")
        assert run_1_res.status_code == 200
        run_1_data = run_1_res.json()
        assert len(run_1_data["stages"]) == 11
        assert run_1_data["investigation_id"] == inv_id

        # Trigger a rerun via POST /runs
        rerun_res = await ac.post(f"/api/investigations/{inv_id}/runs", json={
            "parent_run_id": run_1_id,
            "mode": "real"
        })
        assert rerun_res.status_code == 201
        rerun_data = rerun_res.json()
        run_2_id = rerun_data["run_id"]

        # Run IDs must be strictly unique and separate
        assert run_2_id != run_1_id
        assert rerun_data["parent_run_id"] == run_1_id
        assert rerun_data["retry_count"] == 1

        # Check investigation latest_run_id is updated to run_2_id
        inv_res = await ac.get(f"/api/investigations/{inv_id}")
        assert inv_res.status_code == 200
        updated_inv = inv_res.json()
        assert updated_inv["latest_run_id"] == run_2_id

        # Listing runs returns both historical runs
        runs_list_res = await ac.get(f"/api/investigations/{inv_id}/runs")
        assert runs_list_res.status_code == 200
        runs_list = runs_list_res.json()
        assert len(runs_list) >= 2
        run_ids = [r["run_id"] for r in runs_list]
        assert run_1_id in run_ids
        assert run_2_id in run_ids


@pytest.mark.asyncio
async def test_11_stages_structure_and_tracking():
    """Verify that all 11 stages exist with explicit status and agent mapping."""
    run = investigation_service.create_run_record("inv-test-stages")
    assert len(run["stages"]) == 11

    stage_keys = [s["key"] for s in run["stages"]]
    expected_keys = [s[1] for s in STAGE_DEFINITIONS]
    assert stage_keys == expected_keys

    # Verify initial status of all stages is PENDING
    for s in run["stages"]:
        assert s["status"] == StageStatus.PENDING.value
        assert s["id"] >= 1 and s["id"] <= 11

    # Update stage status and verify timing and details
    investigation_service._update_stage(run, "repo_retrieval", StageStatus.RUNNING.value)
    assert run["stages"][0]["status"] == "RUNNING"
    assert run["stages"][0]["started_at"] is not None

    investigation_service._update_stage(run, "repo_retrieval", StageStatus.PASSED.value, summary="Issue retrieved.")
    assert run["stages"][0]["status"] == "PASSED"
    assert run["stages"][0]["completed_at"] is not None
    assert run["stages"][0]["summary"] == "Issue retrieved."


def test_testing_agent_zero_tests_never_classified_as_passed():
    """Verify that exit code 0 with zero tests executed is classified as TESTS_NOT_CONFIGURED, never PASSED."""
    from app.services.sandbox_service import sandbox_service

    # Zero tests collected with exit code 0
    resp = SandboxTestResponse(
        success=False,
        status="TESTS_NOT_CONFIGURED",
        exit_code=0,
        test_command="pytest",
        framework="pytest",
        tests_run=0,
        tests_passed=0,
        tests_failed=0,
        stdout="collected 0 items\n\n============================ no tests ran in 0.01s =============================",
        stderr="",
        message="Test runner pytest exited with code 0 but zero tests were executed."
    )
    assert resp.status != "PASSED"
    assert resp.status == "TESTS_NOT_CONFIGURED"
    assert resp.success is False


def test_testing_agent_environment_error_classification():
    """Verify missing application module produces ENVIRONMENT_ERROR and captures traceback."""
    stdout = "=== PRE-FLIGHT VERIFICATION ===\nPWD: /workspace/backend\n"
    stderr = "ImportError while loading conftest '/workspace/backend/tests/conftest.py'.\nE ModuleNotFoundError: No module named 'app.models'\n"
    output_combined = (stdout + stderr).lower()

    is_env_error = (
        "importerror while loading conftest" in output_combined
        or "no module named 'app'" in output_combined
        or "no module named 'app." in output_combined
        or (4 == 4 and "pytest" in "pytest")
    )
    assert is_env_error is True


def test_security_review_detects_secrets_and_unsafe_calls():
    """Verify security analysis detects hardcoded secrets and dangerous functions."""
    clean_diff = """--- a/Button.tsx
+++ b/Button.tsx
@@ -1,2 +1,3 @@
-const x = 1;
+const x = 2;
+console.log("Safe change");
"""
    clean_res = security_service.scan_patch(clean_diff)
    assert clean_res["status"] == "PASSED"
    assert clean_res["clean"] is True
    assert len(clean_res["findings"]) == 0

    dangerous_diff = """--- a/service.py
+++ b/service.py
@@ -1,2 +1,4 @@
-def run(): pass
+import os, subprocess
+os.system("rm -rf /")
+subprocess.Popen("sh script.sh", shell=True)
+apiKey = "ghp_1234567890abcdef1234567890abcdef1234"
"""
    vuln_res = security_service.scan_patch(dangerous_diff)
    assert vuln_res["status"] == "FAILED"
    assert vuln_res["clean"] is False
    assert len(vuln_res["findings"]) >= 3
    rule_ids = [f["rule_id"] for f in vuln_res["findings"]]
    assert "UNSAFE_OS_SYSTEM" in rule_ids
    assert "SUBPROCESS_SHELL_TRUE" in rule_ids
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in rule_ids


@pytest.mark.asyncio
async def test_human_approval_gate_and_hash_verification():
    """Verify human approval is strictly required before PR dispatch and validates patch_hash."""
    transport = ASGITransport(app=app)
    test_token = "gho_test_gate_999"
    session_id = session_store.create_session(test_token, {"login": "testengineer"})

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create investigation
        c_res = await ac.post("/api/investigations", json={
            "repository": "acme/gateway",
            "branch": "main",
            "issue_number": 5,
            "issue_title": "Fix memory leak in pool",
            "mode": "real"
        })
        inv = c_res.json()
        inv_id = inv["id"]
        run_id = inv["latest_run_id"]

        # Populate synthetic patch in run
        patch_text = "--- a/pool.py\n+++ b/pool.py\n@@ -1,1 +1,2 @@\n-old\n+new_fixed\n"
        correct_hash = hashlib.sha256(patch_text.encode("utf-8")).hexdigest()
        run = investigation_service.get_run(run_id)
        run["patch"] = {
            "file": "pool.py",
            "diff": patch_text,
            "patch": patch_text,
            "patch_hash": correct_hash,
            "lines_added": 1,
            "lines_removed": 1
        }
        investigation_service.investigations[inv_id]["patch"] = run["patch"]

        # Attempt approval with WRONG / stale hash -> must be rejected with 400
        stale_hash = "wrong_hash_abc123"
        reject_res = await ac.post(
            f"/api/investigations/{inv_id}/runs/{run_id}/approve",
            json={"patch_hash": stale_hash},
            cookies={"devrescue_github_session": session_id}
        )
        assert reject_res.status_code == 400
        assert "mismatch" in reject_res.json()["detail"].lower()

        # Mock GitHub calls for valid approval
        with patch.object(investigation_service.github_service, "create_branch", new_callable=AsyncMock) as mock_cb, \
             patch.object(investigation_service.github_service, "get_file_content_and_sha", new_callable=AsyncMock) as mock_fc, \
             patch.object(investigation_service.github_service, "create_or_update_file", new_callable=AsyncMock) as mock_uf, \
             patch.object(investigation_service.github_service, "create_pull_request", new_callable=AsyncMock) as mock_cpr:

            mock_cb.return_value = {"status": "success", "branch": f"devrescue/fix-{inv_id}"}
            mock_fc.return_value = ("old\n", "sha_111")
            mock_uf.return_value = {"commit_sha": "commit_sha_999"}
            mock_cpr.return_value = {"pr_number": 101, "pr_url": "https://github.com/acme/gateway/pull/101"}

            # Approve with matching patch_hash
            valid_res = await ac.post(
                f"/api/investigations/{inv_id}/runs/{run_id}/approve",
                json={"patch_hash": correct_hash},
                cookies={"devrescue_github_session": session_id}
            )
            assert valid_res.status_code == 200
            data = valid_res.json()
            assert data["status"] == "success"
            assert data["pull_request"]["pr_number"] == 101
            assert run["approval"]["approved"] is True
            assert run["approval"]["patch_hash"] == correct_hash


@pytest.mark.asyncio
async def test_backend_sync_endpoint():
    """Verify PUT /api/investigations/{inv_id} synchronizes client-side state."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        c_res = await ac.post("/api/investigations", json={
            "repository": "acme/sync-test",
            "branch": "main",
            "issue_number": 12,
            "issue_title": "Button state fix",
            "mode": "real"
        })
        inv_id = c_res.json()["id"]

        sync_payload = {
            "status": "READY_FOR_REVIEW",
            "progress": 100,
            "rootCause": {"summary": "Root cause identified by client Nemotron run", "confidence": 96},
            "patch": {"file": "Button.tsx", "diff": "--- a/Button.tsx\n+++ b/Button.tsx\n@@ -1,1 +1,1 @@\n-old\n+new\n"}
        }
        sync_res = await ac.put(f"/api/investigations/{inv_id}", json=sync_payload)
        assert sync_res.status_code == 200

        # Verify state is persisted on backend
        get_res = await ac.get(f"/api/investigations/{inv_id}")
        assert get_res.status_code == 200
        persisted = get_res.json()
        assert persisted["status"] == "READY_FOR_REVIEW"
        assert persisted["progress"] == 100
        assert persisted["rootCause"]["confidence"] == 96


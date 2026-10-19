import pytest
import os
import tempfile
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.sandbox import SandboxTestResponse
from app.schemas.nemotron import NemotronInvestigateResponse, EvidenceItem
from app.services.diff_validator import diff_validator
from app.services.patch_service import patch_service, is_test_file_path
from app.services.sandbox_service import SandboxService, PrepDependenciesResult
from app.schemas.test_strategy import TestStrategyContract


def test_is_test_file_path_helper():
    assert is_test_file_path("tests/test_feature.py") is True
    assert is_test_file_path("test/test_feature.py") is True
    assert is_test_file_path("src/__tests__/feature.test.js") is True
    assert is_test_file_path("backend/tests/unit/test_calc.py") is True
    assert is_test_file_path("src/components/Button.spec.tsx") is True
    assert is_test_file_path("src/utils_test.py") is True
    assert is_test_file_path("src/components/Button.jsx") is False
    assert is_test_file_path("backend/app/main.py") is False


def test_diff_validator_accepts_new_synthesized_test_file():
    original_code = "def add(a, b):\n    return a - b\n"
    file_contents = {"math_util.py": original_code}
    allowed_files = ["math_util.py"]  # Original scope does not list test file

    patch_with_test = (
        "--- a/math_util.py\n"
        "+++ b/math_util.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
        "--- /dev/null\n"
        "+++ b/tests/test_math.py\n"
        "@@ -0,0 +1,4 @@\n"
        "+from math_util import add\n"
        "+\n"
        "+def test_add():\n"
        "+    assert add(2, 3) == 5\n"
    )

    result = diff_validator.validate_and_apply(
        patch=patch_with_test,
        file_contents=file_contents,
        allowed_files=allowed_files
    )

    assert result.is_valid is True
    assert "math_util.py" in result.files_changed
    assert "tests/test_math.py" in result.files_changed
    assert "def test_add():" in result.applied_contents["tests/test_math.py"]


@pytest.mark.asyncio
async def test_patch_service_injects_synthesis_instructions_when_no_tests_found():
    inv_response = NemotronInvestigateResponse(
        root_cause="Bug in calculation logic",
        confidence=0.95,
        affected_files=["app/calc.py"],
        affected_functions=["compute"],
        evidence=[EvidenceItem(file="app/calc.py", line=10, reason="Incorrect addition")],
        proposed_fix="Fix addition",
        test_strategy="NO_TESTS_FOUND"
    )

    fake_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        "--- a/app/calc.py\n"
        "+++ b/app/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        " def compute(x):\n"
        "-    return x - 1\n"
        "+    return x + 1\n"
        "--- /dev/null\n"
        "+++ b/tests/test_calc.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def test_compute():\n"
        "+    assert True\n"
    )
    fake_response = MagicMock(choices=[mock_choice])
    fake_client.chat.completions.create = AsyncMock(return_value=fake_response)

    with patch.object(patch_service.nemotron_service, "get_client", return_value=fake_client), \
         patch.object(patch_service.github_service, "get_file_content_and_sha", AsyncMock(return_value=("def compute(x):\n    return x - 1\n", "sha123"))), \
         patch.object(patch_service.github_service, "get_file_sha", AsyncMock(return_value="sha123")):

        contract = TestStrategyContract(
            subproject_path="",
            container_workdir="/workspace",
            language="python",
            test_framework="pytest",
            discovered_test_files=[],
            test_files_count=0,
            test_command="pytest",
            docker_image="devrescue-python-test:3.11",
            status="NO_TESTS_FOUND",
            confidence=0.8,
            supporting_evidence=["Zero tests discovered"]
        )

        res = await patch_service.synthesize_patch(
            owner="testowner",
            repo="testrepo",
            issue_number=1,
            investigation=inv_response,
            branch="main",
            test_strategy=contract
        )

        assert res.success is True
        assert res.synthesized_test_included is True
        assert "tests/test_calc.py" in res.files_changed

        # Verify that prompt received the synthesis requirement
        call_args = fake_client.chat.completions.create.call_args[1]
        user_msg = next(m["content"] for m in call_args["messages"] if m["role"] == "user")
        assert "CRITICAL REQUIREMENT (NO EXISTING TESTS FOUND)" in user_msg
        assert "NO_TESTS_FOUND" in user_msg


@pytest.mark.asyncio
async def test_sandbox_execution_sets_verified_via_synthesized_test(tmp_path):
    service = SandboxService()
    valid_patch = (
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def hello():\n"
        "-    return 'bye'\n"
        "+    return 'hello'\n"
        "--- /dev/null\n"
        "+++ b/tests/test_app.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+def test_hello():\n"
        "+    assert True\n"
    )

    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "app.py").write_text("def hello():\n    return 'bye'\n", encoding="utf-8")
    tests_dir = ws / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text("def test_hello():\n    assert True\n", encoding="utf-8")

    async def mock_download(*args, **kwargs):
        dest = kwargs.get("destination_dir") or (args[4] if len(args) > 4 else None)
        if dest:
            shutil.copytree(str(ws), dest, dirs_exist_ok=True)
        return True

    mock_prep = AsyncMock(return_value=PrepDependenciesResult("devrescue-python-test:3.11", None))
    mock_exec = AsyncMock(return_value=(0, "collected 1 item\ntests/test_app.py . [100%]\n1 passed in 0.15s", ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", mock_prep), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["app.py", "tests/test_app.py"]), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.tests_run == 1
        assert res.tests_passed == 1
        assert res.tests_failed == 0
        assert res.verified_via_synthesized_test is True
        assert "verified via AI-synthesized unit test" in res.message


def test_sandbox_invariant_enforces_zero_tests_cannot_be_passed():
    with pytest.raises(ValueError, match="status cannot be 'PASSED' when tests_run is 0 or None"):
        SandboxTestResponse(
            success=True,
            status="PASSED",
            tests_run=0,
            tests_passed=0,
            tests_failed=0,
            verified_via_synthesized_test=True
        )


@pytest.mark.asyncio
async def test_investigation_service_metadata_propagation():
    from app.services.investigation_service import investigation_service

    inv_id = "test-inv-synth-1"
    run_id = "test-run-synth-1"

    investigation_service.investigations[inv_id] = {
        "id": inv_id,
        "owner": "testowner",
        "repo_name": "testrepo",
        "branch": "main",
        "issue_number": 1,
        "issue_title": "Bug with zero tests"
    }

    investigation_service.runs[run_id] = {
        "id": run_id,
        "investigation_id": inv_id,
        "status": "IN_PROGRESS",
        "stages": [
            {"id": i, "key": k, "name": k, "status": "PENDING", "summary": ""}
            for i, k in enumerate([
                "repo_retrieval", "repo_analysis", "root_cause", "patch_synthesis",
                "diff_validation", "dependency_prep", "test_execution", "security_review",
                "risk_assessment", "human_approval", "pr_dispatch"
            ], start=1)
        ],
        "logs": []
    }

    mock_inv_res = NemotronInvestigateResponse(
        root_cause="Missing check",
        confidence=0.9,
        affected_files=["app.py"],
        affected_functions=["fn"],
        evidence=[],
        proposed_fix="Add check",
        test_strategy="NO_TESTS_FOUND"
    )

    from app.schemas.nemotron import NemotronRealPatchResponse, PatchValidationDetails

    mock_patch_res = NemotronRealPatchResponse(
        success=True,
        patch=(
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def fn():\n"
            "-    return False\n"
            "+    return True\n"
            "--- /dev/null\n"
            "+++ b/tests/test_fn.py\n"
            "@@ -0,0 +1,3 @@\n"
            "+def test_fn():\n"
            "+    assert True\n"
        ),
        files_changed=["app.py", "tests/test_fn.py"],
        lines_added=4,
        lines_removed=1,
        explanation="Added check and test",
        validation=PatchValidationDetails(is_valid=True, clean_application=True, files_checked=["app.py", "tests/test_fn.py"]),
        synthesized_test_included=True
    )

    mock_sandbox_res = SandboxTestResponse(
        success=True,
        status="PASSED",
        exit_code=0,
        tests_run=1,
        tests_passed=1,
        tests_failed=0,
        duration_seconds=0.5,
        stdout="1 passed",
        stderr="",
        message="All tests passed successfully in Docker sandbox (verified via AI-synthesized unit test).",
        verified_via_synthesized_test=True
    )

    with patch("app.services.investigation_service.github_service.get_issue", AsyncMock(return_value={"title": "Bug", "body": "Fix"})), \
         patch("app.services.nemotron_service.nemotron_service.investigate_issue", AsyncMock(return_value=mock_inv_res)), \
         patch("app.services.patch_service.patch_service.synthesize_patch", AsyncMock(return_value=mock_patch_res)), \
         patch("app.services.sandbox_service.sandbox_service.execute_sandbox_test", AsyncMock(return_value=mock_sandbox_res)), \
         patch("app.services.security_service.security_service.scan_patch", return_value={"status": "PASSED", "summary": "No vulnerabilities"}), \
         patch("app.services.investigation_service.risk_service.predict", return_value=MagicMock(model_dump=lambda: {"risk_level": "LOW", "confidence_score": 0.95, "risk_score": 0.1}, risk_level="LOW", confidence_score=0.95, risk_score=0.1)):

        final_run = await investigation_service.execute_staged_run(
            inv_id=inv_id,
            run_id=run_id,
            mode="real"
        )

        assert final_run.get("verified_via_synthesized_test") is True
        assert investigation_service.investigations[inv_id].get("verified_via_synthesized_test") is True

        test_stage = next(s for s in final_run["stages"] if s["key"] == "test_execution")
        assert test_stage["status"] == "PASSED"
        assert "[Verified via AI-Synthesized Test]" in test_stage["summary"]

        approval_stage = next(s for s in final_run["stages"] if s["key"] == "human_approval")
        assert approval_stage["status"] == "PENDING"
        assert approval_stage["details"].get("verified_via_synthesized_test") is True

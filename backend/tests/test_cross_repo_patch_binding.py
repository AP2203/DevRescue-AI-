"""
Regression tests for cross-repository patch contamination.

Root cause covered here:
    The diff validator and the sandbox workspace applier previously resolved a
    patch's target path by loose suffix/basename matching. A patch generated for
    repository A (e.g. paths prefixed ``smart-city-air-quality/...``) could be
    silently re-bound onto a same-named file in repository B and then fail inside
    the hunk, producing the misleading error
        "Patch does not apply cleanly to 'smart-city-air-quality/.../Button.tsx'".
    Target paths were being silently rewritten instead of rejected.

These tests prove that patches are now bound to an explicit
(owner, repo, base_commit, patch_sha256, investigation_id, run_id) provenance and
that mismatched repository metadata is rejected rather than rewritten.
"""

import hashlib
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from app.services.diff_validator import (
    DiffBindingError,
    DiffValidationError,
    diff_validator,
)
from app.services.investigation_service import investigation_service
from app.services.patch_service import patch_service
from app.services.sandbox_service import SandboxService

SAMPLE_SOURCE = """import React, { useState } from 'react';

export function SubmitButton({ onSubmit }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    onSubmit();
  };

  return <button onClick={handleClick}>Submit</button>;
}
"""

VALID_DIFF = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -6,3 +6,3 @@
   const handleClick = async () => {
-    onSubmit();
+    setLoading(true);
   };
"""

# A patch whose header path carries ANOTHER repository's name prefix, but whose
# basename matches a file that exists in the active repository context.
FOREIGN_PREFIX_DIFF = """--- a/smart-city-air-quality/src/components/SubmitButton.jsx
+++ b/smart-city-air-quality/src/components/SubmitButton.jsx
@@ -6,3 +6,3 @@
   const handleClick = async () => {
-    onSubmit();
+    setLoading(true);
   };
"""

SAMPLE_INVESTIGATION = {
    "root_cause": "Submit button does not set loading state.",
    "confidence": 0.95,
    "affected_files": ["src/components/SubmitButton.jsx"],
    "affected_functions": ["handleClick"],
    "evidence": [{"file": "src/components/SubmitButton.jsx", "line": 6, "reason": "Missing setLoading"}],
    "proposed_fix": "Add setLoading(true) before onSubmit.",
    "test_strategy": "Verify loading indicator renders.",
}


# ---------------------------------------------------------------------------
# 1. diff_validator: strict target binding (no silent cross-repo rewrite)
# ---------------------------------------------------------------------------

def test_patch_from_repo_a_rejected_in_repo_b():
    """A patch path carrying repo A's prefix must NOT bind to repo B's file."""
    with pytest.raises(DiffBindingError) as exc:
        diff_validator.validate_and_apply(
            patch=FOREIGN_PREFIX_DIFF,
            file_contents={"src/components/SubmitButton.jsx": SAMPLE_SOURCE},
            allowed_files=["src/components/SubmitButton.jsx"],
            owner="anshpatel2212",
            repo="ET_AI-2.0-",
        )
    assert exc.value.details.get("repo_mismatch") is True
    assert exc.value.file == "smart-city-air-quality/src/components/SubmitButton.jsx"


def test_resolve_target_content_rejects_foreign_prefix():
    content, key = None, None
    with pytest.raises(DiffBindingError):
        diff_validator.resolve_target_content(
            "other-repo/src/app.ts",
            {"src/app.ts": "const a = 1;\n"},
            owner="acme",
            repo="real",
        )


def test_resolve_target_content_strips_explicit_active_repo_prefix():
    content, key = diff_validator.resolve_target_content(
        "real/src/app.ts",
        {"src/app.ts": "const a = 1;\n"},
        owner="acme",
        repo="real",
    )
    assert content == "const a = 1;\n"
    assert key == "src/app.ts"


def test_valid_patch_applies_to_correct_repository():
    res = diff_validator.validate_and_apply(
        patch=VALID_DIFF,
        file_contents={"src/components/SubmitButton.jsx": SAMPLE_SOURCE},
        allowed_files=["src/components/SubmitButton.jsx"],
        owner="anshpatel2212",
        repo="ET_AI-2.0-",
    )
    assert res.is_valid is True
    assert "setLoading(true);" in res.applied_contents["src/components/SubmitButton.jsx"]


def test_new_file_and_multifile_still_work():
    new_file_diff = """--- /dev/null
+++ b/tests/test_new.py
@@ -0,0 +1,2 @@
+def test_ok():
+    assert True
"""
    res = diff_validator.validate_and_apply(
        patch=new_file_diff,
        file_contents={},
        owner="acme",
        repo="real",
    )
    assert res.is_valid is True
    assert "tests/test_new.py" in res.applied_contents

    f1 = "export const A = 1;\n"
    f2 = "export const B = 2;\n"
    multi = """--- a/src/a.ts
+++ b/src/a.ts
@@ -1,1 +1,1 @@
-export const A = 1;
+export const A = 10;
--- a/src/b.ts
+++ b/src/b.ts
@@ -1,1 +1,1 @@
-export const B = 2;
+export const B = 20;
"""
    res2 = diff_validator.validate_and_apply(
        patch=multi,
        file_contents={"src/a.ts": f1, "src/b.ts": f2},
        allowed_files=["src/a.ts", "src/b.ts"],
    )
    assert res2.is_valid is True
    assert len(res2.files_changed) == 2


# ---------------------------------------------------------------------------
# 2. sandbox workspace applier: reject cross-repo paths and verify binding
# ---------------------------------------------------------------------------

def test_sandbox_rejects_foreign_repo_patch_path():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.makedirs(os.path.join(tmp_dir, "src", "components"), exist_ok=True)
        with open(os.path.join(tmp_dir, "src", "components", "SubmitButton.jsx"), "w") as f:
            f.write(SAMPLE_SOURCE)
        with pytest.raises(DiffBindingError) as exc:
            service.apply_patch_to_workspace(
                tmp_dir, FOREIGN_PREFIX_DIFF, owner="anshpatel2212", repo="ET_AI-2.0-"
            )
        assert exc.value.details.get("repo_mismatch") is True


def test_sandbox_verifies_patch_hash_binding():
    service = SandboxService()
    patch_text = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    binding = {"owner": "acme", "repo": "real", "patch_sha256": "0" * 64}
    with pytest.raises(DiffBindingError) as exc:
        service._verify_patch_binding(patch_text, binding, "acme", "real")
    assert exc.value.details.get("patch_hash_mismatch") is True


def test_sandbox_rejects_repo_mismatch_binding():
    service = SandboxService()
    patch_text = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    binding = {
        "owner": "someone-else",
        "repo": "other",
        "patch_sha256": hashlib.sha256(patch_text.encode()).hexdigest(),
    }
    with pytest.raises(DiffBindingError) as exc:
        service._verify_patch_binding(patch_text, binding, "acme", "real")
    assert exc.value.details.get("repo_mismatch") is True


def test_concurrent_investigations_cannot_share_patch_artifacts():
    """A patch bound to investigation A cannot be applied to investigation B."""
    service = SandboxService()
    patch_a = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    binding_a = {
        "investigation_id": "inv-1",
        "run_id": "run_inv-1_1_aaaaaa",
        "owner": "acme",
        "repo": "project-a",
        "patch_sha256": hashlib.sha256(patch_a.encode()).hexdigest(),
    }
    # Applying investigation A's patch to repository B is rejected.
    with pytest.raises(DiffBindingError):
        service._verify_patch_binding(patch_a, binding_a, "acme", "project-b")


@pytest.mark.asyncio
async def test_sandbox_rejects_patch_from_different_base_commit():
    service = SandboxService()
    patch_text = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    binding = {
        "owner": "acme",
        "repo": "real",
        "base_commit": "oldcommitsha",
        "patch_sha256": hashlib.sha256(patch_text.encode()).hexdigest(),
    }
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch("app.services.sandbox_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch("app.services.sandbox_service.github_service.get_branch_sha", new_callable=AsyncMock, return_value="newcommitsha"), \
         patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]), \
         patch.object(service, "detect_test_framework", return_value=(None, None, None)):
        res = await service.execute_sandbox_test(
            owner="acme",
            repo="real",
            branch="main",
            issue_number=1,
            patch=patch_text,
            binding=binding,
        )
    assert res.success is False
    assert res.status == "PATCH_FAILED"
    assert "base-commit mismatch" in (res.message or "").lower() or "base_commit" in (res.stderr or "").lower()


# ---------------------------------------------------------------------------
# 3. patch_service: reject foreign paths, emit provenance binding
# ---------------------------------------------------------------------------

def _mock_nemotron_client(diff_text):
    from unittest.mock import MagicMock
    mock_choice = MagicMock()
    mock_choice.message.content = diff_text
    mock_resp = MagicMock(choices=[mock_choice])
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
    return mock_client


@pytest.mark.asyncio
async def test_patch_service_rejects_foreign_repository_path():
    """A model patch referencing another repo's path is rejected, never grafted on."""
    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch("app.services.patch_service.github_service.get_file_sha", new_callable=AsyncMock, return_value=None), \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:
        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")
        mock_get_client.return_value = _mock_nemotron_client(FOREIGN_PREFIX_DIFF)

        with pytest.raises(DiffBindingError):
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="ET_AI-2.0-",
                branch="main",
                issue_number=1,
                investigation=SAMPLE_INVESTIGATION,
                access_token="test_token",
                investigation_id="inv-1",
                run_id="run_inv-1_1_aaaaaa",
            )


@pytest.mark.asyncio
async def test_patch_service_result_includes_provenance_binding():
    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch("app.services.patch_service.github_service.get_file_sha", new_callable=AsyncMock, return_value=None), \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:
        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")
        mock_get_client.return_value = _mock_nemotron_client(VALID_DIFF)

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="ET_AI-2.0-",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="test_token",
            investigation_id="inv-7",
            run_id="run_inv-7_99_bbbbbb",
            base_commit="abc123def",
        )

    binding = result["binding"]
    assert binding["owner"] == "anshpatel2212"
    assert binding["repo"] == "ET_AI-2.0-"
    assert binding["investigation_id"] == "inv-7"
    assert binding["run_id"] == "run_inv-7_99_bbbbbb"
    assert binding["base_commit"] == "abc123def"
    assert binding["patch_sha256"] == hashlib.sha256(result["patch"].encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_failed_patch_attempt_never_reports_success():
    """Exhausted retries with a mismatched patch must raise, never return success."""
    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch("app.services.patch_service.github_service.get_file_sha", new_callable=AsyncMock, return_value=None), \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:
        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")
        mock_get_client.return_value = _mock_nemotron_client(FOREIGN_PREFIX_DIFF)

        with pytest.raises(DiffValidationError):
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="ET_AI-2.0-",
                branch="main",
                issue_number=1,
                investigation=SAMPLE_INVESTIGATION,
                access_token="test_token",
            )


# ---------------------------------------------------------------------------
# 4. investigations: reruns use fresh metadata / run IDs
# ---------------------------------------------------------------------------

def test_reruns_use_fresh_run_ids_and_metadata():
    run_a = investigation_service.create_run_record("inv-xyz")
    run_b = investigation_service.create_run_record("inv-xyz", parent_run_id=run_a["run_id"])
    assert run_a["run_id"] != run_b["run_id"]
    assert run_a["investigation_id"] == run_b["investigation_id"] == "inv-xyz"
    assert run_b["parent_run_id"] == run_a["run_id"]
    # Fresh runs start from a clean stage state (no shared artifacts).
    assert run_a["stages"] is not run_b["stages"]


def test_investigation_ids_are_unique():
    ids = {investigation_service._allocate_investigation_id() for _ in range(50)}
    assert len(ids) == 50


# ---------------------------------------------------------------------------
# 5. isolation: a late-finishing OLDER run cannot overwrite the active
#    investigation's shared state (requirement: stale-response guard)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_late_older_run_cannot_overwrite_active_investigation_state():
    """A run that is no longer the investigation's latest run must not write
    shared investigation fields (status, patch, results), even if it finishes
    late."""
    from app.schemas.nemotron import (
        NemotronInvestigateResponse,
        NemotronRealPatchResponse,
        PatchValidationDetails,
    )
    from app.schemas.sandbox import SandboxTestResponse
    from unittest.mock import MagicMock

    inv_id = "inv-late-guard"
    active_run_id = "run_inv-late-guard_2_active00"

    investigation_service.investigations[inv_id] = {
        "id": inv_id,
        "owner": "testowner",
        "repo_name": "testrepo",
        "branch": "main",
        "issue_number": 1,
        "issue_title": "Bug",
        # A NEWER run has already become the active run.
        "latest_run_id": active_run_id,
        "status": "INVESTIGATING",
        "progress": 25,
    }

    stale_run = investigation_service.create_run_record(inv_id)
    stale_run_id = stale_run["run_id"]
    investigation_service.runs[stale_run_id] = stale_run

    mock_inv_res = NemotronInvestigateResponse(
        root_cause="Missing check",
        confidence=0.9,
        affected_files=["app.py"],
        affected_functions=["fn"],
        evidence=[],
        proposed_fix="Add check",
        test_strategy="NO_TESTS_FOUND",
    )
    mock_patch_res = NemotronRealPatchResponse(
        success=True,
        patch=(
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def fn():\n"
            "-    return False\n"
            "+    return True\n"
        ),
        files_changed=["app.py"],
        lines_added=1,
        lines_removed=1,
        explanation="Fix",
        validation=PatchValidationDetails(is_valid=True, clean_application=True, files_checked=["app.py"]),
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
        message="All tests passed successfully in Docker sandbox.",
    )

    with patch("app.services.investigation_service.github_service.get_issue", AsyncMock(return_value={"title": "Bug", "body": "Fix"})), \
         patch("app.services.nemotron_service.nemotron_service.investigate_issue", AsyncMock(return_value=mock_inv_res)), \
         patch("app.services.patch_service.patch_service.synthesize_patch", AsyncMock(return_value=mock_patch_res)), \
         patch("app.services.sandbox_service.sandbox_service.execute_sandbox_test", AsyncMock(return_value=mock_sandbox_res)), \
         patch("app.services.security_service.security_service.scan_patch", return_value={"status": "PASSED", "summary": "No vulnerabilities"}), \
         patch("app.services.investigation_service.risk_service.predict", return_value=MagicMock(model_dump=lambda: {"risk_level": "LOW", "confidence_score": 0.95, "risk_score": 0.1}, risk_level="LOW", confidence_score=0.95, risk_score=0.1)):

        final_run = await investigation_service.execute_staged_run(
            inv_id=inv_id,
            run_id=stale_run_id,
            mode="real",
        )

    # The stale run still records its own run-level results...
    assert final_run["status"] in ("PASSED", "FAILED")
    assert final_run.get("sandbox_result") is not None

    # ...but the active investigation's shared state must be untouched.
    inv_after = investigation_service.investigations[inv_id]
    assert inv_after["latest_run_id"] == active_run_id
    assert inv_after["status"] == "INVESTIGATING"
    assert inv_after["progress"] == 25
    assert "patch" not in inv_after
    assert "sandboxResult" not in inv_after
    assert "riskAssessment" not in inv_after
    assert "stages" not in inv_after
    assert "agents" not in inv_after
    assert inv_after.get("verified_via_synthesized_test") is None

    # Cleanup to avoid cross-test leakage
    investigation_service.runs.pop(stale_run_id, None)
    investigation_service.investigations.pop(inv_id, None)

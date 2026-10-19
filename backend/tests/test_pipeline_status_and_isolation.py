"""
Regression tests for repository isolation, sandbox communication failures and
accurate pipeline status semantics.

Covers:
  * simultaneous investigations of DIFFERENT repositories never cross-contaminate
  * a sandbox transport/communication failure surfaces as a structured ERROR
    (never as a passing test)
  * the SandboxTestResponse invariant forbids PASSED with zero executed tests
  * zero-test repositories are not treated as passing
  * overall investigation status is FAILED (not READY_FOR_REVIEW/100%) when a
    required stage (testing) failed
"""

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.investigation_service import investigation_service
from app.services.sandbox_service import sandbox_service  # noqa: F401  (import side-effects)
from app.schemas.sandbox import SandboxTestRequest, SandboxTestResponse
from app.schemas.nemotron import (
    NemotronInvestigateResponse,
    NemotronRealPatchResponse,
    PatchValidationDetails,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inv_res():
    return NemotronInvestigateResponse(
        root_cause="Missing validation on user input",
        confidence=0.9,
        affected_files=["app.py"],
        affected_functions=["fn"],
        evidence=[],
        proposed_fix="Add validation",
        test_strategy="Run the unit tests",
    )


def _patch_text(path="app.py"):
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,2 +1,2 @@\n"
        " def fn():\n"
        "-    return False\n"
        "+    return True\n"
    )


def _patch_res(path="app.py", owner="acme", repo="alpha", investigation_id=None, run_id=None):
    text = _patch_text(path)
    return NemotronRealPatchResponse(
        success=True,
        patch=text,
        files_changed=[path],
        lines_added=1,
        lines_removed=1,
        explanation="Fix",
        validation=PatchValidationDetails(is_valid=True, clean_application=True, files_checked=[path]),
        binding={
            "owner": owner,
            "repo": repo,
            "investigation_id": investigation_id,
            "run_id": run_id,
            "patch_sha256": hashlib.sha256(text.encode()).hexdigest(),
        },
    )


def _sandbox_res(status):
    if status == "PASSED":
        return SandboxTestResponse(
            success=True, status="PASSED", exit_code=0,
            tests_run=2, tests_passed=2, tests_failed=0,
            duration_seconds=0.5, stdout="2 passed", stderr="",
            message="All tests passed",
        )
    return SandboxTestResponse(
        success=False, status=status, exit_code=1,
        tests_run=0, tests_passed=0, tests_failed=0,
        duration_seconds=0.5, stdout="", stderr="",
        message=f"Sandbox status: {status}",
    )


def _register_investigation(inv_id, owner, repo):
    investigation_service.investigations[inv_id] = {
        "id": inv_id,
        "owner": owner,
        "repo_name": repo,
        "branch": "main",
        "issue_number": 1,
        "issue_title": "Bug",
    }
    run = investigation_service.create_run_record(inv_id)
    investigation_service.investigations[inv_id]["latest_run_id"] = run["run_id"]
    investigation_service.runs[run["run_id"]] = run
    return run


def _patch_stack(synthesize, sandbox_status_or_fn):
    async def _sandbox(**kwargs):
        if callable(sandbox_status_or_fn):
            return sandbox_status_or_fn(kwargs)
        return _sandbox_res(sandbox_status_or_fn)

    return (
        patch("app.services.investigation_service.github_service.get_issue",
              AsyncMock(return_value={"title": "Bug", "body": "Fix"})),
        patch("app.services.nemotron_service.nemotron_service.investigate_issue",
              AsyncMock(return_value=_inv_res())),
        patch("app.services.patch_service.patch_service.synthesize_patch", side_effect=synthesize),
        patch("app.services.sandbox_service.sandbox_service.execute_sandbox_test", side_effect=_sandbox),
        patch("app.services.security_service.security_service.scan_patch",
              return_value={"status": "PASSED", "summary": "No vulnerabilities"}),
        patch("app.services.investigation_service.risk_service.predict",
              return_value=MagicMock(
                  model_dump=lambda: {"risk_level": "LOW", "confidence_score": 0.95, "risk_score": 0.1},
                  risk_level="LOW", confidence_score=0.95, risk_score=0.1)),
    )


def _cleanup(*inv_ids):
    for inv_id in inv_ids:
        investigation_service.investigations.pop(inv_id, None)


# ---------------------------------------------------------------------------
# A. Simultaneous investigations of different repositories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simultaneous_investigations_of_different_repositories_are_isolated():
    run_a = _register_investigation("inv-iso-a", "acme", "alpha")
    run_b = _register_investigation("inv-iso-b", "acme", "beta")

    async def fake_synthesize(owner, repo, **kwargs):
        return _patch_res(
            "app.py", owner=owner, repo=repo,
            investigation_id=kwargs.get("investigation_id"),
            run_id=kwargs.get("run_id"),
        )

    patches = _patch_stack(fake_synthesize, "PASSED")
    for p in patches:
        p.start()
    try:
        res_a, res_b = await asyncio.gather(
            investigation_service.execute_staged_run("inv-iso-a", run_a["run_id"], mode="real"),
            investigation_service.execute_staged_run("inv-iso-b", run_b["run_id"], mode="real"),
        )
    finally:
        for p in patches:
            p.stop()

    # Each run's patch provenance is bound to its OWN repository.
    assert res_a["patch"]["binding"]["repo"] == "alpha"
    assert res_b["patch"]["binding"]["repo"] == "beta"
    assert res_a["patch"]["binding"]["investigation_id"] == "inv-iso-a"
    assert res_b["patch"]["binding"]["investigation_id"] == "inv-iso-b"

    inv_a = investigation_service.investigations["inv-iso-a"]
    inv_b = investigation_service.investigations["inv-iso-b"]
    assert inv_a["repo_name"] == "alpha"
    assert inv_b["repo_name"] == "beta"
    assert inv_a["patch"]["binding"]["repo"] == "alpha"
    assert inv_b["patch"]["binding"]["repo"] == "beta"

    _cleanup("inv-iso-a", "inv-iso-b")


# ---------------------------------------------------------------------------
# B. Sandbox communication failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sandbox_communication_failure_returns_structured_error():
    """A raised transport/communication error must become a structured ERROR
    response, never a success and never an HTTP 500 that hides the cause."""
    from app.api import sandbox as sandbox_api

    payload = SandboxTestRequest(
        owner="acme", repo="alpha", issue_number=1,
        patch="--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a\n+b\n",
    )
    fake_request = MagicMock()

    with patch.object(sandbox_api, "get_github_access_token", return_value="token"), \
         patch("app.services.sandbox_service.sandbox_service.execute_tests",
               new_callable=AsyncMock, side_effect=RuntimeError("docker daemon connection reset")):
        resp = await sandbox_api.run_sandbox_test(fake_request, payload)

    assert resp.success is False
    assert resp.status == "ERROR"
    assert "connection reset" in (resp.message or "")


@pytest.mark.asyncio
async def test_sandbox_transport_failure_never_reported_as_passed_at_pipeline_level():
    run = _register_investigation("inv-transport", "acme", "alpha")

    async def fake_synthesize(owner, repo, **kwargs):
        return _patch_res("app.py", owner=owner, repo=repo)

    # Simulate the sandbox call itself blowing up (as the API would surface ERROR).
    async def boom(**kwargs):
        raise RuntimeError("Failed to fetch")

    patches = _patch_stack(fake_synthesize, boom)
    for p in patches:
        p.start()
    try:
        final_run = await investigation_service.execute_staged_run("inv-transport", run["run_id"], mode="real")
    finally:
        for p in patches:
            p.stop()

    # The failed run must never be reported as a passing/complete investigation.
    assert final_run["status"] == "FAILED"
    inv = investigation_service.investigations["inv-transport"]
    assert inv.get("status") == "FAILED"
    assert inv.get("progress", 0) < 100
    test_stage = next(s for s in final_run["stages"] if s["key"] == "test_execution")
    assert test_stage["status"] == "FAILED"

    _cleanup("inv-transport")


# ---------------------------------------------------------------------------
# C. Test semantics
# ---------------------------------------------------------------------------

def test_passed_status_requires_executed_tests():
    with pytest.raises(ValueError):
        SandboxTestResponse(success=True, status="PASSED", tests_run=0, tests_passed=0, tests_failed=0)
    with pytest.raises(ValueError):
        SandboxTestResponse(success=True, status="PASSED", tests_run=3, tests_passed=2, tests_failed=1)


def test_zero_tests_is_not_a_pass():
    resp = SandboxTestResponse(
        success=False, status="NO_TESTS_FOUND", exit_code=5,
        tests_run=0, tests_passed=0, tests_failed=0,
        message="No matching test files found.",
    )
    assert resp.success is False
    assert resp.status == "NO_TESTS_FOUND"


# ---------------------------------------------------------------------------
# D. Accurate overall status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_tests_make_overall_status_failed_not_complete():
    run = _register_investigation("inv-fail", "acme", "alpha")

    async def fake_synthesize(owner, repo, **kwargs):
        return _patch_res("app.py", owner=owner, repo=repo)

    patches = _patch_stack(fake_synthesize, "FAILED")
    for p in patches:
        p.start()
    try:
        final_run = await investigation_service.execute_staged_run("inv-fail", run["run_id"], mode="real")
    finally:
        for p in patches:
            p.stop()

    assert final_run["status"] == "FAILED"
    inv = investigation_service.investigations["inv-fail"]
    assert inv["status"] == "FAILED"
    assert inv.get("progress", 0) < 100

    test_stage = next(s for s in final_run["stages"] if s["key"] == "test_execution")
    assert test_stage["status"] == "FAILED"

    _cleanup("inv-fail")


@pytest.mark.asyncio
async def test_no_tests_is_partial_review_not_success():
    run = _register_investigation("inv-notests", "acme", "alpha")

    async def fake_synthesize(owner, repo, **kwargs):
        return _patch_res("app.py", owner=owner, repo=repo)

    patches = _patch_stack(fake_synthesize, "NO_TESTS_FOUND")
    for p in patches:
        p.start()
    try:
        final_run = await investigation_service.execute_staged_run("inv-notests", run["run_id"], mode="real")
    finally:
        for p in patches:
            p.stop()

    assert final_run["status"] == "PASSED"  # stage flow completes without a hard failure
    inv = investigation_service.investigations["inv-notests"]
    # ...but the investigation is flagged for human review, not silently "done".
    assert inv["status"] == "READY_FOR_REVIEW"
    assert inv.get("progress") == 90

    _cleanup("inv-notests")


@pytest.mark.asyncio
async def test_passing_tests_yield_ready_for_review_with_full_progress():
    run = _register_investigation("inv-pass", "acme", "alpha")

    async def fake_synthesize(owner, repo, **kwargs):
        return _patch_res("app.py", owner=owner, repo=repo)

    patches = _patch_stack(fake_synthesize, "PASSED")
    for p in patches:
        p.start()
    try:
        final_run = await investigation_service.execute_staged_run("inv-pass", run["run_id"], mode="real")
    finally:
        for p in patches:
            p.stop()

    assert final_run["status"] == "PASSED"
    inv = investigation_service.investigations["inv-pass"]
    assert inv["status"] == "READY_FOR_REVIEW"
    assert inv.get("progress") == 100

    _cleanup("inv-pass")

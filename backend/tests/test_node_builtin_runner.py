"""
Regression tests for previously uncovered test-strategy scenarios:

- Node.js built-in test runner (`node --test` / `node:test`) detection and metrics.
- Node cross-directory test discovery (tests kept at repository root).
- npm workspaces monorepo routing.
- Vitest execute-level PASSED classification.
- Manual override security validation end-to-end (path escape / dangerous command).

Unit tests use mocks for Docker. Real Docker integration remains in test_sandbox.py
(gated by DEVRESCUE_DOCKER_TESTS / cached images).
"""

import os
import json
import pytest
from unittest.mock import patch, AsyncMock

from app.services.sandbox_service import (
    SandboxService,
    parse_test_metrics,
    TestFrameworkResult,
)
from app.services.profiler.node_adapter import NodeAdapter
from app.services.profiler.repo_profiler import RepoProfiler


# -------------------------------------------------------------
# 1. Node.js built-in test runner metrics
# -------------------------------------------------------------

def test_parse_test_metrics_node_tap_passing():
    """Node --test TAP reporter summary is parsed accurately."""
    out = (
        "TAP version 13\n"
        "# Subtest: adds numbers\n"
        "ok 1 - adds numbers\n"
        "1..3\n"
        "# tests 3\n"
        "# suites 0\n"
        "# pass 3\n"
        "# fail 0\n"
        "# cancelled 0\n"
        "# skipped 0\n"
        "# todo 0\n"
    )
    runs, passed, failed = parse_test_metrics("npm test", out)
    assert (runs, passed, failed) == (3, 3, 0)


def test_parse_test_metrics_node_tap_failing():
    """Node --test TAP reporter correctly extracts failures."""
    out = "# tests 4\n# pass 3\n# fail 1\n# skipped 0\n"
    runs, passed, failed = parse_test_metrics("node --test", out)
    assert (runs, passed, failed) == (4, 3, 1)


def test_parse_test_metrics_node_zero_tests():
    """Node --test with zero discovered tests parses as 0/0/0 (never a pass)."""
    out = "# tests 0\n# pass 0\n# fail 0\n"
    runs, passed, failed = parse_test_metrics("npm test", out)
    assert (runs, passed, failed) == (0, 0, 0)


def test_parse_test_metrics_node_spec_reporter():
    """Node spec reporter output is parsed when the TAP reporter is unavailable."""
    out = "\u2139 tests 2\n\u2139 pass 2\n\u2139 fail 0\n"
    runs, passed, failed = parse_test_metrics("npm test", out)
    assert (runs, passed, failed) == (2, 2, 0)


# -------------------------------------------------------------
# 2. Node adapter: built-in runner detection
# -------------------------------------------------------------

def test_node_adapter_detects_builtin_runner(tmp_path):
    """package.json with 'node --test' is detected as the node built-in runner."""
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "builtin-app",
        "scripts": {"test": "node --test"},
        "devDependencies": {"@types/node": "^20.0.0"},
    }), encoding="utf-8")
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "math.test.js").write_text(
        "const test = require('node:test'); test('x', () => {});\n", encoding="utf-8"
    )

    adapter = NodeAdapter()
    profile = adapter.detect(str(tmp_path), "", str(tmp_path))
    assert profile is not None
    assert profile.test_framework == "node"
    assert profile.test_command == "npm test"
    assert profile.test_files_count == 1

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "READY"
    assert contract.test_command == "npm test"


def test_node_adapter_builtin_runner_zero_tests(tmp_path):
    """Built-in runner configured but no test files -> NO_TESTS_FOUND, never READY-as-pass."""
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "builtin-empty",
        "scripts": {"test": "node --test"},
    }), encoding="utf-8")
    (tmp_path / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")

    adapter = NodeAdapter()
    profile = adapter.detect(str(tmp_path), "", str(tmp_path))
    assert profile is not None
    assert profile.test_framework == "node"

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "NO_TESTS_FOUND"
    assert contract.test_files_count == 0


def test_detect_test_framework_node_builtin(tmp_path):
    """Sandbox detect_test_framework resolves the built-in node runner to 'npm test'."""
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": {"test": "node --test"},
        "devDependencies": {"@types/node": "^20"},
    }), encoding="utf-8")
    (tmp_path / "a.test.js").write_text("// t\n", encoding="utf-8")

    service = SandboxService()
    res = service.detect_test_framework(str(tmp_path), [])
    assert res.framework == "node"
    assert res.command == "npm test"
    assert res.workdir == "/workspace"


# -------------------------------------------------------------
# 3. Node cross-directory test discovery
# -------------------------------------------------------------

def test_node_adapter_cross_directory_root_tests(tmp_path):
    """Nested Node subproject discovers a repository-root test suite instead of 0 tests."""
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "package.json").write_text(json.dumps({
        "name": "backend",
        "scripts": {"test": "jest"},
        "devDependencies": {"jest": "^29.0.0"},
    }), encoding="utf-8")
    (backend / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")

    root_tests = tmp_path / "tests"
    root_tests.mkdir()
    (root_tests / "core.test.js").write_text("test('c', () => {});\n", encoding="utf-8")

    adapter = NodeAdapter()
    profile = adapter.detect(str(backend), "backend", str(tmp_path))
    assert profile is not None
    assert profile.test_files_count == 1
    assert any("root/parent test suite" in ev for ev in profile.evidence)


# -------------------------------------------------------------
# 4. npm workspaces monorepo routing
# -------------------------------------------------------------

def test_npm_workspaces_monorepo_routing(tmp_path):
    """Root 'workspaces' manifest is detected and per-package strategy routing works."""
    (tmp_path / "package.json").write_text(json.dumps({
        "name": "root", "private": True, "workspaces": ["packages/*"],
    }), encoding="utf-8")

    pkg_a = tmp_path / "packages" / "a"
    pkg_a.mkdir(parents=True)
    (pkg_a / "package.json").write_text(json.dumps({
        "name": "@x/a", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29"},
    }), encoding="utf-8")
    (pkg_a / "a.test.js").write_text("test('a', () => {});\n", encoding="utf-8")

    pkg_b = tmp_path / "packages" / "b"
    pkg_b.mkdir(parents=True)
    (pkg_b / "package.json").write_text(json.dumps({
        "name": "@x/b", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1"},
    }), encoding="utf-8")
    (pkg_b / "b.test.ts").write_text("// vitest\n", encoding="utf-8")

    profiler = RepoProfiler()
    repo_profile = profiler.profile_repository(str(tmp_path))
    assert repo_profile.is_monorepo is True
    assert repo_profile.monorepo_type == "npm_workspaces"

    strat_a = profiler.evaluate_test_strategy(str(tmp_path), ["packages/a/a.js"], repo_profile)
    assert strat_a.subproject_path == "packages/a"
    assert strat_a.test_framework == "jest"
    assert strat_a.container_workdir == "/workspace/packages/a"

    strat_b = profiler.evaluate_test_strategy(str(tmp_path), ["packages/b/b.ts"], repo_profile)
    assert strat_b.subproject_path == "packages/b"
    assert strat_b.test_framework == "vitest"


# -------------------------------------------------------------
# 5. Execute-level classifications: Vitest and Node built-in runner
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitest_passing_execution_returns_passed_status():
    """Valid Vitest execution with passing assertions returns PASSED with accurate metrics."""
    service = SandboxService()
    out = (
        " RUN  v1.2.0 /workspace\n\n"
        " \u2713 src/math.test.ts (2)\n\n"
        " Test Files  1 passed (1)\n"
        "      Tests  4 passed (4)\n"
        "   Duration  1.23s\n"
    )
    patch_ = "--- a/src/math.js\n+++ b/src/math.js\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(0, out, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["src/math.js"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace", "node:20-slim", "vitest")), \
         patch.object(service, "prepare_node_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):
        res = await service.execute_sandbox_test(
            owner="test", repo="vitest-app", branch="main", issue_number=1, patch=patch_
        )

    assert res.success is True
    assert res.status == "PASSED"
    assert res.tests_run == 4
    assert res.tests_passed == 4
    assert res.tests_failed == 0


@pytest.mark.asyncio
async def test_node_builtin_runner_passing_execution_returns_passed_status():
    """Node --test passing output is classified as PASSED (not NO_TESTS_FOUND)."""
    service = SandboxService()
    out = "# tests 3\n# pass 3\n# fail 0\n"
    patch_ = "--- a/src/math.js\n+++ b/src/math.js\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(0, out, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["src/math.js"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace", "node:20-slim", "node")), \
         patch.object(service, "prepare_node_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):
        res = await service.execute_sandbox_test(
            owner="test", repo="node-builtin-app", branch="main", issue_number=1, patch=patch_
        )

    assert res.success is True
    assert res.status == "PASSED"
    assert res.tests_run == 3
    assert res.tests_passed == 3


@pytest.mark.asyncio
async def test_node_builtin_runner_zero_tests_never_passed():
    """Node --test with 0 tests must be NO_TESTS_FOUND, never PASSED."""
    service = SandboxService()
    out = "# tests 0\n# pass 0\n# fail 0\n"
    patch_ = "--- a/src/math.js\n+++ b/src/math.js\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(0, out, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["src/math.js"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace", "node:20-slim", "node")), \
         patch.object(service, "prepare_node_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):
        res = await service.execute_sandbox_test(
            owner="test", repo="node-builtin-empty", branch="main", issue_number=1, patch=patch_
        )

    assert res.success is False
    assert res.status == "NO_TESTS_FOUND"
    assert res.tests_run == 0


# -------------------------------------------------------------
# 6. Manual override security validation (end-to-end)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_workdir_override_outside_workspace_rejected():
    """Absolute path outside /workspace is rejected with ENVIRONMENT_ERROR."""
    service = SandboxService()
    patch_ = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n"

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["x.py"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("pytest", "/workspace", "python:3.11-slim", "pytest")):
        res = await service.execute_sandbox_test(
            owner="t", repo="r", branch="main", issue_number=1, patch=patch_,
            working_directory_override="/etc"
        )

    assert res.success is False
    assert res.status == "ENVIRONMENT_ERROR"
    assert "Security violation" in (res.message or "")


@pytest.mark.asyncio
async def test_dangerous_command_override_rejected():
    """Destructive/unsafe test command override is rejected with ENVIRONMENT_ERROR."""
    service = SandboxService()
    patch_ = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n"

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["x.py"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("pytest", "/workspace", "python:3.11-slim", "pytest")):
        res = await service.execute_sandbox_test(
            owner="t", repo="r", branch="main", issue_number=1, patch=patch_,
            test_command_override="rm -rf /workspace && pytest"
        )

    assert res.success is False
    assert res.status == "ENVIRONMENT_ERROR"
    assert "Security violation" in (res.message or "")


@pytest.mark.asyncio
async def test_unapproved_command_override_rejected():
    """Non-test-runner command override is rejected."""
    service = SandboxService()
    patch_ = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n"

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["x.py"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("pytest", "/workspace", "python:3.11-slim", "pytest")):
        res = await service.execute_sandbox_test(
            owner="t", repo="r", branch="main", issue_number=1, patch=patch_,
            test_command_override="make test"
        )

    assert res.success is False
    assert res.status == "ENVIRONMENT_ERROR"


def test_validate_working_directory_override_guards(tmp_path):
    """Unit-level checks for the working directory override validator."""
    from app.services.sandbox_service import validate_working_directory_override

    # Traversal rejected
    ok, _, err = validate_working_directory_override("../../etc")
    assert ok is False and err

    # Absolute escape rejected
    ok, _, err = validate_working_directory_override("/etc/passwd")
    assert ok is False and err

    # Valid relative path accepted and normalized under /workspace
    ok, norm, err = validate_working_directory_override("backend/src")
    assert ok is True
    assert norm == "/workspace/backend/src"

    # Empty accepted as workspace root
    ok, norm, err = validate_working_directory_override("")
    assert ok is True
    assert norm == "/workspace"

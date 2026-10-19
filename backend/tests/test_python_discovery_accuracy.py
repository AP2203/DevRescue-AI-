"""
Regression tests for accurate Python test discovery across GitHub repositories.

Covers:
- manifest/lockfile-only pytest declarations (pyproject Poetry groups, poetry.lock)
- conftest.py as a pytest suite signal
- recursive discovery in deeply nested monorepo subprojects
- never reporting TESTS_NOT_CONFIGURED when a runnable suite exists elsewhere
- searched-root evidence when nothing is found
- repository/commit identity binding of the evaluated workspace
- isolation of discovery to the given workspace
"""
import os
import json

from app.services.profiler.repo_profiler import RepoProfiler
from app.services.profiler.python_adapter import PythonAdapter


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def test_pyproject_poetry_group_pytest_dependency(tmp_path):
    """pytest declared only in a Poetry dev-dependency group is detected."""
    backend = tmp_path / "backend"
    _write(str(backend / "pyproject.toml"), (
        "[tool.poetry]\n"
        "name = \"backend\"\n"
        "version = \"0.1.0\"\n\n"
        "[tool.poetry.group.dev.dependencies]\n"
        "pytest = \"^7.4.0\"\n"
    ))
    _write(str(backend / "src" / "app.py"), "app = None\n")
    _write(str(backend / "tests" / "test_api.py"), "def test_api(): assert True\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(str(tmp_path), ["backend/src/app.py"])

    assert strategy.language == "python"
    assert strategy.subproject_path == "backend"
    assert strategy.test_framework == "pytest"
    assert strategy.test_command == "pytest"
    assert strategy.status == "READY"
    assert strategy.test_files_count == 1


def test_poetry_lockfile_pytest_dependency(tmp_path):
    """A root project with only a poetry.lock declaring pytest is still runnable."""
    _write(str(tmp_path / "poetry.lock"), "name = \"pytest\"\nversion = \"8.0.0\"\n")
    _write(str(tmp_path / "app.py"), "def main(): pass\n")
    _write(str(tmp_path / "tests" / "test_core.py"), "def test_core(): assert True\n")

    adapter = PythonAdapter()
    profile = adapter.detect(str(tmp_path), "", str(tmp_path))
    assert profile is not None
    assert profile.test_framework == "pytest"

    contract = adapter.resolve_test_strategy(profile, ["app.py"])
    assert contract.status == "READY"
    assert contract.test_command == "pytest"


def test_conftest_marks_pytest_suite(tmp_path):
    """conftest.py plus test files yields pytest even without a pytest manifest."""
    _write(str(tmp_path / "conftest.py"), "import sys\n")
    _write(str(tmp_path / "app.py"), "pass\n")
    _write(str(tmp_path / "requirements.txt"), "requests\n")  # no pytest
    _write(str(tmp_path / "tests" / "test_app.py"), "def test_app(): assert True\n")

    adapter = PythonAdapter()
    profile = adapter.detect(str(tmp_path), "", str(tmp_path))
    assert profile is not None
    assert profile.test_framework == "pytest"
    assert any("conftest.py" in ev for ev in profile.evidence)


def test_deeply_nested_test_discovery(tmp_path):
    """Tests nested several directories deep are discovered recursively."""
    _write(str(tmp_path / "requirements.txt"), "pytest\n")
    _write(str(tmp_path / "src" / "pkg" / "app.py"), "pass\n")
    _write(str(tmp_path / "src" / "pkg" / "tests" / "test_deep.py"), "def test_deep(): assert True\n")

    adapter = PythonAdapter()
    contract = adapter.resolve_test_strategy(
        adapter.detect(str(tmp_path), "", str(tmp_path)), ["src/pkg/app.py"]
    )
    assert contract.test_files_count >= 1
    assert any("test_deep.py" in f for f in contract.discovered_test_files)
    assert contract.status == "READY"


def test_searched_roots_evidence_when_no_tests(tmp_path):
    """TESTS_NOT_CONFIGURED carries the searched roots for diagnostics."""
    _write(str(tmp_path / "app.py"), "pass\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(str(tmp_path), ["app.py"])

    assert strategy.status == "TESTS_NOT_CONFIGURED"
    assert strategy.test_command is None
    assert any("Searched project roots" in ev for ev in strategy.supporting_evidence)


def test_no_false_negative_when_sibling_has_tests(tmp_path):
    """
    A changed file that points at an untested subproject must not shadow a
    sibling subproject that has a runnable suite (avoids false TESTS_NOT_CONFIGURED).
    """
    _write(str(tmp_path / "services" / "api" / "main.py"), "def run(): pass\n")
    _write(str(tmp_path / "backend" / "requirements.txt"), "pytest\n")
    _write(str(tmp_path / "backend" / "tests" / "test_api.py"), "def test_api(): assert True\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(str(tmp_path), ["services/api/main.py"])

    # Must not falsely conclude there is nothing to test; the sibling suite is run.
    assert strategy.status == "READY"
    assert strategy.status != "TESTS_NOT_CONFIGURED"
    assert strategy.test_framework == "pytest"
    assert strategy.test_files_count == 1
    assert any("test_api.py" in f for f in strategy.discovered_test_files)


def test_repo_identity_bound_into_evidence(tmp_path):
    """The verified owner/repo/commit is recorded in the contract evidence."""
    _write(str(tmp_path / "requirements.txt"), "pytest\n")
    _write(str(tmp_path / "app.py"), "pass\n")
    _write(str(tmp_path / "tests" / "test_app.py"), "def test_app(): assert True\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(
        str(tmp_path),
        ["tests/test_app.py"],
        repo_identity={
            "owner": "acme",
            "repo": "widgets",
            "branch": "main",
            "commit": "abc123def4567890",
            "workspace": str(tmp_path),
        },
    )

    joined = "\n".join(strategy.supporting_evidence)
    assert "acme/widgets" in joined
    assert "abc123def456" in joined


def test_tox_and_nox_evidence_recorded(tmp_path):
    """tox.ini and noxfile.py are inspected and surfaced as evidence."""
    _write(str(tmp_path / "requirements.txt"), "pytest\n")
    _write(str(tmp_path / "app.py"), "pass\n")
    _write(str(tmp_path / "tests" / "test_app.py"), "def test_app(): assert True\n")
    _write(str(tmp_path / "tox.ini"), "[testenv]\ncommands = pytest\n")
    _write(str(tmp_path / "noxfile.py"), "import nox\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(str(tmp_path), ["tests/test_app.py"])

    joined = "\n".join(strategy.supporting_evidence)
    assert "tox.ini" in joined
    assert "noxfile.py" in joined


def test_discovery_is_isolated_to_workspace(tmp_path):
    """Discovery for one workspace never reports tests from another checkout."""
    empty_repo = tmp_path / "empty_repo"
    _write(str(empty_repo / "app.py"), "pass\n")

    tested_repo = tmp_path / "tested_repo"
    _write(str(tested_repo / "requirements.txt"), "pytest\n")
    _write(str(tested_repo / "app.py"), "pass\n")
    _write(str(tested_repo / "tests" / "test_app.py"), "def test_app(): assert True\n")

    profiler = RepoProfiler()
    empty_strategy = profiler.evaluate_test_strategy(str(empty_repo), ["app.py"])
    tested_strategy = profiler.evaluate_test_strategy(str(tested_repo), ["app.py"])

    assert empty_strategy.discovered_test_files == []
    assert empty_strategy.status == "TESTS_NOT_CONFIGURED"
    assert tested_strategy.test_files_count == 1
    assert tested_strategy.status == "READY"


def test_node_monorepo_unaffected_by_python_changes(tmp_path):
    """Python discovery changes do not hijack Node subproject selection."""
    backend = tmp_path / "backend"
    _write(str(backend / "requirements.txt"), "pytest\n")
    _write(str(backend / "tests" / "test_api.py"), "def test_api(): assert True\n")

    frontend = tmp_path / "frontend"
    _write(str(frontend / "package.json"), json.dumps(
        {"name": "fe", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}
    ))
    _write(str(frontend / "src" / "__tests__" / "app.test.js"), "test('x', () => {});\n")

    profiler = RepoProfiler()
    strategy = profiler.evaluate_test_strategy(str(tmp_path), ["frontend/src/App.jsx"])

    assert strategy.subproject_path == "frontend"
    assert strategy.test_framework == "jest"
    assert strategy.status == "READY"

"""
Regression tests for the top-level root cause of a misleading
``DEPENDENCIES_UNAVAILABLE`` on a polyglot repository (e.g. anshpatel2212/2D2Mesh:
a Vite/Node frontend at the repo root beside a Python ``backend/``).

Three distinct defects are covered:

1. Subproject selection: the deepest matching *package* directory (which owns no
   tests) outranked the real project root, and the safety net then fell back to
   the recursive root catch-all (``""`` -> ``/workspace``).
2. Dependency ecosystem: the mere presence of a root ``package.json`` routed a
   pytest run into ``prepare_node_dependencies`` using the Python base image,
   where ``npm`` does not exist.
3. Env synthesis: substring heuristics mis-typed numeric/boolean settings
   (``ACCESS_TOKEN_EXPIRE_MINUTES`` -> secret, ``MONGODB_MAX_POOL_SIZE`` -> URL,
   ``AI_OBJ_EXPORT`` -> port), crashing typed settings during import preflight.
"""
import json
import os

from app.services.profiler.repo_profiler import RepoProfiler
from app.services.profiler.env_synthesizer import EnvSynthesizer
from app.services.sandbox_service import SandboxService, DEFAULT_PYTHON_IMAGE


def _make_polyglot_repo(root: str) -> None:
    """Root Vite/Node frontend beside a Python backend with a real test suite."""
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "vision3d-frontend", "scripts": {"test": "vitest run"}}, f)
    with open(os.path.join(root, ".env.example"), "w", encoding="utf-8") as f:
        f.write("ACCESS_TOKEN_EXPIRE_MINUTES=30\nMONGODB_MAX_POOL_SIZE=50\nAI_OBJ_EXPORT=true\n")

    backend = os.path.join(root, "backend")
    os.makedirs(os.path.join(backend, "tests"))
    os.makedirs(os.path.join(backend, "app", "models"))
    with open(os.path.join(backend, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("pytest>=7.0.0\nfastapi\n")
    with open(os.path.join(backend, "pytest.ini"), "w", encoding="utf-8") as f:
        f.write("[pytest]\ntestpaths = tests\n")
    with open(os.path.join(backend, "tests", "test_api.py"), "w", encoding="utf-8") as f:
        f.write("def test_api():\n    assert True\n")
    with open(os.path.join(backend, "app", "models", "enums.py"), "w", encoding="utf-8") as f:
        f.write("class JobStatus:\n    pass\n")


def test_polyglot_repo_routes_changed_backend_file_to_backend(tmp_path):
    _make_polyglot_repo(str(tmp_path))
    profiler = RepoProfiler()
    profile = profiler.profile_repository(str(tmp_path))

    strategy = profiler.evaluate_test_strategy(
        str(tmp_path), ["backend/app/models/enums.py"], profile
    )
    assert strategy.subproject_path == "backend"
    assert strategy.container_workdir == "/workspace/backend"
    assert strategy.test_command == "pytest"
    assert strategy.language == "python"


def test_nested_untested_package_does_not_outrank_project_root(tmp_path):
    _make_polyglot_repo(str(tmp_path))
    profiler = RepoProfiler()
    profile = profiler.profile_repository(str(tmp_path))

    # A change deep inside an untested package directory must still resolve to
    # the enclosing tested project, not the inner directory.
    strategy = profiler.evaluate_test_strategy(
        str(tmp_path), ["backend/app/models/enums.py"], profile
    )
    assert strategy.subproject_path == "backend"
    assert strategy.status == "READY"
    assert strategy.test_files_count == 1


def test_root_catchall_not_selected_over_nested_tested_project(tmp_path):
    _make_polyglot_repo(str(tmp_path))
    profiler = RepoProfiler()
    profile = profiler.profile_repository(str(tmp_path))

    # Root-level (non-source) changes must not pick the recursive root catch-all
    # when a real nested project owns the tests.
    strategy = profiler.evaluate_test_strategy(str(tmp_path), [], profile)
    assert strategy.subproject_path == "backend"
    assert strategy.container_workdir == "/workspace/backend"


def test_python_framework_wins_over_stray_root_package_json(tmp_path):
    _make_polyglot_repo(str(tmp_path))
    profiler = RepoProfiler()
    profile = profiler.profile_repository(str(tmp_path))

    strategy = profiler.evaluate_test_strategy(str(tmp_path), [], profile)
    assert strategy.language == "python"
    assert strategy.test_command == "pytest"


def test_classify_dependency_ecosystem_respects_framework_over_manifest(tmp_path):
    root = str(tmp_path)
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "fe"}, f)

    classify = SandboxService.classify_dependency_ecosystem

    # The regression: a pytest strategy in a dir holding a stray package.json
    # must never be classified as a Node project.
    assert classify("pytest", DEFAULT_PYTHON_IMAGE, root) == "python"
    assert classify("unittest", "python:3.11-slim", root) == "python"

    # Framework/image stays authoritative for genuine Node runs.
    assert classify("node", "node:20-slim", None) == "node"
    assert classify("npm test", "node:20-slim", None) == "node"
    assert classify("vitest", "node:20-slim", root) == "node"

    # Manifest presence only matters when the strategy is genuinely ambiguous.
    assert classify(None, None, root) == "node"

    # Other ecosystems are unaffected.
    assert classify("maven", "maven:3.9-eclipse-temurin-17", None) == "java"
    assert classify("cargo", "rust:1.77-slim", None) == "rust"
    assert classify(None, None, None) == "none"


def test_env_synthesizer_types_numeric_and_boolean_fields():
    keys = {
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "MONGODB_MAX_POOL_SIZE",
        "MONGODB_MIN_POOL_SIZE",
        "AI_OBJ_EXPORT",
        "PORT",
        "LOG_LEVEL",
        "JWT_SECRET",
        "DATABASE_URL",
    }
    env = EnvSynthesizer.synthesize_dummy_env_vars(keys, {"LOG_LEVEL": "info"})

    # Numeric/duration fields must parse as integers.
    for numeric_key in (
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "MONGODB_MAX_POOL_SIZE",
        "MONGODB_MIN_POOL_SIZE",
    ):
        int(env[numeric_key])

    # Boolean flags must parse as booleans, not ports/secrets/URLs.
    assert env["AI_OBJ_EXPORT"] == "false"

    # Behaviour preserved for the existing contract.
    assert env["PORT"] == "3000"
    assert env["LOG_LEVEL"] == "info"
    assert env["JWT_SECRET"] == "devrescue_dummy_test_secret_32bytes_mock"
    assert env["DATABASE_URL"] == "sqlite:///:memory:"

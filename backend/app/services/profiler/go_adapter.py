import os
import re
from typing import List, Optional, Tuple, Set

from app.schemas.test_strategy import SubprojectProfile, TestStrategyContract
from app.services.profiler.base import (
    BaseLanguageAdapter,
    is_ignored_directory,
    safe_relpath,
    to_container_workdir
)


class GoAdapter(BaseLanguageAdapter):
    """
    Adapter for Go projects.
    Supports Go modules, workspaces (go.work), and 'go test ./...'.
    """

    @property
    def name(self) -> str:
        return "go"

    @property
    def default_image(self) -> str:
        return "golang:1.22-alpine"

    def find_test_files(self, project_dir: str, rel_path: str = "") -> List[str]:
        """Discovers *_test.go files."""
        test_files: List[str] = []
        if not os.path.isdir(project_dir):
            return test_files

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d) and d != "vendor"]
            for file in files:
                if file.endswith("_test.go"):
                    full = os.path.join(root, file)
                    rel = safe_relpath(full, project_dir)
                    if rel_path:
                        rel = f"{rel_path.strip('/')}/{rel}"
                    test_files.append(rel)
        return sorted(test_files)

    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """Detects Go runtime version from go.mod and resolves image."""
        go_mod_path = os.path.join(project_dir, "go.mod")
        version = None
        if os.path.isfile(go_mod_path):
            try:
                with open(go_mod_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                m = re.search(r"^go\s+([0-9]+(?:\.[0-9]+)?)", content, re.MULTILINE)
                if m:
                    version = m.group(1)
            except Exception:
                pass

        image = self.default_image
        if version:
            m = re.match(r"^1\.(\d+)", version)
            if m:
                minor = int(m.group(1))
                if minor in (20, 21, 22, 23):
                    image = f"golang:1.{minor}-alpine"

        return version, image

    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """Detects if directory contains a Go project."""
        go_mod_path = os.path.join(project_dir, "go.mod")
        has_go_mod = os.path.isfile(go_mod_path)

        test_files = self.find_test_files(project_dir, rel_path)

        if not has_go_mod and not test_files:
            return None

        evidence = []
        if has_go_mod:
            evidence.append("Found go.mod")

        is_monorepo = False
        if os.path.isfile(os.path.join(repo_root, "go.work")):
            is_monorepo = True
            evidence.append("Found go.work (Go workspace)")

        lockfile_path = None
        go_sum = os.path.join(project_dir, "go.sum")
        if os.path.isfile(go_sum):
            lockfile_path = safe_relpath(go_sum, repo_root)
            evidence.append("Found go.sum")

        evidence.append(f"Discovered {len(test_files)} Go test file(s)")

        runtime_ver, docker_image = self.resolve_runtime_and_image(project_dir, repo_root)

        return SubprojectProfile(
            path=rel_path,
            language="go",
            runtime_version=runtime_ver,
            build_tool="go",
            manifest_path=safe_relpath(go_mod_path, repo_root) if has_go_mod else None,
            lockfile_path=lockfile_path,
            test_framework="go test",
            test_config_path=safe_relpath(go_mod_path, repo_root) if has_go_mod else None,
            test_files=test_files,
            test_files_count=len(test_files),
            test_command="go test ./...",
            docker_image=docker_image,
            is_monorepo=is_monorepo,
            confidence=1.0 if (has_go_mod and len(test_files) > 0) else 0.8,
            evidence=evidence
        )

    def resolve_test_strategy(
        self,
        profile: SubprojectProfile,
        changed_files: List[str]
    ) -> TestStrategyContract:
        """Builds a validated TestStrategyContract for Go."""
        workdir = to_container_workdir(profile.path)
        test_files = profile.test_files
        count = len(test_files)
        evidence = list(profile.evidence)

        if count == 0:
            status = "NO_TESTS_FOUND"
            evidence.append("Go project detected, but zero *_test.go files found")
            cmd = "go test ./..."
        else:
            status = "READY"
            cmd = "go test ./..."
            evidence.append(f"Configured 'go test ./...' for {count} test files")

        plan = "Phase 1: go mod download into module cache. Phase 2: isolated execution with --network none."

        return TestStrategyContract(
            subproject_path=profile.path,
            container_workdir=workdir,
            language="go",
            runtime_version=profile.runtime_version,
            manifest_path=profile.manifest_path,
            lockfile_path=profile.lockfile_path,
            package_manager="go",
            test_framework="go test",
            test_config_path=profile.test_config_path,
            discovered_test_files=test_files,
            test_files_count=count,
            test_command=cmd,
            docker_image=profile.docker_image or self.default_image,
            dependency_prep_plan=plan,
            confidence=profile.confidence,
            status=status,
            supporting_evidence=evidence,
            env_var_names=profile.env_var_names
        )


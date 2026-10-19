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


class RustAdapter(BaseLanguageAdapter):
    """
    Adapter for Rust projects.
    Supports Cargo, Cargo workspaces, integration tests, and 'cargo test'.
    """

    @property
    def name(self) -> str:
        return "rust"

    @property
    def default_image(self) -> str:
        return "rust:1.77-slim"

    def find_test_files(self, project_dir: str, rel_path: str = "") -> List[str]:
        """Discovers Rust test files under tests/ or src/ with #[test]."""
        test_files: List[str] = []
        if not os.path.isdir(project_dir):
            return test_files

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d) and d != "target"]
            rel_dir = safe_relpath(root, project_dir)
            in_tests_dir = "tests" in rel_dir.split("/")

            for file in files:
                if not file.endswith(".rs"):
                    continue

                full = os.path.join(root, file)
                rel = safe_relpath(full, project_dir)
                if rel_path:
                    rel = f"{rel_path.strip('/')}/{rel}"

                if in_tests_dir or file.startswith("test_") or file.endswith("_test.rs"):
                    test_files.append(rel)
                else:
                    # Scan file for #[test] or #[cfg(test)]
                    try:
                        with open(full, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        if "#[test]" in content or "#[cfg(test)]" in content:
                            test_files.append(rel)
                    except Exception:
                        pass

        return sorted(test_files)

    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """Detects Rust edition / version from Cargo.toml or toolchain files."""
        version = None
        cargo_path = os.path.join(project_dir, "Cargo.toml")
        if os.path.isfile(cargo_path):
            try:
                with open(cargo_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                m = re.search(r'rust-version\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    version = m.group(1)
                elif 'edition = "2021"' in content:
                    version = "1.77"
            except Exception:
                pass

        return version, self.default_image

    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """Detects if directory contains a Rust Cargo project."""
        cargo_path = os.path.join(project_dir, "Cargo.toml")
        has_cargo = os.path.isfile(cargo_path)

        test_files = self.find_test_files(project_dir, rel_path)

        if not has_cargo and not test_files:
            return None

        evidence = []
        is_monorepo = False
        if has_cargo:
            evidence.append("Found Cargo.toml")
            try:
                with open(cargo_path, "r", encoding="utf-8", errors="replace") as f:
                    if "[workspace]" in f.read():
                        is_monorepo = True
                        evidence.append("Cargo.toml defines [workspace]")
            except Exception:
                pass

        lockfile_path = None
        cargo_lock = os.path.join(project_dir, "Cargo.lock")
        if os.path.isfile(cargo_lock):
            lockfile_path = safe_relpath(cargo_lock, repo_root)
            evidence.append("Found Cargo.lock")

        evidence.append(f"Discovered {len(test_files)} Rust test file(s)")

        runtime_ver, docker_image = self.resolve_runtime_and_image(project_dir, repo_root)

        return SubprojectProfile(
            path=rel_path,
            language="rust",
            runtime_version=runtime_ver,
            build_tool="cargo",
            manifest_path=safe_relpath(cargo_path, repo_root) if has_cargo else None,
            lockfile_path=lockfile_path,
            test_framework="cargo test",
            test_config_path=safe_relpath(cargo_path, repo_root) if has_cargo else None,
            test_files=test_files,
            test_files_count=len(test_files),
            test_command="cargo test",
            docker_image=docker_image,
            is_monorepo=is_monorepo,
            confidence=1.0 if (has_cargo and len(test_files) > 0) else 0.8,
            evidence=evidence
        )

    def resolve_test_strategy(
        self,
        profile: SubprojectProfile,
        changed_files: List[str]
    ) -> TestStrategyContract:
        """Builds a validated TestStrategyContract for Rust."""
        workdir = to_container_workdir(profile.path)
        test_files = profile.test_files
        count = len(test_files)
        evidence = list(profile.evidence)

        if count == 0 and not profile.test_command:
            status = "TESTS_NOT_CONFIGURED"
            cmd = None
        elif count == 0:
            status = "NO_TESTS_FOUND"
            evidence.append("Cargo project detected, but zero test functions or files found")
            cmd = "cargo test"
        else:
            status = "READY"
            cmd = "cargo test"
            evidence.append(f"Configured 'cargo test' for {count} test file(s)")

        plan = "Phase 1: cargo fetch dependencies into offline cache. Phase 2: isolated cargo test --offline execution with --network none."

        return TestStrategyContract(
            subproject_path=profile.path,
            container_workdir=workdir,
            language="rust",
            runtime_version=profile.runtime_version,
            manifest_path=profile.manifest_path,
            lockfile_path=profile.lockfile_path,
            package_manager="cargo",
            test_framework="cargo test",
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


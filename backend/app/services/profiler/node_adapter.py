import os
import re
import json
from typing import List, Optional, Tuple, Set, Dict, Any

from app.schemas.test_strategy import SubprojectProfile, TestStrategyContract
from app.services.profiler.base import (
    BaseLanguageAdapter,
    is_ignored_directory,
    safe_relpath,
    to_container_workdir
)


NODE_TEST_FILE_EXTENSIONS = (
    ".test.js", ".test.jsx", ".test.ts", ".test.tsx", ".test.mjs", ".test.cjs",
    ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx", ".spec.mjs", ".spec.cjs"
)


class NodeAdapter(BaseLanguageAdapter):
    """
    Adapter for JavaScript and TypeScript projects.
    Supports npm, yarn, pnpm, Jest, Vitest, Mocha, and monorepo workspaces.
    """

    @property
    def name(self) -> str:
        return "javascript"

    @property
    def default_image(self) -> str:
        return os.environ.get("DEVRESCUE_NODE_TEST_IMAGE", "node:20-slim")

    def find_test_files(self, project_dir: str, rel_path: str = "") -> List[str]:
        """Discovers test and spec files conforming to JS/TS conventions."""
        test_files: List[str] = []
        if not os.path.isdir(project_dir):
            return test_files

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            in_tests_dir = "__tests__" in root.replace("\\", "/").split("/")

            for file in files:
                file_lower = file.lower()
                is_match = False
                for ext in NODE_TEST_FILE_EXTENSIONS:
                    if file_lower.endswith(ext):
                        is_match = True
                        break

                if not is_match and in_tests_dir:
                    if any(file_lower.endswith(x) for x in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
                        if not file_lower.startswith((".", "_")) and not file_lower.endswith((".d.ts", ".config.js", ".config.ts")):
                            is_match = True

                if is_match:
                    full = os.path.join(root, file)
                    rel = safe_relpath(full, project_dir)
                    if rel_path:
                        rel = f"{rel_path.strip('/')}/{rel}"
                    test_files.append(rel)

        return sorted(test_files)

    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """Detects Node.js runtime version and resolves Docker image."""
        runtime_version = None

        # 1. .nvmrc or .node-version
        for vname in (".nvmrc", ".node-version"):
            for base in (project_dir, repo_root):
                vfile = os.path.join(base, vname)
                if os.path.isfile(vfile):
                    try:
                        with open(vfile, "r", encoding="utf-8") as f:
                            raw = f.read().strip().lstrip("v").strip()
                        if raw:
                            runtime_version = raw
                            break
                    except Exception:
                        pass
            if runtime_version:
                break

        # 2. package.json engines.node
        if not runtime_version:
            pkg_path = os.path.join(project_dir, "package.json")
            if os.path.isfile(pkg_path):
                try:
                    with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
                        data = json.load(f)
                    engines = data.get("engines", {})
                    node_engine = engines.get("node")
                    if node_engine:
                        m = re.search(r"(\d+)(?:\.\d+)?", str(node_engine))
                        if m:
                            runtime_version = m.group(1)
                except Exception:
                    pass

        # Resolve image
        image = self.default_image
        if runtime_version:
            m = re.match(r"^(\d+)", runtime_version)
            if m:
                major = int(m.group(1))
                if major in (16, 18, 20, 22):
                    image = f"node:{major}-slim"

        return runtime_version, image

    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """Detects if project_dir is a Node.js / TypeScript subproject."""
        pkg_path = os.path.join(project_dir, "package.json")
        if not os.path.isfile(pkg_path):
            return None

        evidence = ["Found package.json"]
        pkg_data: Dict[str, Any] = {}
        try:
            with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
                pkg_data = json.load(f)
        except Exception as e:
            evidence.append(f"Failed to parse package.json: {e}")

        # Detect package manager
        package_manager = "npm"
        lockfile_path = None
        if os.path.isfile(os.path.join(project_dir, "pnpm-lock.yaml")) or os.path.isfile(os.path.join(repo_root, "pnpm-workspace.yaml")):
            package_manager = "pnpm"
            lockfile_path = safe_relpath(os.path.join(project_dir, "pnpm-lock.yaml"), repo_root)
            evidence.append("Found pnpm configuration / lockfile")
        elif os.path.isfile(os.path.join(project_dir, "yarn.lock")):
            package_manager = "yarn"
            lockfile_path = safe_relpath(os.path.join(project_dir, "yarn.lock"), repo_root)
            evidence.append("Found yarn.lock")
        elif os.path.isfile(os.path.join(project_dir, "package-lock.json")):
            package_manager = "npm"
            lockfile_path = safe_relpath(os.path.join(project_dir, "package-lock.json"), repo_root)
            evidence.append("Found package-lock.json")

        # Determine language (JavaScript vs TypeScript)
        is_ts = False
        if os.path.isfile(os.path.join(project_dir, "tsconfig.json")):
            is_ts = True
            evidence.append("Found tsconfig.json (TypeScript project)")
        else:
            dev_deps = pkg_data.get("devDependencies", {})
            deps = pkg_data.get("dependencies", {})
            if "typescript" in dev_deps or "typescript" in deps:
                is_ts = True
                evidence.append("TypeScript dependency declared in package.json")

        lang = "typescript" if is_ts else "javascript"

        # Inspect scripts and test dependencies
        scripts = pkg_data.get("scripts", {})
        test_script = scripts.get("test", "").strip()

        dev_deps = pkg_data.get("devDependencies", {})
        deps = pkg_data.get("dependencies", {})
        all_deps = {**deps, **dev_deps}

        test_framework = None
        test_config_path = None

        # Check configuration files first
        jest_configs = ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.json")
        for jc in jest_configs:
            jcp = os.path.join(project_dir, jc)
            if os.path.isfile(jcp):
                test_framework = "jest"
                test_config_path = safe_relpath(jcp, repo_root)
                evidence.append(f"Found Jest config file: {jc}")
                break

        if not test_framework:
            vitest_configs = ("vitest.config.js", "vitest.config.ts", "vitest.config.mjs")
            for vc in vitest_configs:
                vcp = os.path.join(project_dir, vc)
                if os.path.isfile(vcp):
                    test_framework = "vitest"
                    test_config_path = safe_relpath(vcp, repo_root)
                    evidence.append(f"Found Vitest config file: {vc}")
                    break

        if not test_framework:
            # Check package.json test script and dependencies
            t_lower = test_script.lower()
            if "node --test" in t_lower or "node:test" in t_lower:
                test_framework = "node"
                evidence.append("Detected Node.js built-in test runner (node --test) in test script")
            elif "vitest" in t_lower or "vitest" in all_deps:
                test_framework = "vitest"
                evidence.append("Detected Vitest in test script or dependencies")
            elif "jest" in t_lower or "jest" in all_deps:
                test_framework = "jest"
                evidence.append("Detected Jest in test script or dependencies")
            elif "mocha" in t_lower or "mocha" in all_deps:
                test_framework = "mocha"
                evidence.append("Detected Mocha in test script or dependencies")
            elif "playwright" in t_lower or "@playwright/test" in all_deps:
                test_framework = "playwright"
            elif test_script:
                test_framework = "npm"

        # Validate test script usability
        is_test_script_configured = bool(test_script)
        if test_script:
            t_lower = test_script.lower()
            if "no test specified" in t_lower or ("exit 1" in t_lower and "echo" in t_lower):
                is_test_script_configured = False
                evidence.append(f"Default npm placeholder test script detected: '{test_script}'")

        # Discover test files
        test_files = self.find_test_files(project_dir, rel_path)

        # Cross-directory test discovery: if a nested Node subproject has no internal
        # test files, check the repository root for a genuine root test suite
        # (e.g. repo_root/tests/, __tests__/, or *.test.js at the root). This prevents
        # a nested `backend` package from falsely reporting NO_TESTS_FOUND when the
        # repository keeps its tests at the root.
        if not test_files and repo_root and os.path.abspath(project_dir) != os.path.abspath(repo_root):
            root_test_files = self.find_test_files(repo_root, "")
            applicable_root_tests = [
                rt for rt in root_test_files
                if (rt.startswith("tests/") or rt.startswith("test/")
                    or rt.startswith("__tests__/") or "/" not in rt)
                and not rt.startswith(rel_path + "/")
            ]
            if applicable_root_tests:
                test_files = applicable_root_tests
                evidence.append(
                    f"Discovered {len(applicable_root_tests)} repository test file(s) in root/parent test suite"
                )

        evidence.append(f"Discovered {len(test_files)} test file(s) under {project_dir}")

        test_command = None
        if is_test_script_configured:
            test_command = f"{package_manager} test"
        elif test_framework in ("jest", "vitest", "mocha") and len(test_files) > 0:
            test_command = f"npx {test_framework}"
            evidence.append(f"No package.json test script, but {test_framework} test files exist; using 'npx {test_framework}'")
        elif test_framework == "node" and len(test_files) > 0:
            test_command = "node --test"
            evidence.append("No package.json test script, but Node test files exist; using 'node --test'")

        # Monorepo / workspace check
        is_monorepo = False
        if "workspaces" in pkg_data:
            is_monorepo = True
            evidence.append("package.json declares 'workspaces'")
        elif os.path.isfile(os.path.join(repo_root, "pnpm-workspace.yaml")):
            is_monorepo = True

        runtime_ver, docker_image = self.resolve_runtime_and_image(project_dir, repo_root)

        confidence = 1.0 if (is_test_script_configured and len(test_files) > 0) else 0.8

        return SubprojectProfile(
            path=rel_path,
            language=lang,
            runtime_version=runtime_ver,
            build_tool=package_manager,
            manifest_path=safe_relpath(pkg_path, repo_root),
            lockfile_path=lockfile_path,
            test_framework=test_framework,
            test_config_path=test_config_path,
            test_files=test_files,
            test_files_count=len(test_files),
            test_command=test_command,
            docker_image=docker_image,
            is_monorepo=is_monorepo,
            confidence=confidence,
            evidence=evidence
        )

    def resolve_test_strategy(
        self,
        profile: SubprojectProfile,
        changed_files: List[str]
    ) -> TestStrategyContract:
        """Builds a validated TestStrategyContract for Node.js / TypeScript."""
        workdir = to_container_workdir(profile.path)
        test_files = profile.test_files
        count = len(test_files)
        evidence = list(profile.evidence)

        if not profile.test_command and count == 0:
            status = "TESTS_NOT_CONFIGURED"
            evidence.append("No runnable test script or test files configured in Node project")
            cmd = None
        elif profile.test_command and count == 0:
            status = "NO_TESTS_FOUND"
            evidence.append(
                f"Test command '{profile.test_command}' is configured, but 0 test files were discovered. "
                "Execution must accurately report NO_TESTS_FOUND if runner finds 0 tests."
            )
            cmd = profile.test_command
        else:
            status = "READY"
            cmd = profile.test_command or "npm test"
            evidence.append(f"Configured test command '{cmd}' for {count} discovered test file(s)")

        pm = profile.build_tool or "npm"
        plan = f"Phase 1: {pm} install inside isolated container (staged /node_deps). Phase 2: isolated execution with --network none."

        return TestStrategyContract(
            subproject_path=profile.path,
            container_workdir=workdir,
            language=profile.language,
            runtime_version=profile.runtime_version,
            manifest_path=profile.manifest_path,
            lockfile_path=profile.lockfile_path,
            package_manager=pm,
            test_framework=profile.test_framework,
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


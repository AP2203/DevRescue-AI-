import os
import re
import fnmatch
import configparser
from typing import List, Optional, Tuple, Set

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None

from app.schemas.test_strategy import SubprojectProfile, TestStrategyContract
from app.services.profiler.base import (
    BaseLanguageAdapter,
    is_ignored_directory,
    safe_relpath,
    to_container_workdir
)


DEFAULT_TEST_PATTERNS = [
    "test_*.py",
    "*_test.py",
    "test*.py",
    "tests.py",
    "test.py",
    "*_tests.py",
    "*test.py"
]

STANDARD_TEST_DIRS = {
    "tests", "test", "testing", "__tests__", "unit_tests",
    "integration_tests", "functional_tests", "e2e_tests"
}


class PythonAdapter(BaseLanguageAdapter):
    """
    Adapter for Python projects.
    Supports pytest, unittest, poetry, pipenv, and standard pip packages.
    Performs recursive test discovery, parses pytest/tox/setup/pyproject configs,
    and supports cross-directory / monorepo test strategies.
    """

    @property
    def name(self) -> str:
        return "python"

    @property
    def default_image(self) -> str:
        return os.environ.get("DEVRESCUE_PYTHON_TEST_IMAGE", "devrescue-python-test:3.11")

    def _has_python_files(self, directory: str) -> bool:
        """Checks if directory contains any .py files directly or in subdirectories."""
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            for f in files:
                if f.endswith(".py"):
                    return True
        return False

    def _has_conftest(self, directory: str) -> bool:
        """Returns True if directory contains a conftest.py (pytest suite marker)."""
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]
            if "conftest.py" in files:
                return True
        return False

    def _declares_pytest(self, project_dir: str) -> Optional[str]:
        """
        Scans dependency manifests and lockfiles (requirements*.txt, Pipfile,
        Pipfile.lock, poetry.lock, uv.lock, setup.py, setup.cfg) for a declared
        pytest dependency. Returns the declaring filename, or None.
        """
        if not os.path.isdir(project_dir):
            return None
        try:
            names = os.listdir(project_dir)
        except Exception:
            return None

        candidates = []
        for fname in names:
            low = fname.lower()
            if (low.endswith(".txt") and "requirements" in low):
                candidates.append(fname)
            elif fname in (
                "Pipfile", "Pipfile.lock", "poetry.lock", "uv.lock",
                "setup.py", "setup.cfg"
            ):
                candidates.append(fname)

        for fname in candidates:
            try:
                with open(os.path.join(project_dir, fname), "r", encoding="utf-8", errors="replace") as f:
                    if "pytest" in f.read().lower():
                        return fname
            except Exception:
                continue
        return None

    def _parse_pytest_config(self, project_dir: str) -> Tuple[List[str], List[str]]:
        """
        Parses testpaths and python_files patterns from configuration files:
        - pytest.ini, .pytest.ini
        - setup.cfg
        - tox.ini
        - pyproject.toml
        Returns (testpaths, python_files_patterns).
        """
        testpaths: List[str] = []
        python_files: List[str] = []

        # 1. pytest.ini / .pytest.ini
        for ininame in ("pytest.ini", ".pytest.ini"):
            inipath = os.path.join(project_dir, ininame)
            if os.path.isfile(inipath):
                cp = configparser.ConfigParser()
                try:
                    cp.read(inipath, encoding="utf-8")
                    if cp.has_section("pytest"):
                        if cp.has_option("pytest", "testpaths"):
                            raw = cp.get("pytest", "testpaths")
                            testpaths.extend(re.split(r"[\s,]+", raw.strip()))
                        if cp.has_option("pytest", "python_files"):
                            raw = cp.get("pytest", "python_files")
                            python_files.extend(re.split(r"[\s,]+", raw.strip()))
                except Exception:
                    pass

        # 2. setup.cfg or tox.ini
        for cfgname in ("setup.cfg", "tox.ini"):
            cfgpath = os.path.join(project_dir, cfgname)
            if os.path.isfile(cfgpath):
                cp = configparser.ConfigParser()
                try:
                    cp.read(cfgpath, encoding="utf-8")
                    section = None
                    for candidate in ("tool:pytest", "pytest"):
                        if cp.has_section(candidate):
                            section = candidate
                            break
                    if section:
                        if cp.has_option(section, "testpaths"):
                            raw = cp.get(section, "testpaths")
                            testpaths.extend(re.split(r"[\s,]+", raw.strip()))
                        if cp.has_option(section, "python_files"):
                            raw = cp.get(section, "python_files")
                            python_files.extend(re.split(r"[\s,]+", raw.strip()))
                except Exception:
                    pass

        # 3. pyproject.toml
        pyproj = os.path.join(project_dir, "pyproject.toml")
        if os.path.isfile(pyproj):
            if tomllib is not None:
                try:
                    with open(pyproj, "rb") as f:
                        data = tomllib.load(f)
                    tool = data.get("tool", {})
                    pytest_cfg = tool.get("pytest", {}).get("ini_options", {})
                    if isinstance(pytest_cfg, dict):
                        tp = pytest_cfg.get("testpaths", [])
                        if isinstance(tp, list):
                            testpaths.extend([str(x).strip() for x in tp if str(x).strip()])
                        elif isinstance(tp, str):
                            testpaths.extend(re.split(r"[\s,]+", tp.strip()))
                        pf = pytest_cfg.get("python_files", [])
                        if isinstance(pf, list):
                            python_files.extend([str(x).strip() for x in pf if str(x).strip()])
                        elif isinstance(pf, str):
                            python_files.extend(re.split(r"[\s,]+", pf.strip()))
                except Exception:
                    pass
            else:
                try:
                    with open(pyproj, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    m_tp = re.search(r'testpaths\s*=\s*\[([^\]]+)\]', content)
                    if m_tp:
                        items = re.findall(r'["\']([^"\']+)["\']', m_tp.group(1))
                        testpaths.extend(items)
                    m_pf = re.search(r'python_files\s*=\s*\[([^\]]+)\]', content)
                    if m_pf:
                        items = re.findall(r'["\']([^"\']+)["\']', m_pf.group(1))
                        python_files.extend(items)
                except Exception:
                    pass

        clean_testpaths = [t.strip() for t in testpaths if t.strip()]
        clean_python_files = [p.strip() for p in python_files if p.strip()]
        return clean_testpaths, clean_python_files

    def find_test_files(
        self,
        project_dir: str,
        rel_path: str = "",
        custom_testpaths: Optional[List[str]] = None,
        custom_patterns: Optional[List[str]] = None
    ) -> List[str]:
        """
        Recursively discovers Python test files relative to the project directory
        and repo root, respecting custom testpaths and python_files patterns.
        Discovers test_*.py, *_test.py, test*.py, tests.py, and all .py files in test dirs.
        """
        test_files: List[str] = []
        if not os.path.isdir(project_dir):
            return test_files

        if custom_testpaths is None or custom_patterns is None:
            cfg_paths, cfg_pats = self._parse_pytest_config(project_dir)
            if custom_testpaths is None:
                custom_testpaths = cfg_paths
            if custom_patterns is None:
                custom_patterns = cfg_pats

        patterns = list(custom_patterns) if custom_patterns else list(DEFAULT_TEST_PATTERNS)

        test_dir_names = set(STANDARD_TEST_DIRS)
        if custom_testpaths:
            for tp in custom_testpaths:
                clean_tp = tp.replace("\\", "/").strip("/").lower()
                if clean_tp:
                    test_dir_names.add(clean_tp)
                    # Also add basename if nested like tests/unit
                    test_dir_names.add(clean_tp.split("/")[-1])

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not is_ignored_directory(d)]

            rel_root = safe_relpath(root, project_dir).lower()
            root_parts = set(rel_root.split("/")) if rel_root else set()
            in_test_dir = bool(root_parts & test_dir_names)

            for file in files:
                if not file.endswith(".py"):
                    continue
                if file in ("__init__.py", "conftest.py", "setup.py"):
                    continue

                matches_pattern = any(fnmatch.fnmatch(file, pat) for pat in patterns)

                if matches_pattern or in_test_dir:
                    full = os.path.join(root, file)
                    rel = safe_relpath(full, project_dir)
                    if rel_path:
                        rel = f"{rel_path.strip('/')}/{rel}"
                    test_files.append(rel)

        return sorted(list(set(test_files)))

    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """Detects Python runtime version and resolves Docker image."""
        runtime_version = None

        # 1. .python-version
        pv_file = os.path.join(project_dir, ".python-version")
        if not os.path.isfile(pv_file):
            pv_file = os.path.join(repo_root, ".python-version")
        if os.path.isfile(pv_file):
            try:
                with open(pv_file, "r", encoding="utf-8") as f:
                    runtime_version = f.read().strip()
            except Exception:
                pass

        # 2. runtime.txt
        if not runtime_version:
            rt_file = os.path.join(project_dir, "runtime.txt")
            if not os.path.isfile(rt_file):
                rt_file = os.path.join(repo_root, "runtime.txt")
            if os.path.isfile(rt_file):
                try:
                    with open(rt_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    m = re.search(r"python-([0-9\.]+)", content, re.IGNORECASE)
                    if m:
                        runtime_version = m.group(1)
                except Exception:
                    pass

        # 3. pyproject.toml requires-python
        if not runtime_version:
            pyproj = os.path.join(project_dir, "pyproject.toml")
            if os.path.isfile(pyproj):
                try:
                    with open(pyproj, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
                    if m:
                        runtime_version = m.group(1)
                except Exception:
                    pass

        return runtime_version, self.default_image

    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """Detects if project_dir is a Python subproject."""
        if not os.path.isdir(project_dir):
            return None

        # Test directories themselves are not independent subprojects
        base_dir_name = os.path.basename(project_dir.rstrip("/\\")).lower()
        if rel_path and base_dir_name in STANDARD_TEST_DIRS:
            return None

        manifest_candidates = [
            ("pyproject.toml", "pyproject"),
            ("Pipfile", "pipenv"),
            ("setup.py", "setuptools"),
            ("setup.cfg", "setuptools"),
            ("requirements.txt", "pip"),
            ("requirements-dev.txt", "pip"),
            ("requirements-test.txt", "pip"),
            ("test-requirements.txt", "pip"),
        ]

        found_manifest = None
        build_tool = None
        lockfile_path = None
        evidence = []

        for m_name, b_tool in manifest_candidates:
            p = os.path.join(project_dir, m_name)
            if os.path.isfile(p):
                if not found_manifest:
                    found_manifest = safe_relpath(p, repo_root)
                    build_tool = b_tool
                evidence.append(f"Found manifest {m_name}")

        # Check lockfiles
        if os.path.isfile(os.path.join(project_dir, "poetry.lock")):
            lockfile_path = safe_relpath(os.path.join(project_dir, "poetry.lock"), repo_root)
            build_tool = "poetry"
            evidence.append("Found poetry.lock")
        elif os.path.isfile(os.path.join(project_dir, "Pipfile.lock")):
            lockfile_path = safe_relpath(os.path.join(project_dir, "Pipfile.lock"), repo_root)
            build_tool = "pipenv"
            evidence.append("Found Pipfile.lock")

        # Check for pyproject.toml build tool specifics
        pyproj_path = os.path.join(project_dir, "pyproject.toml")
        if os.path.isfile(pyproj_path):
            try:
                with open(pyproj_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                if "[tool.poetry]" in content:
                    build_tool = "poetry"
                    evidence.append("pyproject.toml specifies [tool.poetry]")
                elif "[tool.flit" in content:
                    build_tool = "flit"
                elif "[tool.hatch" in content:
                    build_tool = "hatch"
            except Exception:
                pass

        config_checks = [
            ("pytest.ini", "pytest"),
            ("setup.cfg", "pytest"),
            ("tox.ini", "pytest"),
            (".pytest.ini", "pytest")
        ]
        has_test_config = any(os.path.isfile(os.path.join(project_dir, c[0])) for c in config_checks)

        # Parse custom testpaths and python_files patterns
        custom_testpaths, custom_patterns = self._parse_pytest_config(project_dir)
        if custom_testpaths:
            evidence.append(f"Parsed testpaths from configuration: {', '.join(custom_testpaths)}")
        if custom_patterns:
            evidence.append(f"Parsed python_files from configuration: {', '.join(custom_patterns)}")

        # If no manifest was found and directory has no python files or test config, it cannot be a Python subproject
        has_py_files = self._has_python_files(project_dir)
        if not found_manifest and not has_py_files and not has_test_config:
            return None

        test_files = self.find_test_files(
            project_dir,
            rel_path,
            custom_testpaths=custom_testpaths,
            custom_patterns=custom_patterns
        )

        # Cross-directory test discovery: If Python subproject has no internal test files,
        # check repo_root for genuine root test suite (e.g. repo_root/tests/ or repo_root/test/)
        if not test_files and repo_root and os.path.abspath(project_dir) != os.path.abspath(repo_root):
            root_test_files = self.find_test_files(repo_root, "")
            # Only consider genuine root-level tests (e.g. tests/*, test/*, test_*.py at root)
            applicable_root_tests = [
                rt for rt in root_test_files
                if (rt.startswith("tests/") or rt.startswith("test/") or "/" not in rt)
                and not rt.startswith(rel_path + "/")
            ]
            if applicable_root_tests:
                test_files = applicable_root_tests
                evidence.append(
                    f"Discovered {len(applicable_root_tests)} repository test file(s) in root/parent test suite"
                )

        if not found_manifest and not has_py_files and not test_files and not has_test_config:
            return None

        # Detect test framework and test configuration
        test_framework = None
        test_config_path = None
        test_command = None

        for cname, fw in config_checks:
            cp = os.path.join(project_dir, cname)
            if os.path.isfile(cp):
                test_framework = fw
                test_config_path = safe_relpath(cp, repo_root)
                evidence.append(f"Found test configuration {cname}")
                break

        if not test_framework and os.path.isfile(pyproj_path):
            try:
                with open(pyproj_path, "r", encoding="utf-8", errors="replace") as f:
                    c = f.read().lower()
                if "tool.pytest" in c:
                    test_framework = "pytest"
                    test_config_path = safe_relpath(pyproj_path, repo_root)
                    evidence.append("pyproject.toml contains tool.pytest configuration")
            except Exception:
                pass

        if not test_framework:
            # Check requirements for pytest
            for fname in os.listdir(project_dir):
                if (fname.startswith("requirements") and fname.endswith(".txt")) or fname in ("test-requirements.txt", "requirements-dev.txt"):
                    rp = os.path.join(project_dir, fname)
                    if os.path.isfile(rp):
                        try:
                            with open(rp, "r", encoding="utf-8", errors="replace") as f:
                                if "pytest" in f.read().lower():
                                    test_framework = "pytest"
                                    evidence.append(f"{fname} specifies pytest dependency")
                                    break
                        except Exception:
                            pass

        # Check pyproject.toml poetry/optional/dev dependency groups for pytest
        if not test_framework and os.path.isfile(pyproj_path):
            try:
                with open(pyproj_path, "r", encoding="utf-8", errors="replace") as f:
                    if "pytest" in f.read().lower():
                        test_framework = "pytest"
                        test_config_path = safe_relpath(pyproj_path, repo_root)
                        evidence.append("pyproject.toml declares a pytest dependency")
            except Exception:
                pass

        # Check additional manifests/lockfiles (Pipfile, poetry.lock, uv.lock, setup.*) for pytest
        if not test_framework:
            declaring = self._declares_pytest(project_dir)
            if declaring:
                test_framework = "pytest"
                evidence.append(f"{declaring} declares pytest dependency")

        # conftest.py is a strong pytest suite signal
        if not test_framework and self._has_conftest(project_dir):
            test_framework = "pytest"
            evidence.append("Found conftest.py indicating a pytest test suite")

        # Record alternative runners for transparency (evidence only; pytest is the
        # runner available in the sandbox image unless config declares otherwise).
        if os.path.isfile(os.path.join(project_dir, "noxfile.py")):
            evidence.append("Found noxfile.py (nox test sessions)")
        if os.path.isfile(os.path.join(project_dir, "tox.ini")):
            evidence.append("Found tox.ini test environment configuration")

        # Check if discovered test files use unittest
        uses_unittest = False
        if test_files:
            for s_rel in test_files[:5]:
                s_full = os.path.join(repo_root, s_rel) if repo_root else os.path.join(project_dir, s_rel)
                if not os.path.isfile(s_full):
                    s_full = os.path.join(project_dir, s_rel)
                if os.path.isfile(s_full):
                    try:
                        with open(s_full, "r", encoding="utf-8", errors="replace") as sf:
                            s_body = sf.read()
                        if "unittest.TestCase" in s_body or "import unittest" in s_body or "from unittest" in s_body:
                            uses_unittest = True
                            break
                    except Exception:
                        pass

        if not test_framework and uses_unittest:
            test_framework = "unittest"
            test_command = "python -m unittest discover"
            evidence.append("Discovered unittest test cases; configured python -m unittest discover")
        elif not test_framework and test_files:
            test_framework = "pytest"
            test_command = "pytest"
            evidence.append("Discovered Python test files; defaulting to pytest")
        elif test_framework == "pytest":
            test_command = "pytest"
        elif test_framework == "unittest":
            test_command = "python -m unittest discover"
        elif test_framework:
            test_command = "python -m unittest discover"

        runtime_ver, docker_image = self.resolve_runtime_and_image(project_dir, repo_root)

        # Monorepo detection: check if sibling directories also have manifests
        parent_dir = os.path.dirname(project_dir)
        is_monorepo = False
        if parent_dir and parent_dir != repo_root and os.path.isdir(parent_dir):
            siblings = [d for d in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, d))]
            if len(siblings) > 1:
                is_monorepo = True

        confidence = 1.0 if (found_manifest and test_files) else (0.8 if found_manifest or test_files else 0.5)

        return SubprojectProfile(
            path=rel_path,
            language="python",
            runtime_version=runtime_ver,
            build_tool=build_tool or "pip",
            manifest_path=found_manifest,
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
        """Builds a validated TestStrategyContract for Python."""
        workdir = to_container_workdir(profile.path)
        test_files = profile.test_files
        count = len(test_files)
        evidence = list(profile.evidence)

        if not profile.test_framework and count == 0 and not profile.test_command:
            status = "TESTS_NOT_CONFIGURED"
            evidence.append("No test suite configuration or test files found in Python subproject")
            cmd = None
        elif (profile.test_framework or profile.test_command) and count == 0:
            status = "NO_TESTS_FOUND"
            fw = profile.test_framework or "python"
            evidence.append(f"Configured test framework '{fw}' but 0 test files were discovered")
            cmd = profile.test_command or "pytest"
        else:
            status = "READY"
            cmd = profile.test_command or "pytest"
            # If subproject is nested (e.g. 'backend') but test files reside in repo root (e.g. 'tests/...'),
            # format container command to point directly to the test folder so runner finds them.
            if profile.path and test_files and not test_files[0].startswith(profile.path + "/"):
                top_folder = test_files[0].split("/")[0]
                if cmd == "pytest":
                    cmd = f"pytest /workspace/{top_folder}"
                elif "unittest" in cmd:
                    cmd = f"python -m unittest discover -s /workspace/{top_folder}"
            evidence.append(f"Configured {cmd} for {count} test files")

        plan = "Phase 1: pip install requirements into isolated container. Phase 2: isolated execution with --network none."
        if profile.build_tool == "poetry":
            plan = "Phase 1: poetry install/wheel staging. Phase 2: isolated pytest execution with --network none."

        return TestStrategyContract(
            subproject_path=profile.path,
            container_workdir=workdir,
            language="python",
            runtime_version=profile.runtime_version,
            manifest_path=profile.manifest_path,
            lockfile_path=profile.lockfile_path,
            package_manager=profile.build_tool or "pip",
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

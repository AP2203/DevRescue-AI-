import os
import re
import json
import time
import shutil
import asyncio
import logging
import tempfile
import subprocess
import ast
import posixpath
import shlex
from typing import Dict, Any, List, Optional, Tuple, Set

from app.services.github_service import (
    github_service,
    GitHubError,
    GitHubAuthError,
    GitHubPermissionError,
    GitHubRateLimitError
)
import hashlib
from app.services.diff_validator import diff_validator, DiffApplicationError, DiffValidationError
from app.schemas.sandbox import SandboxTestResponse

logger = logging.getLogger("devrescue.sandbox")

DEFAULT_PYTHON_IMAGE = os.environ.get("DEVRESCUE_PYTHON_TEST_IMAGE", "devrescue-python-test:3.11")
DEFAULT_NODE_IMAGE = os.environ.get("DEVRESCUE_NODE_TEST_IMAGE", "node:20-slim")


class TestFrameworkResult(tuple):
    """
    Result of test framework detection.
    Unpacks as 3-tuple (command, workdir, image) for backwards compatibility.
    Provides explicit attributes: command, workdir, image, framework.
    """
    command: Optional[str]
    workdir: Optional[str]
    image: Optional[str]
    framework: Optional[str]

    def __new__(cls, command: Optional[str], workdir: Optional[str], image: Optional[str], framework: Optional[str] = None):
        instance = super().__new__(cls, (command, workdir, image))
        instance.command = command
        instance.workdir = workdir
        instance.image = image
        instance.framework = framework or (
            "pytest" if command == "pytest" else
            "unittest" if command and "unittest" in command else
            "npm" if command == "npm test" else command
        )
        return instance


class PrepDependenciesResult(tuple):
    """
    Result of dependency preparation stage.
    Unpacks as 2-tuple (image, error) for backwards compatibility.
    Provides explicit attributes: image, error, stdout, stderr, exit_code,
    last_50_lines, timed_out, manifest_name, install_cmd, manifest_sha256, manifest_size.
    """
    image: str
    error: Optional[str]
    stdout: str
    stderr: str
    exit_code: Optional[int]
    last_50_lines: str
    timed_out: bool
    manifest_name: Optional[str]
    install_cmd: Optional[str]
    manifest_sha256: Optional[str]
    manifest_size: Optional[int]

    def __new__(
        cls,
        image: str,
        error: Optional[str] = None,
        stdout: str = "",
        stderr: str = "",
        exit_code: Optional[int] = 0,
        last_50_lines: str = "",
        timed_out: bool = False,
        manifest_name: Optional[str] = None,
        install_cmd: Optional[str] = None,
        manifest_sha256: Optional[str] = None,
        manifest_size: Optional[int] = None
    ):
        instance = super().__new__(cls, (image, error))
        instance.image = image
        instance.error = error
        instance.stdout = stdout
        instance.stderr = stderr
        instance.exit_code = exit_code
        instance.last_50_lines = last_50_lines
        instance.timed_out = timed_out
        instance.manifest_name = manifest_name
        instance.install_cmd = install_cmd
        instance.manifest_sha256 = manifest_sha256
        instance.manifest_size = manifest_size
        return instance


def normalize_container_path(path: Optional[str]) -> str:
    """
    Normalizes container paths to POSIX standard, eliminating duplicate slashes,
    Windows backslashes, and redundant relative parts.
    E.g. '//workspace/backend' -> '/workspace/backend'
         'workspace\\backend' -> '/workspace/backend'
         '/workspace' -> '/workspace'
    """
    if not path:
        return "/workspace"
    clean = str(path).replace("\\", "/").strip()
    normalized = posixpath.normpath(clean)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    while normalized.startswith("//"):
        normalized = normalized[1:]
    return normalized


def flatten_nested_root_folder(target_dir: str) -> None:
    """
    If target_dir contains only a single directory and no non-hidden files,
    moves all contents of that nested directory into target_dir so repository
    files sit directly at the root.
    """
    if not os.path.isdir(target_dir):
        return
    try:
        entries = os.listdir(target_dir)
        non_hidden = [e for e in entries if not e.startswith(".")]
        if len(non_hidden) == 1:
            folder_name = non_hidden[0]
            # If the folder is named backend, frontend, src, etc., it is a project directory, not a wrapper
            if folder_name.lower() in (
                "backend", "frontend", "src", "app", "client", "server",
                "api", "web", "packages", "tests", "test", "lib", "core",
                "services", "docs", "cmd", "pkg"
            ):
                return
            nested = os.path.join(target_dir, folder_name)
            if os.path.isdir(nested):
                files_in_root = [e for e in entries if os.path.isfile(os.path.join(target_dir, e))]
                if not files_in_root:
                    logger.info(f"[SANDBOX] Flattening nested root directory '{folder_name}' into '{target_dir}'")
                    temp_stage = tempfile.mkdtemp(prefix="flatten_stage_", dir=os.path.dirname(target_dir))
                    try:
                        for item in os.listdir(nested):
                            shutil.move(os.path.join(nested, item), os.path.join(temp_stage, item))
                        shutil.rmtree(nested, ignore_errors=True)
                        for item in os.listdir(temp_stage):
                            shutil.move(os.path.join(temp_stage, item), os.path.join(target_dir, item))
                    finally:
                        shutil.rmtree(temp_stage, ignore_errors=True)
    except Exception as e:
        logger.warning(f"[SANDBOX] Failed to flatten nested root directory in {target_dir}: {e}")


def extract_last_n_lines(text: str, n: int = 50) -> str:
    """Extracts the final N lines of a string without truncation."""
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def extract_failure_traceback(stdout: str, stderr: Optional[str] = None) -> Optional[str]:
    """
    Extracts the most specific and actionable traceback or collection error
    from test execution output (stdout and stderr).
    Preserves exact conftest collection errors, ModuleNotFoundError,
    ImportError, and full tracebacks without truncation of critical lines.
    """
    combined = f"{stdout or ''}\n{stderr or ''}".strip()
    if not combined:
        return None

    # 1. Look for Pytest conftest loading error:
    # Starts with "ImportError while loading conftest" and ends at "E   <Error>: <msg>"
    m_conftest = re.search(
        r"(ImportError while loading conftest[^\n]*\n[\s\S]*?E\s+[A-Za-z0-9_.]+(?:Error|Exception):[^\n]+)",
        combined
    )
    if m_conftest:
        return m_conftest.group(1).strip()

    # Generic conftest loading block search if regex didn't catch trailing line
    if "ImportError while loading conftest" in combined:
        lines = combined.splitlines()
        extracted_lines = []
        capturing = False
        for line in lines:
            if "ImportError while loading conftest" in line:
                capturing = True
            if capturing:
                extracted_lines.append(line)
                if line.startswith("E   ") or (len(extracted_lines) > 2 and line.startswith("===")):
                    if line.startswith("==="):
                        extracted_lines.pop()
                    break
        if extracted_lines:
            return "\n".join(extracted_lines).strip()

    # 2. Look for Pytest error collecting block:
    m_collect = re.search(
        r"(ERROR collecting [^\n]*\n[\s\S]*?E\s+[A-Za-z0-9_.]+(?:Error|Exception):[^\n]+)",
        combined
    )
    if m_collect:
        return m_collect.group(1).strip()

    # 3. Look for Python Traceback:
    m_tb = re.findall(
        r"(Traceback \(most recent call last\):[\s\S]*?(?:^[A-Za-z0-9_.]+(?:Error|Exception):[^\n]+))",
        combined,
        re.MULTILINE
    )
    if m_tb:
        return m_tb[-1].strip()

    # 4. Look for preflight import error or warning:
    m_preflight = re.search(
        r"(PREFLIGHT_(?:IMPORT_)?(?:ERROR|WARNING|MISSING_MODULES):[^\n]*(?:\n[ \t]+[^\n]*|\nTraceback[\s\S]*?(?:^[A-Za-z0-9_.]+(?:Error|Exception):[^\n]+))?)",
        combined,
        re.MULTILINE
    )
    if m_preflight:
        return m_preflight.group(1).strip()

    # 5. Look for standalone ModuleNotFoundError / ImportError lines:
    m_import_err = re.findall(
        r"((?:ModuleNotFoundError|ImportError):[^\n]+)",
        combined
    )
    if m_import_err:
        return m_import_err[-1].strip()

    # 6. Fallback to last non-empty lines:
    non_empty = [ln for ln in combined.splitlines() if ln.strip()]
    if non_empty:
        return "\n".join(non_empty[-15:]).strip()

    return None


def parse_test_metrics(test_cmd: Optional[str], stdout: str, stderr: Optional[str] = None) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Extracts (tests_run, tests_passed, tests_failed) from test runner output.
    Supports Pytest, Jest/Vitest, and unittest across stdout and stderr.
    """
    combined = f"{stdout or ''}\n{stderr or ''}"
    if not combined.strip():
        return None, None, None

    # 1. Pytest regex: e.g. "5 passed, 1 failed in 2.3s" or "10 passed in 1.1s"
    passed_m = re.search(r'(\d+)\s+passed', combined)
    failed_m = re.search(r'(\d+)\s+failed', combined)
    skipped_m = re.search(r'(\d+)\s+skipped', combined)
    error_m = re.search(r'(\d+)\s+errors?', combined)

    if passed_m or failed_m:
        p = int(passed_m.group(1)) if passed_m else 0
        f = int(failed_m.group(1)) if failed_m else 0
        s = int(skipped_m.group(1)) if skipped_m else 0
        e = int(error_m.group(1)) if error_m else 0
        tests_passed = p
        tests_failed = f + e
        tests_run = p + f + s + e
        return tests_run, tests_passed, tests_failed

    # 2. Jest regex: "Tests:  1 failed, 4 passed, 5 total"
    jest_total = re.search(r'Tests:\s+.*?(\d+)\s+total', combined)
    jest_passed = re.search(r'Tests:\s+.*?(\d+)\s+passed', combined)
    jest_failed = re.search(r'Tests:\s+.*?(\d+)\s+failed', combined)
    if jest_total or jest_passed or jest_failed:
        tests_run = int(jest_total.group(1)) if jest_total else None
        tests_passed = int(jest_passed.group(1)) if jest_passed else 0
        tests_failed = int(jest_failed.group(1)) if jest_failed else 0
        return tests_run, tests_passed, tests_failed

    # 3. Vitest regex: "Tests  1 failed | 4 passed (5)" or "Tests  4 passed (4)"
    vitest_m = re.search(r'Tests\s+(?:(\d+)\s+failed\s*\|?\s*)?(?:(\d+)\s+passed\s*\|?\s*)?(?:(\d+)\s+skipped\s*\|?\s*)?\((\d+)\)', combined)
    if vitest_m:
        f = int(vitest_m.group(1)) if vitest_m.group(1) else 0
        p = int(vitest_m.group(2)) if vitest_m.group(2) else 0
        total = int(vitest_m.group(4))
        return total, p, f

    # 4. Unittest: "Ran 5 tests in ... OK" or "FAILED (failures=1)"
    unittest_m = re.search(r'Ran\s+(\d+)\s+tests?', combined)
    if unittest_m:
        tests_run = int(unittest_m.group(1))
        if "OK" in combined:
            tests_passed = tests_run
            tests_failed = 0
        elif "FAILED" in combined:
            failures_m = re.search(r'failures=(\d+)', combined)
            errors_m = re.search(r'errors=(\d+)', combined)
            f = int(failures_m.group(1)) if failures_m else 0
            e = int(errors_m.group(1)) if errors_m else 0
            tests_failed = f + e
            tests_passed = max(0, tests_run - tests_failed)
        else:
            tests_passed = tests_run
            tests_failed = 0
        return tests_run, tests_passed, tests_failed

    return None, None, None


def parse_test_duration(test_cmd: Optional[str], stdout: str, stderr: Optional[str] = None) -> Optional[float]:
    """
    Parses test runner output to extract the actual test execution duration reported by the test runner.
    Supports Pytest, Jest, Vitest, and unittest across stdout and stderr.
    Examples:
      Pytest: "=== 65 passed in 16.14s ===" -> 16.14
      Jest: "Time: 16.14 s" -> 16.14
      Vitest: "Duration 16.14s" -> 16.14
      Unittest: "Ran 5 tests in 0.012s" -> 0.01
    """
    combined = f"{stdout or ''}\n{stderr or ''}"
    if not combined.strip():
        return None

    # 1. Pytest summary lines:
    # e.g. "65 passed in 16.14s", "65 passed, 1 warning in 16.14s", "1 failed in 2.34s"
    pytest_m = re.search(r'(?:passed|failed|skipped|errors?|warnings?)[^\n]*\bin\s+([0-9]+(?:\.[0-9]+)?)\s*s\b', combined, re.IGNORECASE)
    if pytest_m:
        try:
            return round(float(pytest_m.group(1)), 2)
        except ValueError:
            pass

    # Generic Pytest footer banner: e.g. "=== ... in 16.14s ==="
    pytest_footer = re.search(r'={3,}.*?\bin\s+([0-9]+(?:\.[0-9]+)?)\s*s\b.*?={3,}', combined, re.IGNORECASE)
    if pytest_footer:
        try:
            return round(float(pytest_footer.group(1)), 2)
        except ValueError:
            pass

    # 2. Jest: e.g. "Time:        16.14 s" or "Time: 2.345s"
    jest_m = re.search(r'Time:\s+([0-9]+(?:\.[0-9]+)?)\s*s\b', combined, re.IGNORECASE)
    if jest_m:
        try:
            return round(float(jest_m.group(1)), 2)
        except ValueError:
            pass

    # 3. Vitest: e.g. "Duration  16.14s" or "Duration 16.14 s"
    vitest_m = re.search(r'Duration\s+([0-9]+(?:\.[0-9]+)?)\s*s\b', combined, re.IGNORECASE)
    if vitest_m:
        try:
            return round(float(vitest_m.group(1)), 2)
        except ValueError:
            pass

    # 4. Unittest: e.g. "Ran 5 tests in 0.012s"
    unittest_m = re.search(r'Ran\s+\d+\s+tests?\s+in\s+([0-9]+(?:\.[0-9]+)?)\s*s\b', combined, re.IGNORECASE)
    if unittest_m:
        try:
            return round(float(unittest_m.group(1)), 2)
        except ValueError:
            pass

    return None


def _sanitize_error(err: Any) -> str:
    """Removes sensitive credentials, tokens, or cookie values from error messages."""
    msg = str(err)
    msg = re.sub(r'gh[opsu]_[A-Za-z0-9_]{16,}', '[REDACTED_TOKEN]', msg)
    msg = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED]', msg, flags=re.IGNORECASE)
    msg = re.sub(r'devrescue_[a-zA-Z0-9_\-]+=[A-Za-z0-9_\-]+', 'session=[REDACTED]', msg)
    return msg


class SandboxService:
    """
    Isolated execution sandbox service for running untrusted repository code
    and test suites in containerized Docker isolation.
    Enforces security constraints:
    - --network none
    - Resource limits (CPU, Memory, PIDs)
    - Strict execution timeout
    - No mounting host directories, secrets, or docker socket
    - No privileged mode
    """

    def __init__(self):
        self.cpu_limit: float = 2.0
        self.memory_limit: str = "2g"
        self.pids_limit: int = 100
        self.timeout_seconds: int = 120
        self.dependency_timeout_seconds: int = int(os.environ.get("DEVRESCUE_DEPENDENCY_TIMEOUT_SECONDS", "600"))
        self.network_enabled: bool = False
        self._pip_version_cache: Dict[str, str] = {}
        self._python_version_cache: Dict[str, str] = {}

    def check_docker_available(self) -> Tuple[bool, Optional[str]]:
        """
        Validates whether Docker CLI and Docker daemon are reachable.
        Returns (is_available, error_message).
        """
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0:
                return True, None
            err = res.stderr.strip() or res.stdout.strip() or "Docker daemon returned non-zero exit code."
            return False, f"Docker daemon unreachable: {err[:200]}"
        except FileNotFoundError:
            return False, "Docker CLI executable not found on host PATH."
        except subprocess.TimeoutExpired:
            return False, "Docker info check timed out after 10 seconds."
        except Exception as e:
            return False, f"Failed to check Docker status: {str(e)}"

    def check_image_available(self, image: str) -> bool:
        """
        Validates if Docker image is locally cached and available in the Docker daemon.
        Does not attempt to pull over the network under isolation.
        """
        if not image:
            return False
        try:
            res = subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode != 0:
                err_text = (res.stderr or res.stdout).lower()
                if "no such image" in err_text or "not found" in err_text:
                    return False
            return res.returncode == 0
        except Exception:
            return True

    def get_docker_build_cmd(self, tag: str, dockerfile_path: str, context_dir: str) -> List[str]:
        """
        Constructs standard docker build command with no unsupported resource flags (--cpus, --memory).
        Docker BuildKit / buildx does not support --cpus or --memory directly on 'docker build'.
        """
        return [
            "docker", "build",
            "-t", tag,
            "-f", dockerfile_path,
            context_dir
        ]

    def build_python_test_image(
        self,
        image_name: str = DEFAULT_PYTHON_IMAGE,
        dockerfile_path: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Builds the version-pinned Python test image with pytest before isolated execution.
        Executed only when network is available and controlled.
        """
        is_avail, daemon_err = self.check_docker_available()
        if not is_avail:
            return False, daemon_err or "Docker daemon unavailable."

        target_df = dockerfile_path
        created_temp = False
        context_dir = None
        if not target_df or not os.path.isfile(target_df):
            candidates = [
                os.path.join(os.getcwd(), "docker", "Dockerfile.python-test"),
                os.path.join(os.getcwd(), "backend", "docker", "Dockerfile.python-test"),
            ]
            for c in candidates:
                if os.path.isfile(c):
                    target_df = c
                    context_dir = os.path.dirname(c)
                    break

        if not target_df or not os.path.isfile(target_df):
            context_dir = tempfile.mkdtemp(prefix="devrescue_pybuild_")
            created_temp = True
            target_df = os.path.join(context_dir, "Dockerfile")
            with open(target_df, "w", encoding="utf-8") as f:
                f.write(
                    "FROM python:3.11-slim\n"
                    "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1\n"
                    "RUN pip install --no-cache-dir pytest==8.3.4\n"
                    "WORKDIR /workspace\n"
                    "CMD [\"pytest\"]\n"
                )

        try:
            build_cmd = self.get_docker_build_cmd(image_name, target_df, context_dir or os.getcwd())
            res = subprocess.run(
                build_cmd,
                capture_output=True,
                text=True,
                timeout=180
            )
            if res.returncode == 0:
                logger.info(f"[SANDBOX] Built Python test image '{image_name}' successfully.")
                return True, None
            err_msg = _sanitize_error(res.stderr or res.stdout)
            logger.error(f"[SANDBOX] Failed to build Python test image '{image_name}': {err_msg}")
            return False, err_msg
        except Exception as e:
            err_msg = _sanitize_error(e)
            logger.error(f"[SANDBOX] Exception building Python test image '{image_name}': {err_msg}")
            return False, err_msg
        finally:
            if created_temp and context_dir:
                shutil.rmtree(context_dir, ignore_errors=True)


    async def _execute_docker_cmd(
        self,
        docker_cmd: List[str],
        timeout: Optional[int] = None
    ) -> Tuple[int, str, str]:
        """
        Executes Docker subprocess asynchronously.
        Supports ProactorEventLoop and provides seamless fallback on Windows SelectorEventLoop.
        Streams stdout and stderr in real-time for package download progress, dependency resolution,
        and build diagnostics, while capturing exact returncode, stdout, and stderr.
        """
        effective_timeout = timeout if timeout is not None else self.timeout_seconds
        # Prevent Git Bash / MSYS2 on Windows from converting POSIX container paths
        # (e.g. /workspace → C:/Program Files/Git/workspace) in subprocess arguments.
        subprocess_env = dict(os.environ)
        subprocess_env["MSYS_NO_PATHCONV"] = "1"
        subprocess_env["MSYS2_ARG_CONV_EXCL"] = "*"
        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=subprocess_env
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=effective_timeout
                )
            except (asyncio.TimeoutError, TimeoutError):
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                raise asyncio.TimeoutError(f"Docker command timed out after {effective_timeout}s")

            stdout = (
                stdout_bytes.decode("utf-8", errors="replace")
                if isinstance(stdout_bytes, (bytes, bytearray))
                else str(stdout_bytes or "")
            )
            stderr = (
                stderr_bytes.decode("utf-8", errors="replace")
                if isinstance(stderr_bytes, (bytes, bytearray))
                else str(stderr_bytes or "")
            )

            # Log sanitized output for package download progress, dependency resolution, and diagnostics
            for line in (stdout + "\n" + stderr).splitlines():
                cl = line.strip()
                if cl:
                    logger.info(f"[SANDBOX:STREAM] {_sanitize_error(cl)}")

            return proc.returncode, stdout, stderr
        except NotImplementedError:
            logger.info("[SANDBOX] Asynchronous subprocess not implemented on current event loop, running via thread pool.")
            def _sync_exec():
                res = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                    env=subprocess_env
                )
                return res.returncode, res.stdout, res.stderr
            return await asyncio.to_thread(_sync_exec)

    async def ensure_base_image_available(self, image: str) -> Tuple[bool, Optional[str]]:
        """
        Verifies if base image exists locally.
        If missing, pulls the image (or builds if default Python image) while network
        access is permitted in Phase A preparation stage.
        Returns (is_available, error_message).
        """
        if not image:
            return False, "No container image specified."

        if self.check_image_available(image):
            return True, None

        docker_avail, docker_reason = self.check_docker_available()
        if not docker_avail:
            return False, f"Docker daemon unavailable: {docker_reason}"

        logger.info(f"[SANDBOX] Base image '{image}' not cached locally. Attempting to retrieve in Phase A preparation...")
        print(f"[SANDBOX] Base image '{image}' not cached locally. Attempting to retrieve in Phase A preparation...", flush=True)

        if image == DEFAULT_PYTHON_IMAGE:
            built_ok, build_err = self.build_python_test_image(image)
            if built_ok and self.check_image_available(image):
                return True, None
            return False, f"Could not build Python test image '{image}': {build_err}"

        # Pull image over network during Phase A
        try:
            pull_cmd = ["docker", "pull", image]
            exit_code, stdout, stderr = await self._execute_docker_cmd(pull_cmd, timeout=180)
            if exit_code == 0 and self.check_image_available(image):
                logger.info(f"[SANDBOX] Successfully retrieved base image '{image}' in Phase A.")
                return True, None
            err_detail = _sanitize_error(stderr.strip() or stdout.strip())
            return False, f"Failed to pull base image '{image}': {err_detail}"
        except Exception as e:
            err_msg = _sanitize_error(e)
            return False, f"Exception while pulling base image '{image}': {err_msg}"

    def get_docker_status(self) -> Dict[str, Any]:
        """Returns structured status of Docker daemon and sandbox environment."""
        is_avail, reason = self.check_docker_available()
        return {
            "docker_available": is_avail,
            "status": "READY" if is_avail else "UNAVAILABLE",
            "environment": "Docker Container (Isolated --network none)" if is_avail else "None (Docker unavailable)",
            "message": reason,
            "default_image": DEFAULT_PYTHON_IMAGE,
            "timeout_seconds": self.timeout_seconds,
            "dependency_timeout_seconds": self.dependency_timeout_seconds,
            "network_enabled": self.network_enabled
        }

    def _is_ignored_dir(self, dirname: str) -> bool:
        ignored = {
            ".git", ".venv", "venv", "node_modules", "__pycache__",
            ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
            ".next", ".nuxt", ".output", ".cache", "coverage", ".idea", ".vscode"
        }
        return dirname in ignored or (dirname.startswith(".") and dirname not in (".", ".."))

    def _has_python_test_files(self, directory: str) -> bool:
        """Checks if a directory contains any test_*.py or *_test.py files."""
        if not os.path.isdir(directory):
            return False
        try:
            for item in os.listdir(directory):
                if item.endswith(".py") and (item.startswith("test_") or item.endswith("_test.py")):
                    return True
        except Exception:
            pass
        return False

    def _inspect_manifest_validity(
        self,
        manifest_path: str,
        base_dir: str
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Inspects whether a manifest exists, is readable, and all referenced
        manifests exist and contain no circular dependencies.
        Returns (is_valid, error_msg, all_referenced_files).
        """
        if not os.path.isfile(manifest_path) or not os.access(manifest_path, os.R_OK):
            return False, f"Manifest file does not exist or is not readable: {manifest_path}", []
        return self._detect_circular_requirements(manifest_path, base_dir=base_dir)

    def _manifest_includes_production_manifest(
        self,
        manifest_path: str,
        referenced_files: List[str],
        project_dir: str
    ) -> bool:
        """
        Inspects candidate manifest and all its referenced includes to determine
        if it includes the project's production requirements (e.g. requirements.txt).
        A dev manifest that references requirements.txt merely wraps production
        dependencies and must not automatically be treated as a lightweight test manifest.
        """
        prod_manifest_names = {
            "requirements.txt",
            "requirements-prod.txt",
            "prod-requirements.txt",
            "requirements_prod.txt"
        }
        manifest_real = os.path.normcase(os.path.realpath(manifest_path))

        # 1. Check all transitively referenced files
        for ref in referenced_files:
            ref_real = os.path.normcase(os.path.realpath(ref))
            if ref_real != manifest_real:
                ref_basename = os.path.basename(ref).lower()
                if ref_basename in prod_manifest_names:
                    return True

        # 2. Also inspect direct lines in manifest_path (and any referenced file)
        # for explicit -r references pointing to production manifest names
        all_to_scan = [manifest_path] + [f for f in referenced_files if os.path.isfile(f)]
        for fpath in set(all_to_scan):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_clean = line.strip()
                        if not line_clean or line_clean.startswith("#"):
                            continue
                        if line_clean.startswith("-r") or line_clean.startswith("--requirement"):
                            parts = line_clean.split(None, 2)
                            if len(parts) >= 2:
                                target = os.path.basename(parts[1].strip().strip('"\'')).lower()
                                if target in prod_manifest_names:
                                    return True
            except Exception:
                pass

        return False

    def _find_python_manifest(self, project_dir: str) -> Optional[Tuple[str, str]]:
        """
        Inspects project directory for dependency manifests.
        Maintains priority order:
        1. Genuine test-specific manifests (requirements-test.txt, test-requirements.txt, etc.)
           selected only when they exist and their referenced dependencies are valid.
        2. Development manifests (requirements-dev.txt, dev-requirements.txt)
           inspected to verify they do not merely wrap production requirements.txt.
        3. General application requirements (requirements.txt, pyproject.toml, setup.py, setup.cfg).
        Never inspects or falls back to DevRescue AI's own local requirements.
        Returns (manifest_path, manifest_type) e.g. ('.../requirements-test.txt', 'requirements').
        """
        if not os.path.isdir(project_dir):
            return None

        test_manifest_names = [
            "requirements-test.txt",
            "test-requirements.txt",
            "requirements_test.txt",
            "test_requirements.txt"
        ]
        dev_manifest_names = [
            "requirements-dev.txt",
            "dev-requirements.txt"
        ]
        prod_manifest_names = [
            "requirements.txt"
        ]
        build_manifest_names = [
            ("pyproject.toml", "pyproject"),
            ("setup.py", "setup_py"),
            ("setup.cfg", "setup_cfg")
        ]

        # 1. Prefer genuine test-specific manifests when they exist and have valid references
        for tname in test_manifest_names:
            tpath = os.path.join(project_dir, tname)
            if os.path.isfile(tpath):
                is_valid, _, _ = self._inspect_manifest_validity(tpath, base_dir=project_dir)
                if is_valid:
                    return tpath, "requirements"

        # 2. Inspect development manifests
        dev_wrapping_prod: Optional[str] = None
        for dname in dev_manifest_names:
            dpath = os.path.join(project_dir, dname)
            if os.path.isfile(dpath):
                is_valid, _, ref_files = self._inspect_manifest_validity(dpath, base_dir=project_dir)
                if is_valid:
                    # Check if it merely wraps production requirements
                    if self._manifest_includes_production_manifest(dpath, ref_files, project_dir):
                        # Do not treat as lightweight test manifest; remember as fallback
                        if dev_wrapping_prod is None:
                            dev_wrapping_prod = dpath
                    else:
                        # Standalone dev manifest without production requirements
                        return dpath, "requirements"

        # 3. Check general production requirements
        for pname in prod_manifest_names:
            ppath = os.path.join(project_dir, pname)
            if os.path.isfile(ppath):
                is_valid, _, _ = self._inspect_manifest_validity(ppath, base_dir=project_dir)
                if is_valid:
                    return ppath, "requirements"

        # 4. Check build manifests (pyproject.toml, setup.py, setup.cfg)
        for bname, btype in build_manifest_names:
            bpath = os.path.join(project_dir, bname)
            if os.path.isfile(bpath):
                return bpath, btype

        # 5. If dev manifest wrapping production was found, but no standalone requirements.txt/build manifest,
        # fallback to using it as the project manifest
        if dev_wrapping_prod is not None:
            return dev_wrapping_prod, "requirements"

        # 6. If test or dev manifests exist but had invalid references, return the first existing one
        # so prepare_project_dependencies can report actionable circular/missing include errors
        for all_name in test_manifest_names + dev_manifest_names + prod_manifest_names:
            mpath = os.path.join(project_dir, all_name)
            if os.path.isfile(mpath):
                return mpath, "requirements"

        return None

    def _find_supplemental_test_requirements(
        self,
        project_dir: str,
        primary_manifest_path: str,
        all_referenced_manifests: Optional[List[str]] = None
    ) -> List[str]:
        """
        Discovers supplemental test-specific dependencies declared in secondary manifests
        (e.g. requirements-dev.txt, requirements-test.txt) that are not present in the
        primary manifest (e.g. requirements.txt), but are required by tests or conftest fixtures.
        Prevents conftest collection failures (e.g. missing mongomock-motor, pytest-asyncio, httpx)
        while preserving fast installation via lightweight binary wheels.
        """
        if not os.path.isdir(project_dir) or not os.path.isfile(primary_manifest_path):
            return []

        primary_files = {os.path.normcase(os.path.realpath(primary_manifest_path))}
        if all_referenced_manifests:
            for rf in all_referenced_manifests:
                if os.path.isfile(rf):
                    primary_files.add(os.path.normcase(os.path.realpath(rf)))

        # Collect packages already declared in primary manifest(s)
        existing_pkgs: Set[str] = set()
        for pf in primary_files:
            try:
                with open(pf, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_clean = line.strip()
                        if not line_clean or line_clean.startswith("#") or line_clean.startswith("-"):
                            continue
                        pkg_base = re.split(r'[<>=!~;@\s\[]', line_clean)[0].strip().lower().replace("-", "_")
                        if pkg_base:
                            existing_pkgs.add(pkg_base)
            except Exception:
                pass

        # Look for secondary test/dev manifests
        secondary_manifest_names = [
            "requirements-dev.txt",
            "dev-requirements.txt",
            "requirements-test.txt",
            "test-requirements.txt",
            "requirements_test.txt",
            "test_requirements.txt"
        ]

        supplemental_lines: List[str] = []
        seen_extra_pkgs: Set[str] = set()

        ignored_pure_linters = {"flake8", "black", "ruff", "mypy", "isort", "pre_commit", "pre-commit"}

        for sname in secondary_manifest_names:
            spath = os.path.join(project_dir, sname)
            if not os.path.isfile(spath):
                continue
            s_real = os.path.normcase(os.path.realpath(spath))
            if s_real in primary_files:
                continue

            try:
                with open(spath, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line_clean = line.strip()
                        if not line_clean or line_clean.startswith("#") or line_clean.startswith("-"):
                            continue
                        pkg_raw = re.split(r'[<>=!~;@\s\[]', line_clean)[0].strip()
                        pkg_norm = pkg_raw.lower().replace("-", "_")
                        if not pkg_norm or pkg_norm in existing_pkgs or pkg_norm in seen_extra_pkgs:
                            continue
                        if pkg_norm in ignored_pure_linters:
                            continue

                        seen_extra_pkgs.add(pkg_norm)
                        supplemental_lines.append(line_clean)
            except Exception:
                pass

        return supplemental_lines

    def _has_extra_pip_dependencies(
        self,
        manifest_path: str,
        manifest_type: str,
        all_referenced_manifests: Optional[List[str]] = None
    ) -> bool:
        """
        Checks whether manifest specifies external dependencies beyond standard test runners.
        Recursively inspects all referenced manifests if provided.
        """
        try:
            if manifest_type in ("pyproject", "setup_py", "setup_cfg"):
                return True

            files_to_check = [manifest_path]
            if all_referenced_manifests:
                files_to_check = list(dict.fromkeys([manifest_path] + all_referenced_manifests))

            ignored_packages = {
                "pytest", "pluggy", "iniconfig", "packaging", "setuptools", "wheel"
            }

            clean_lines = []
            for fpath in files_to_check:
                if not os.path.isfile(fpath):
                    continue
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    lines = [line.strip() for line in f.readlines()]
                for line in lines:
                    if not line or line.startswith("#"):
                        continue
                    pkg = line.split("#")[0].strip().lower()
                    # Requirements reference
                    if pkg.startswith("-r") or pkg.startswith("--requirement"):
                        continue
                    # Strip version specifiers and extras
                    pkg_base = re.split(r'[<>=!~;@\s\[]', pkg)[0].strip().lower()
                    if pkg_base in ignored_packages:
                        continue
                    clean_lines.append(pkg)
            return len(clean_lines) > 0
        except Exception:
            return True

    def _get_codebase_imports(self, project_dir: str) -> Set[str]:
        """
        Scans Python source and test files in project_dir to discover all top-level imported module names.
        """
        imported: Set[str] = set()
        if not os.path.isdir(project_dir):
            return imported

        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(d)]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    tree = ast.parse(content, filename=file_path)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                imported.add(name.name.split(".")[0].lower())
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imported.add(node.module.split(".")[0].lower())
                except Exception:
                    try:
                        for match in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z0-9_]+)", content, re.MULTILINE):
                            imported.add(match.group(1).lower())
                    except Exception:
                        pass
        return imported

    def _prune_unneeded_manifest_dependencies(
        self,
        manifest_content: str,
        manifest_basename: str,
        project_dir: str
    ) -> str:
        """
        Preserves original manifest dependencies without silent pruning.
        AST scanning is intentionally disabled to prevent stripping indirect
        or dynamically imported packages needed by the application or tests.
        """
        return manifest_content

    def get_pip_version(self, image: str = DEFAULT_PYTHON_IMAGE) -> str:
        """
        Dynamically inspects and caches the pip version inside the specified Docker image.
        Returns a sanitized version string (e.g. 'pip 24.0').
        """
        if image in self._pip_version_cache:
            return self._pip_version_cache[image]

        try:
            res = subprocess.run(
                ["docker", "run", "--rm", image, "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0 and res.stdout.strip():
                raw_ver = res.stdout.strip().split("\n")[0].strip()
                self._pip_version_cache[image] = raw_ver
                return raw_ver
        except Exception as e:
            logger.debug(f"[SANDBOX] Failed to inspect pip version for {image}: {e}")

        fallback = "pip 24.0 (detected)"
        self._pip_version_cache[image] = fallback
        return fallback

    def get_python_version(self, image: str = DEFAULT_PYTHON_IMAGE) -> str:
        """
        Dynamically inspects and caches the Python version inside the specified Docker image.
        Returns a version string (e.g. '3.11.10' or '3.11').
        """
        if hasattr(self, "_python_version_cache") and image in self._python_version_cache:
            return self._python_version_cache[image]
        if not hasattr(self, "_python_version_cache"):
            self._python_version_cache = {}

        try:
            res = subprocess.run(
                ["docker", "run", "--rm", image, "python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0 and res.stdout.strip():
                raw_ver = res.stdout.strip().split("\n")[0].strip()
                self._python_version_cache[image] = raw_ver
                return raw_ver
        except Exception as e:
            logger.debug(f"[SANDBOX] Failed to inspect python version for {image}: {e}")

        fallback = "3.11"
        if ":" in image:
            tag = image.split(":")[-1]
            m = re.search(r"(\d+\.\d+(?:\.\d+)?)", tag)
            if m:
                fallback = m.group(1)
        self._python_version_cache[image] = fallback
        return fallback

    def _verify_staged_manifest(self, source_path: str, staged_path: str) -> Tuple[bool, Optional[str]]:
        """
        Verifies that the staged manifest is a regular file (not a symlink or directory)
        and that its byte content and SHA-256 hash match the source manifest exactly.
        """
        if not os.path.isfile(staged_path):
            return False, f"Staged manifest '{staged_path}' does not exist or is not a regular file."
        if os.path.islink(staged_path):
            return False, f"Staged manifest '{staged_path}' cannot be a symlink."
        if not os.path.isfile(source_path):
            return False, f"Source manifest '{source_path}' does not exist or is not a regular file."

        source_size = os.path.getsize(source_path)
        staged_size = os.path.getsize(staged_path)
        if source_size != staged_size:
            return False, f"Staged manifest byte size ({staged_size}) does not match source ({source_size})."

        with open(source_path, "rb") as sf, open(staged_path, "rb") as tf:
            source_hash = hashlib.sha256(sf.read()).hexdigest()
            staged_hash = hashlib.sha256(tf.read()).hexdigest()

        if source_hash != staged_hash:
            return False, f"Staged manifest SHA-256 hash ({staged_hash}) does not match source ({source_hash})."

        return True, None

    def _detect_circular_requirements(
        self,
        root_manifest_path: str,
        base_dir: Optional[str] = None,
        max_depth: int = 20
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        Parses requirement file(s) starting from root_manifest_path to detect self-referencing
        or circular includes (-r / --requirement).
        Returns (is_valid, error_msg, all_referenced_files).
        all_referenced_files is a list of absolute paths of all valid referenced manifest files
        (including root_manifest_path).
        """
        if not os.path.isabs(root_manifest_path) and base_dir:
            root_manifest_path = os.path.abspath(os.path.join(base_dir, root_manifest_path))
        else:
            root_manifest_path = os.path.abspath(root_manifest_path)

        if not os.path.isfile(root_manifest_path):
            return False, f"Manifest file does not exist: {root_manifest_path}", []

        all_referenced: Set[str] = {os.path.normcase(os.path.realpath(root_manifest_path))}
        raw_referenced_paths: Set[str] = {root_manifest_path}

        def check_file(file_path: str, stack: List[str]) -> Optional[str]:
            real_path = os.path.normcase(os.path.realpath(file_path))
            base_name = os.path.basename(file_path)

            real_stack = [os.path.normcase(os.path.realpath(p)) for p in stack]
            if real_path in real_stack:
                cycle_start = real_stack.index(real_path)
                cycle_names = [os.path.basename(p) for p in stack[cycle_start:]] + [base_name]
                if len(stack) > 0 and real_stack[-1] == real_path:
                    return (
                        f"Self-referencing requirement include detected in '{base_name}': "
                        f"File includes itself via '-r {base_name}'. Infinite recursion prevented."
                    )
                return (
                    f"Circular requirement include detected: "
                    f"{' -> '.join(cycle_names)}. Infinite recursion prevented."
                )

            if len(stack) >= max_depth:
                chain_names = [os.path.basename(p) for p in stack] + [base_name]
                return f"Maximum requirement include depth ({max_depth}) exceeded: {' -> '.join(chain_names)}"

            if not os.path.isfile(file_path):
                parent_name = os.path.basename(stack[-1]) if stack else "manifest"
                return f"Referenced requirement file '{base_name}' from '{parent_name}' does not exist or is not a regular file."

            current_dir = os.path.dirname(os.path.abspath(file_path))
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except Exception as e:
                return f"Failed to read requirement file '{base_name}': {_sanitize_error(e)}"

            next_stack = stack + [file_path]
            for line in lines:
                line_clean = line.strip()
                if not line_clean or line_clean.startswith("#"):
                    continue

                req_match = re.match(r'^(?:-r|--requirement)\s*[=\s]\s*([^\s#]+)', line_clean)
                if not req_match:
                    if line_clean.startswith("-r ") or line_clean.startswith("--requirement "):
                        parts = line_clean.split(None, 2)
                        if len(parts) >= 2:
                            ref_target = parts[1].strip()
                        else:
                            continue
                    else:
                        continue
                else:
                    ref_target = req_match.group(1).strip()

                ref_target = ref_target.strip('"\'')
                if not ref_target:
                    continue

                ref_abs_path = os.path.normpath(os.path.join(current_dir, ref_target))
                all_referenced.add(os.path.normcase(os.path.realpath(ref_abs_path)))
                raw_referenced_paths.add(ref_abs_path)

                err = check_file(ref_abs_path, next_stack)
                if err:
                    return err

            return None

        err = check_file(root_manifest_path, [])
        if err:
            return False, err, list(raw_referenced_paths)

        return True, None, list(raw_referenced_paths)

    async def prepare_project_dependencies(
        self,
        workspace_dir: str,
        rel_workdir: str,
        base_image: str = DEFAULT_PYTHON_IMAGE,
        mount_mode: str = "directory"
    ) -> PrepDependenciesResult:
        """
        Prepares a project-specific test image in an isolated build stage with resource limits
        and no secrets. Does NOT execute arbitrary scripts or install packages on the host.
        Supports both directory bind mount (/tmp/deps_manifest) and single-file bind mount (/tmp/<manifest>).
        Returns PrepDependenciesResult(image, error, stdout, stderr, exit_code, last_50_lines, timed_out, manifest_name, install_cmd).
        """
        host_project_dir = os.path.join(workspace_dir, rel_workdir) if rel_workdir else workspace_dir
        manifest_info = self._find_python_manifest(host_project_dir)
        if not manifest_info and host_project_dir != workspace_dir:
            manifest_info = self._find_python_manifest(workspace_dir)

        if not manifest_info:
            return PrepDependenciesResult(base_image, None)

        manifest_path, manifest_type = manifest_info

        # Validate that the selected manifest exists and is readable before starting
        if not os.path.isfile(manifest_path) or not os.access(manifest_path, os.R_OK):
            err_msg = f"Dependency manifest does not exist or is not readable: {manifest_path}"
            logger.error(f"[SANDBOX] {err_msg}")
            return PrepDependenciesResult(
                base_image,
                error=err_msg,
                stderr=err_msg,
                exit_code=1,
                last_50_lines=err_msg,
                manifest_name=os.path.basename(manifest_path)
            )

        manifest_basename = os.path.basename(manifest_path)
        logger.info(f"[SANDBOX] Selected dependency manifest: '{manifest_basename}' in '{host_project_dir}'")
        print(f"[SANDBOX] Selected dependency manifest: '{manifest_basename}' in '{host_project_dir}'", flush=True)

        # Detect self-referencing or circular requirement includes before proceeding
        is_valid_reqs, circ_err, all_referenced_manifests = self._detect_circular_requirements(
            manifest_path,
            base_dir=host_project_dir
        )
        if not is_valid_reqs:
            logger.error(f"[SANDBOX] Circular or invalid requirement include detected: {circ_err}")
            return PrepDependenciesResult(
                base_image,
                error=circ_err,
                stderr=circ_err,
                exit_code=1,
                last_50_lines=circ_err,
                manifest_name=manifest_basename
            )

        if not self._has_extra_pip_dependencies(manifest_path, manifest_type, all_referenced_manifests):
            return PrepDependenciesResult(base_image, None, manifest_name=manifest_basename)

        # Read manifest content and calculate exact SHA-256 and byte size
        try:
            with open(manifest_path, "rb") as f:
                raw_manifest_bytes = f.read()
            manifest_content = raw_manifest_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            err_msg = f"Failed to read dependency manifest: {_sanitize_error(e)}"
            return PrepDependenciesResult(
                base_image,
                error=err_msg,
                stderr=err_msg,
                exit_code=1,
                last_50_lines=err_msg,
                manifest_name=manifest_basename
            )

        manifest_sha256 = hashlib.sha256(raw_manifest_bytes).hexdigest()
        manifest_size = len(raw_manifest_bytes)
        effective_manifest_content = manifest_content

        referenced_hashes = []
        for ref_f in sorted(all_referenced_manifests):
            if os.path.isfile(ref_f):
                try:
                    with open(ref_f, "rb") as rf:
                        f_sha = hashlib.sha256(rf.read()).hexdigest()
                    referenced_hashes.append(f"{os.path.basename(ref_f)}:{f_sha}")
                except Exception:
                    pass
        combined_ref_hash = ";".join(referenced_hashes)

        # Discover supplemental test requirements from secondary manifests (e.g. requirements-dev.txt)
        supplemental_reqs = self._find_supplemental_test_requirements(
            host_project_dir,
            manifest_path,
            all_referenced_manifests
        )
        supp_hash = hashlib.sha256("\n".join(sorted(supplemental_reqs)).encode("utf-8")).hexdigest()[:8] if supplemental_reqs else ""

        python_version = self.get_python_version(base_image)
        pip_options = "pip=timeout30_retries3_prefer_binary_noprogress"
        cache_key_raw = f"base={base_image}::python={python_version}::manifest={manifest_sha256}::refs={combined_ref_hash}::supp={supp_hash}::opts={pip_options}"
        cache_hash = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()[:16]
        derived_tag = f"devrescue-proj-deps:{cache_hash}"

        start_prep_time = time.time()

        # If already cached locally, reuse
        if self.check_image_available(derived_tag):
            elapsed_sec = round(time.time() - start_prep_time, 2)
            logger.info(f"[SANDBOX] Cache HIT: Reusing existing cached dependency image '{derived_tag}' (cache key={cache_hash}). Elapsed: {elapsed_sec}s.")
            print(f"[SANDBOX] Cache HIT: Reusing existing cached dependency image '{derived_tag}' (cache key={cache_hash}). Elapsed: {elapsed_sec}s.", flush=True)
            return PrepDependenciesResult(
                derived_tag,
                None,
                manifest_name=manifest_basename,
                manifest_sha256=manifest_sha256,
                manifest_size=manifest_size
            )

        logger.info(f"[SANDBOX] Cache MISS: No existing cached dependency image '{derived_tag}' found. Preparing dependencies...")
        print(f"[SANDBOX] Cache MISS: No existing cached dependency image '{derived_tag}' found. Preparing dependencies...", flush=True)

        # Isolated build stage: strictly isolate build context with only the manifest file
        build_ctx = os.path.abspath(tempfile.mkdtemp(prefix="devrescue_deps_build_"))
        container_name = f"devrescue_prep_{cache_hash}_{int(time.time())}"
        try:
            staged_manifest_path = os.path.join(build_ctx, manifest_basename)
            with open(staged_manifest_path, "wb") as f:
                f.write(raw_manifest_bytes)

            # Stage all legitimately referenced requirement files (preserving relative path structure)
            manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
            for ref_abs_path in all_referenced_manifests:
                if os.path.normcase(os.path.realpath(ref_abs_path)) == os.path.normcase(os.path.realpath(manifest_path)):
                    continue
                if os.path.isfile(ref_abs_path):
                    try:
                        rel_ref = os.path.relpath(ref_abs_path, manifest_dir)
                    except ValueError:
                        rel_ref = os.path.basename(ref_abs_path)
                    if not rel_ref.startswith(".."):
                        dest_ref_path = os.path.join(build_ctx, rel_ref)
                    else:
                        dest_ref_path = os.path.join(build_ctx, os.path.basename(ref_abs_path))
                    os.makedirs(os.path.dirname(dest_ref_path), exist_ok=True)
                    with open(ref_abs_path, "rb") as rf, open(dest_ref_path, "wb") as wf:
                        wf.write(rf.read())

            # Verify staged manifest integrity (regular file, byte equality, sha256 equality)
            is_staged_valid, stage_err = self._verify_staged_manifest(manifest_path, staged_manifest_path)
            if not is_staged_valid:
                logger.error(f"[SANDBOX] Staged manifest verification failed: {stage_err}")
                return PrepDependenciesResult(
                    base_image,
                    error=stage_err,
                    stderr=stage_err,
                    exit_code=1,
                    last_50_lines=stage_err,
                    manifest_name=manifest_basename,
                    manifest_sha256=manifest_sha256,
                    manifest_size=manifest_size
                )

            supp_manifest_name: Optional[str] = None
            if supplemental_reqs:
                supp_manifest_name = "devrescue-supp-test-deps.txt"
                supp_staged_path = os.path.join(build_ctx, supp_manifest_name)
                with open(supp_staged_path, "w", encoding="utf-8") as sf:
                    sf.write("\n".join(supplemental_reqs) + "\n")
                mount_mode = "directory"

            # Also generate Dockerfile in build_ctx for inspection or fallback
            df_path = os.path.join(build_ctx, "Dockerfile")
            with open(df_path, "w", encoding="utf-8") as df:
                df_cmd = f"RUN pip install --no-cache-dir --prefer-binary --default-timeout 30 --retries 3 --progress-bar off -r {manifest_basename}"
                if supp_manifest_name:
                    df_cmd += f" -r {supp_manifest_name}"
                df.write(
                    f"FROM {base_image}\n"
                    f"COPY . /tmp/deps_manifest/\n"
                    f"WORKDIR /tmp/deps_manifest\n"
                    f"{df_cmd}\n"
                )

            if mount_mode == "file":
                file_source = staged_manifest_path.replace("\\", "/")
                container_file_path = f"/tmp/{manifest_basename}"
                mount_opt = f"type=bind,source={file_source},target={container_file_path},readonly"
                pip_target = container_file_path
                container_workdir = "/tmp"
                mount_target = container_file_path
                pip_install_cmd = f"pip install --no-cache-dir --prefer-binary --default-timeout 30 --retries 3 --progress-bar off -r {pip_target}"
            else:
                dir_source = build_ctx.replace("\\", "/")
                container_file_path = f"/tmp/deps_manifest/{manifest_basename}"
                mount_opt = f"type=bind,source={dir_source},target=/tmp/deps_manifest,readonly"
                pip_target = container_file_path
                container_workdir = "/tmp/deps_manifest"
                mount_target = "/tmp/deps_manifest"
                pip_install_cmd = f"pip install --no-cache-dir --prefer-binary --default-timeout 30 --retries 3 --progress-bar off -r {pip_target}"
                if supp_manifest_name:
                    pip_install_cmd += f" -r /tmp/deps_manifest/{supp_manifest_name}"

            sanitized_install_cmd = _sanitize_error(pip_install_cmd)
            pip_version = self.get_pip_version(base_image)

            # Log all diagnostic parameters
            logger.info(
                f"[SANDBOX] Dependency staging diagnostics:\n"
                f"  - Selected manifest: {manifest_basename}\n"
                f"  - Referenced manifests: {[os.path.basename(p) for p in all_referenced_manifests]}\n"
                f"  - Supplemental test packages: {supplemental_reqs}\n"
                f"  - SHA-256: {manifest_sha256}\n"
                f"  - Byte size: {manifest_size} bytes\n"
                f"  - Base image: {base_image} (Python {python_version})\n"
                f"  - Cache tag: {derived_tag} (key={cache_hash})\n"
                f"  - Sanitized pip command: {sanitized_install_cmd}\n"
                f"  - Pip version: {pip_version}\n"
                f"  - Container working directory: {container_workdir}\n"
                f"  - Mount target: {mount_target}"
            )
            print(
                f"[SANDBOX] Dependency staging diagnostics: manifest={manifest_basename}, "
                f"refs={[os.path.basename(p) for p in all_referenced_manifests]}, "
                f"sha256={manifest_sha256}, size={manifest_size}B, base={base_image}, "
                f"python={python_version}, cache_key={cache_hash}, pip={pip_version}, "
                f"workdir={container_workdir}, mount={mount_target}, cmd='{sanitized_install_cmd}'",
                flush=True
            )

            prep_cmd = [
                "docker", "run",
                "--name", container_name,
                "--cpus", str(self.cpu_limit),
                "--memory", str(self.memory_limit),
                "--pids-limit", str(self.pids_limit),
                "--security-opt", "no-new-privileges:true",
                "--workdir", container_workdir,
                "--mount", mount_opt,
                base_image,
                "sh", "-c", pip_install_cmd
            ]
            try:
                exit_code, stdout, stderr = await self._execute_docker_cmd(
                    prep_cmd,
                    timeout=self.dependency_timeout_seconds
                )
            except (asyncio.TimeoutError, subprocess.TimeoutExpired) as te:
                elapsed_sec = round(time.time() - start_prep_time, 2)
                partial_stream = getattr(te, "stdout", "") or getattr(te, "output", "") or ""
                partial_err = getattr(te, "stderr", "") or ""
                docker_logs = ""
                try:
                    log_res = subprocess.run(
                        ["docker", "logs", "--tail", "150", container_name],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    docker_logs = log_res.stdout or log_res.stderr or ""
                except Exception:
                    pass

                # Immediately remove the timed-out container so it does not linger
                try:
                    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=10)
                except Exception:
                    pass

                combined_logs = "\n".join(filter(None, [str(partial_stream).strip(), str(partial_err).strip(), docker_logs.strip()]))
                sanitized_logs = _sanitize_error(combined_logs.strip())
                last_50 = extract_last_n_lines(sanitized_logs, 50)

                # Classify what pip was doing when the timeout occurred
                pip_activity = "installing dependencies"
                if any(k in sanitized_logs for k in ["Downloading", "Collecting", "fetch"]):
                    pip_activity = "downloading or collecting packages from package index"
                elif any(k in sanitized_logs for k in ["resolving dependencies", "Determining projects", "Resolution"]):
                    pip_activity = "resolving package dependency constraints"
                elif any(k in sanitized_logs for k in ["Building wheel", "Running setup.py", "gcc", "clang"]):
                    pip_activity = "compiling source wheels or running setup.py"
                elif any(k in sanitized_logs for k in ["Retrying", "Read timed out", "ConnectionError", "Max retries"]):
                    pip_activity = "waiting on unreachable package index or network connection"

                log_diag = f"\nInstallation progress before timeout (last 50 lines):\n{last_50}" if last_50 else ""
                err_msg = (
                    f"Dependency installation timed out after {self.dependency_timeout_seconds} seconds "
                    f"(elapsed: {elapsed_sec}s, stage: {pip_activity}).{log_diag}"
                )
                logger.error(f"[SANDBOX] {err_msg}")
                return PrepDependenciesResult(
                    base_image,
                    error=err_msg,
                    stdout=str(partial_stream),
                    stderr=str(partial_err) + ("\n" + docker_logs if docker_logs else ""),
                    exit_code=124,
                    last_50_lines=last_50,
                    timed_out=True,
                    manifest_name=manifest_basename,
                    install_cmd=sanitized_install_cmd,
                    manifest_sha256=manifest_sha256,
                    manifest_size=manifest_size
                )

            elapsed_sec = round(time.time() - start_prep_time, 2)
            if exit_code == 0:
                commit_cmd = ["docker", "commit", container_name, derived_tag]
                c_exit, c_out, c_err = await self._execute_docker_cmd(commit_cmd, timeout=60)
                if c_exit == 0:
                    logger.info(f"[SANDBOX] Successfully committed isolated dependency image '{derived_tag}' in {elapsed_sec}s.")
                    return PrepDependenciesResult(
                        derived_tag,
                        error=None,
                        stdout=stdout,
                        stderr=stderr,
                        exit_code=0,
                        last_50_lines=extract_last_n_lines(_sanitize_error(stdout or stderr), 50),
                        manifest_name=manifest_basename,
                        install_cmd=sanitized_install_cmd,
                        manifest_sha256=manifest_sha256,
                        manifest_size=manifest_size
                    )
                else:
                    c_combined = _sanitize_error(c_err.strip() or c_out.strip())
                    last_50 = extract_last_n_lines(c_combined, 50)
                    err_msg = f"Failed to commit dependency image: {last_50}"
                    logger.error(f"[SANDBOX] Failed to commit dependency image '{derived_tag}': {err_msg}")
                    return PrepDependenciesResult(
                        base_image,
                        error=err_msg,
                        stdout=c_out,
                        stderr=c_err,
                        exit_code=c_exit,
                        last_50_lines=last_50,
                        manifest_name=manifest_basename,
                        install_cmd=sanitized_install_cmd,
                        manifest_sha256=manifest_sha256,
                        manifest_size=manifest_size
                    )
            else:
                docker_logs = ""
                try:
                    log_res = subprocess.run(
                        ["docker", "logs", "--tail", "150", container_name],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    docker_logs = (log_res.stderr or log_res.stdout or "").strip()
                except Exception:
                    pass

                raw_combined = "\n".join(filter(None, [stdout.strip(), stderr.strip(), docker_logs.strip()]))
                sanitized_combined = _sanitize_error(raw_combined)
                last_50 = extract_last_n_lines(sanitized_combined, 50)

                failure_reason = "Dependency installation failed"
                if "ResolutionImpossible" in sanitized_combined or "conflicting dependencies" in sanitized_combined or "cannot install" in sanitized_combined or "incompatible" in sanitized_combined:
                    failure_reason = "Dependency conflict detected"
                elif "recursionerror" in sanitized_combined.lower() or "maximum recursion depth exceeded" in sanitized_combined.lower() or "circular" in sanitized_combined.lower():
                    failure_reason = "Recursive or circular dependency include detected in requirements file"
                elif "Could not find a version that satisfies" in sanitized_combined or "No matching distribution found" in sanitized_combined:
                    failure_reason = "Package not found or incompatible distribution"
                elif "Failed to build wheel" in sanitized_combined or "error: subprocess-exited-with-error" in sanitized_combined or "command 'gcc' failed" in sanitized_combined:
                    failure_reason = "Source build failure (missing binary wheel or build dependencies)"
                elif "ConnectionError" in sanitized_combined or "ReadTimeoutError" in sanitized_combined or "Max retries exceeded" in sanitized_combined or "HTTPError" in sanitized_combined or "timed out" in sanitized_combined.lower():
                    failure_reason = "Package index unreachable or network error"

                err_msg = (
                    f"Failed to resolve project dependencies in isolated build stage ({failure_reason}) [exit code {exit_code}, elapsed {elapsed_sec}s]:\n"
                    f"{last_50}"
                )
                logger.error(f"[SANDBOX] Failed to install dependencies in isolated container '{container_name}': {err_msg}")
                return PrepDependenciesResult(
                    base_image,
                    error=err_msg,
                    stdout=stdout,
                    stderr=stderr + ("\n" + docker_logs if docker_logs and docker_logs not in stderr else ""),
                    exit_code=exit_code,
                    last_50_lines=last_50,
                    timed_out=False,
                    manifest_name=manifest_basename,
                    install_cmd=sanitized_install_cmd,
                    manifest_sha256=manifest_sha256,
                    manifest_size=manifest_size
                )
        except Exception as be:
            err_msg = _sanitize_error(be)
            return PrepDependenciesResult(
                base_image,
                error=f"Error during isolated dependency build: {err_msg}",
                stderr=err_msg,
                exit_code=1,
                last_50_lines=err_msg,
                manifest_name=manifest_basename
            )
        finally:
            try:
                cleanup_cmd = ["docker", "rm", "-f", container_name]
                subprocess.run(cleanup_cmd, capture_output=True, timeout=10)
            except Exception:
                pass
            shutil.rmtree(build_ctx, ignore_errors=True)

    def detect_node_runtime_version(
        self,
        directory: str,
        workspace_dir: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Detects Node.js runtime version requirements from manifests and configuration.
        Inspects:
        1. .nvmrc in directory or workspace_dir
        2. .node-version in directory or workspace_dir
        3. package.json 'engines.node'
        4. package.json devDependencies/dependencies '@types/node'
        Returns (version_str, docker_image) e.g. ("20", "node:20-slim").
        Supports versions 18, 20, 22. Defaults to ("20", DEFAULT_NODE_IMAGE).
        """
        candidates_to_check = [directory]
        if workspace_dir and os.path.abspath(workspace_dir) != os.path.abspath(directory):
            candidates_to_check.append(workspace_dir)

        for d in candidates_to_check:
            if not os.path.isdir(d):
                continue

            # 1. .nvmrc
            nvmrc_path = os.path.join(d, ".nvmrc")
            if os.path.isfile(nvmrc_path):
                try:
                    with open(nvmrc_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_val = f.read().strip().lower()
                    m = re.search(r"(?:v)?(\d+)(?:\.\d+)*", raw_val)
                    if m:
                        ver = m.group(1)
                        return ver, f"node:{ver}-slim"
                    elif "iron" in raw_val:
                        return "20", "node:20-slim"
                    elif "hydrogen" in raw_val:
                        return "18", "node:18-slim"
                    elif "jod" in raw_val:
                        return "22", "node:22-slim"
                except Exception:
                    pass

            # 2. .node-version
            node_ver_path = os.path.join(d, ".node-version")
            if os.path.isfile(node_ver_path):
                try:
                    with open(node_ver_path, "r", encoding="utf-8", errors="replace") as f:
                        raw_val = f.read().strip().lower()
                    m = re.search(r"(?:v)?(\d+)(?:\.\d+)*", raw_val)
                    if m:
                        ver = m.group(1)
                        return ver, f"node:{ver}-slim"
                except Exception:
                    pass

            # 3. package.json
            pkg_path = os.path.join(d, "package.json")
            if os.path.isfile(pkg_path):
                try:
                    with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
                        pkg_data = json.load(f)

                    # engines.node
                    engines_node = str(pkg_data.get("engines", {}).get("node", "")).strip()
                    if engines_node:
                        m = re.search(r"(\d+)(?:\.\d+)*", engines_node)
                        if m:
                            ver = m.group(1)
                            return ver, f"node:{ver}-slim"

                    # @types/node in devDependencies or dependencies
                    dev_deps = pkg_data.get("devDependencies", {})
                    deps = pkg_data.get("dependencies", {})
                    node_types = str(dev_deps.get("@types/node") or deps.get("@types/node") or "")
                    if node_types:
                        m = re.search(r"(\d+)(?:\.\d+)*", node_types)
                        if m:
                            ver = m.group(1)
                            return ver, f"node:{ver}-slim"
                except Exception:
                    pass

        return "20", DEFAULT_NODE_IMAGE

    def _find_node_manifest(
        self,
        project_dir: str,
        workspace_dir: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Locates package.json and lockfile (package-lock.json, yarn.lock, pnpm-lock.yaml)
        in project_dir or workspace_dir.
        Calculates SHA-256 hashes and selects reproducible install command.
        """
        candidates = [project_dir]
        if workspace_dir and os.path.abspath(workspace_dir) != os.path.abspath(project_dir):
            candidates.append(workspace_dir)

        pkg_path = None
        target_dir = None
        for d in candidates:
            candidate_pkg = os.path.join(d, "package.json")
            if os.path.isfile(candidate_pkg) and os.access(candidate_pkg, os.R_OK):
                pkg_path = candidate_pkg
                target_dir = d
                break

        if not pkg_path:
            return None

        try:
            with open(pkg_path, "rb") as f:
                pkg_bytes = f.read()
            pkg_sha256 = hashlib.sha256(pkg_bytes).hexdigest()
        except Exception as e:
            logger.error(f"[SANDBOX] Failed to read package.json at {pkg_path}: {e}")
            return None

        lockfile_path = None
        lockfile_name = None
        lockfile_bytes = b""
        lockfile_sha256 = ""
        install_cmd = ""
        lockfile_type = "none"

        npm_lock = os.path.join(target_dir, "package-lock.json")
        yarn_lock = os.path.join(target_dir, "yarn.lock")
        pnpm_lock = os.path.join(target_dir, "pnpm-lock.yaml")

        if os.path.isfile(npm_lock) and os.access(npm_lock, os.R_OK):
            lockfile_path = npm_lock
            lockfile_name = "package-lock.json"
            lockfile_type = "npm"
            install_cmd = "(npm ci --ignore-scripts --no-audit --no-fund || npm install --ignore-scripts --no-audit --no-fund)"
        elif os.path.isfile(yarn_lock) and os.access(yarn_lock, os.R_OK):
            lockfile_path = yarn_lock
            lockfile_name = "yarn.lock"
            lockfile_type = "yarn"
            install_cmd = "(corepack enable && yarn install --frozen-lockfile --ignore-scripts)"
        elif os.path.isfile(pnpm_lock) and os.access(pnpm_lock, os.R_OK):
            lockfile_path = pnpm_lock
            lockfile_name = "pnpm-lock.yaml"
            lockfile_type = "pnpm"
            install_cmd = "(corepack enable && pnpm install --frozen-lockfile --ignore-scripts)"
        else:
            lockfile_type = "none"
            install_cmd = "npm install --ignore-scripts --no-audit --no-fund"

        if lockfile_path:
            try:
                with open(lockfile_path, "rb") as f:
                    lockfile_bytes = f.read()
                lockfile_sha256 = hashlib.sha256(lockfile_bytes).hexdigest()
            except Exception as e:
                logger.warning(f"[SANDBOX] Could not read lockfile {lockfile_path}: {e}")

        return {
            "target_dir": target_dir,
            "pkg_path": pkg_path,
            "pkg_name": "package.json",
            "pkg_bytes": pkg_bytes,
            "pkg_sha256": pkg_sha256,
            "lockfile_path": lockfile_path,
            "lockfile_name": lockfile_name,
            "lockfile_bytes": lockfile_bytes,
            "lockfile_sha256": lockfile_sha256,
            "lockfile_type": lockfile_type,
            "install_cmd": install_cmd
        }

    async def prepare_node_dependencies(
        self,
        workspace_dir: str,
        rel_workdir: Optional[str] = None,
        base_image: str = DEFAULT_NODE_IMAGE
    ) -> PrepDependenciesResult:
        """
        Phase A: Prepares Node.js project dependencies in an isolated container build stage
        with network access enabled, reproducible lockfile-based installation, no secrets mounted,
        and strict caching keyed by runtime, manifest, and lockfile hashes.
        Returns PrepDependenciesResult(image, error, stdout, stderr, exit_code, last_50_lines, timed_out, manifest_name, install_cmd).
        """
        host_project_dir = os.path.join(workspace_dir, rel_workdir) if rel_workdir else workspace_dir
        manifest = self._find_node_manifest(host_project_dir, workspace_dir)

        if not manifest:
            # No package.json found; check if base image is ready
            base_ok, base_err = await self.ensure_base_image_available(base_image)
            if not base_ok:
                msg = (
                    f"Container image '{base_image}' is not cached locally and cannot be pulled under network isolation (--network none). "
                    f"{base_err or ''}"
                )
                return PrepDependenciesResult(base_image, error=msg, stderr=base_err or "", exit_code=127)
            return PrepDependenciesResult(base_image, None)

        # Calculate cache key
        cache_key_raw = (
            f"node_base={base_image}::pkg={manifest['pkg_sha256']}::"
            f"lock={manifest['lockfile_sha256']}::cmd={manifest['install_cmd']}"
        )
        cache_hash = hashlib.sha256(cache_key_raw.encode("utf-8")).hexdigest()[:16]
        derived_tag = f"devrescue-node-deps:{cache_hash}"

        start_prep_time = time.time()

        # Cache HIT check
        if self.check_image_available(derived_tag):
            elapsed_sec = round(time.time() - start_prep_time, 2)
            logger.info(f"[SANDBOX] Cache HIT: Reusing existing cached Node dependency image '{derived_tag}' (key={cache_hash}). Elapsed: {elapsed_sec}s.")
            print(f"[SANDBOX] Cache HIT: Reusing existing cached Node dependency image '{derived_tag}' (key={cache_hash}). Elapsed: {elapsed_sec}s.", flush=True)
            return PrepDependenciesResult(
                derived_tag,
                None,
                manifest_name=manifest["pkg_name"],
                install_cmd=manifest["install_cmd"],
                manifest_sha256=manifest["pkg_sha256"],
                manifest_size=len(manifest["pkg_bytes"])
            )

        logger.info(f"[SANDBOX] Cache MISS: Preparing Node.js dependencies for '{derived_tag}' (key={cache_hash})...")
        print(f"[SANDBOX] Cache MISS: Preparing Node.js dependencies for '{derived_tag}' (key={cache_hash})...", flush=True)

        # Ensure base image is available before running container install
        base_ok, base_err = await self.ensure_base_image_available(base_image)
        if not base_ok:
            logger.error(f"[SANDBOX] Cannot prepare Node dependencies: Base image '{base_image}' unavailable: {base_err}")
            return PrepDependenciesResult(
                base_image,
                error=(
                    f"Container image '{base_image}' is not cached locally and cannot be pulled under network isolation (--network none). "
                    f"{base_err or ''}"
                ),
                stderr=base_err or "",
                exit_code=127,
                manifest_name=manifest["pkg_name"],
                install_cmd=manifest["install_cmd"]
            )

        # Stage ONLY package.json and lockfile into isolated staging directory
        build_ctx = os.path.abspath(tempfile.mkdtemp(prefix="devrescue_node_deps_"))
        try:
            staged_pkg_path = os.path.join(build_ctx, "package.json")
            with open(staged_pkg_path, "wb") as f:
                f.write(manifest["pkg_bytes"])

            copy_lock_line = ""
            if manifest["lockfile_name"] and manifest["lockfile_bytes"]:
                staged_lock_path = os.path.join(build_ctx, manifest["lockfile_name"])
                with open(staged_lock_path, "wb") as f:
                    f.write(manifest["lockfile_bytes"])
                if manifest["lockfile_name"] != "package-lock.json":
                    copy_lock_line = f"COPY {manifest['lockfile_name']} ./\n"

            df_path = os.path.join(build_ctx, "Dockerfile")
            dockerfile_content = (
                f"FROM {base_image}\n"
                f"WORKDIR /node_deps\n"
                f"COPY package*.json ./\n"
                f"{copy_lock_line}"
                f"RUN {manifest['install_cmd']}\n"
                f"RUN ln -s /node_deps/node_modules /node_modules 2>/dev/null || true\n"
                f"ENV NODE_PATH=/node_deps/node_modules:/node_modules\n"
                f"ENV PATH=/node_deps/node_modules/.bin:/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
            )
            with open(df_path, "w", encoding="utf-8") as df:
                df.write(dockerfile_content)

            build_cmd = ["docker", "build", "-t", derived_tag, build_ctx]
            try:
                exit_code, stdout, stderr = await self._execute_docker_cmd(
                    build_cmd,
                    timeout=self.dependency_timeout_seconds
                )
            except (asyncio.TimeoutError, subprocess.TimeoutExpired) as te:
                elapsed_sec = round(time.time() - start_prep_time, 2)
                err_msg = f"Node dependency installation timed out after {self.dependency_timeout_seconds}s (elapsed: {elapsed_sec}s)."
                return PrepDependenciesResult(
                    base_image,
                    error=err_msg,
                    stderr=err_msg,
                    exit_code=124,
                    timed_out=True,
                    manifest_name=manifest["pkg_name"],
                    install_cmd=manifest["install_cmd"]
                )

            elapsed_sec = round(time.time() - start_prep_time, 2)
            if exit_code == 0:
                logger.info(f"[SANDBOX] Successfully built Node dependency image '{derived_tag}' in {elapsed_sec}s.")
                # Verify test runner or dependencies in built image
                v_cmd = ["docker", "run", "--rm", derived_tag, "sh", "-c", "which jest || which vitest || which mocha || npm --version"]
                await self._execute_docker_cmd(v_cmd, timeout=15)

                return PrepDependenciesResult(
                    derived_tag,
                    error=None,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=0,
                    last_50_lines=extract_last_n_lines(_sanitize_error(stdout or stderr), 50),
                    manifest_name=manifest["pkg_name"],
                    install_cmd=manifest["install_cmd"],
                    manifest_sha256=manifest["pkg_sha256"],
                    manifest_size=len(manifest["pkg_bytes"])
                )
            else:
                combined_err = _sanitize_error(stderr.strip() or stdout.strip())
                last_50 = extract_last_n_lines(combined_err, 50)
                err_msg = f"Node dependency installation failed (exit code {exit_code}):\n{last_50}"
                return PrepDependenciesResult(
                    base_image,
                    error=err_msg,
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    last_50_lines=last_50,
                    manifest_name=manifest["pkg_name"],
                    install_cmd=manifest["install_cmd"]
                )
        except Exception as e:
            err_msg = _sanitize_error(e)
            return PrepDependenciesResult(
                base_image,
                error=f"Error during isolated Node dependency preparation: {err_msg}",
                stderr=err_msg,
                exit_code=1,
                manifest_name=manifest["pkg_name"],
                install_cmd=manifest["install_cmd"]
            )
        finally:
            shutil.rmtree(build_ctx, ignore_errors=True)

    def _discover_project_python_packages(
        self,
        project_dir: str,
        workspace_dir: str
    ) -> List[str]:
        """
        Discovers top-level Python packages in project_dir, src/, or workspace_dir
        to verify importability during sandbox pre-flight checks.
        """
        ignored_dir_names = {
            "tests", "test", "testing", "unit_tests", "tests_unit",
            "venv", ".venv", "env", ".env", ".git", "__pycache__",
            "site-packages", "dist", "build", "node_modules", ".pytest_cache"
        }
        packages: List[str] = []

        dirs_to_inspect = [project_dir]
        src_dir = os.path.join(project_dir, "src")
        if os.path.isdir(src_dir):
            dirs_to_inspect.append(src_dir)
        if workspace_dir != project_dir:
            dirs_to_inspect.append(workspace_dir)
            ws_src = os.path.join(workspace_dir, "src")
            if os.path.isdir(ws_src):
                dirs_to_inspect.append(ws_src)

        for d in dirs_to_inspect:
            if not os.path.isdir(d):
                continue
            try:
                for entry in sorted(os.listdir(d)):
                    if entry.lower() in ignored_dir_names or entry.startswith("."):
                        continue
                    full_p = os.path.join(d, entry)
                    if os.path.isdir(full_p):
                        if os.path.isfile(os.path.join(full_p, "__init__.py")):
                            if entry not in packages:
                                packages.append(entry)
                    elif entry.endswith(".py") and entry not in ("setup.py", "conftest.py"):
                        base_mod = entry[:-3]
                        if base_mod not in packages and base_mod not in ignored_dir_names:
                            packages.append(base_mod)
            except Exception:
                pass

        # If "app" is in packages, ensure it is first
        if "app" in packages:
            packages.remove("app")
            packages.insert(0, "app")

        return packages

    def _check_python_dir(self, directory: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Inspects directory for Python test configuration.
        Returns (is_configured, command, framework).
        """
        if not os.path.isdir(directory):
            return False, None, None

        # 1. pytest.ini
        if os.path.isfile(os.path.join(directory, "pytest.ini")):
            return True, "pytest", "pytest"

        # 2. pyproject.toml
        pyproject_path = os.path.join(directory, "pyproject.toml")
        if os.path.isfile(pyproject_path):
            try:
                with open(pyproject_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
                if "tool.pytest" in content or "pytest" in content:
                    return True, "pytest", "pytest"
            except Exception:
                pass

        # 3. tox.ini
        tox_path = os.path.join(directory, "tox.ini")
        if os.path.isfile(tox_path):
            try:
                with open(tox_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
                if "pytest" in content or "testenv" in content:
                    return True, "pytest", "pytest"
            except Exception:
                pass

        # 4. setup.cfg
        setup_cfg_path = os.path.join(directory, "setup.cfg")
        if os.path.isfile(setup_cfg_path):
            try:
                with open(setup_cfg_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
                if "tool:pytest" in content or "[pytest]" in content or "pytest" in content:
                    return True, "pytest", "pytest"
            except Exception:
                pass

        # 5. requirements*.txt with pytest
        try:
            for item in os.listdir(directory):
                if (item.startswith("requirements") and item.endswith(".txt")) or item in ("test-requirements.txt", "requirements-dev.txt"):
                    req_path = os.path.join(directory, item)
                    if os.path.isfile(req_path):
                        with open(req_path, "r", encoding="utf-8", errors="replace") as f:
                            if "pytest" in f.read().lower():
                                return True, "pytest", "pytest"
        except Exception:
            pass

        # 6. Test directories: tests, test, testing, unit_tests, tests_unit
        test_dir_names = ["tests", "test", "testing", "unit_tests", "tests_unit"]
        for tname in test_dir_names:
            tdir = os.path.join(directory, tname)
            if self._has_python_test_files(tdir):
                return True, "pytest", "pytest"
            if os.path.isdir(tdir):
                try:
                    for sub in os.listdir(tdir):
                        sub_path = os.path.join(tdir, sub)
                        if self._has_python_test_files(sub_path):
                            return True, "pytest", "pytest"
                except Exception:
                    pass

        # 7. Test files directly in directory
        if self._has_python_test_files(directory):
            return True, "pytest", "pytest"

        return False, None, None

    def _check_node_dir(self, directory: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Inspects directory for Node/JS/TS test configuration.
        Returns (is_configured, command, framework).
        """
        pkg_path = os.path.join(directory, "package.json")
        if not os.path.isfile(pkg_path):
            return False, None, None

        try:
            with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
                pkg_data = json.load(f)
            scripts = pkg_data.get("scripts", {})
            test_script = scripts.get("test", "").strip()

            # Reject empty or default placeholder test scripts
            if not test_script:
                return False, None, None

            test_lower = test_script.lower()
            if "no test specified" in test_lower or ("exit 1" in test_lower and "echo" in test_lower):
                return False, None, None

            # Detect specific framework if mentioned
            framework = "npm"
            dev_deps = pkg_data.get("devDependencies", {})
            deps = pkg_data.get("dependencies", {})
            if "vitest" in test_lower or "vitest" in dev_deps or "vitest" in deps:
                framework = "vitest"
            elif "jest" in test_lower or "jest" in dev_deps or "jest" in deps:
                framework = "jest"
            elif "mocha" in test_lower or "mocha" in dev_deps:
                framework = "mocha"

            return True, "npm test", framework
        except Exception as e:
            logger.warning(f"[SANDBOX] Failed to inspect package.json at {pkg_path}: {e}")
            return False, None, None

    def detect_test_framework(
        self,
        workspace_dir: str,
        changed_files: List[str]
    ) -> TestFrameworkResult:
        """
        Inspects repository files to detect the appropriate test framework.
        Supports root-level projects, nested directories, and monorepos.
        Returns TestFrameworkResult(command, container_workdir, docker_image, framework).
        """
        if not os.path.isdir(workspace_dir):
            return TestFrameworkResult(None, None, None, None)

        candidates = []

        # Check root first
        is_py, py_cmd, py_fw = self._check_python_dir(workspace_dir)
        if is_py:
            candidates.append({"rel_dir": "", "command": py_cmd, "framework": py_fw, "image": DEFAULT_PYTHON_IMAGE})

        is_node, node_cmd, node_fw = self._check_node_dir(workspace_dir)
        if is_node:
            _, node_img = self.detect_node_runtime_version(workspace_dir)
            candidates.append({"rel_dir": "", "command": node_cmd, "framework": node_fw, "image": node_img})

        # Recursively search subdirectories (up to max depth 3)
        for root, dirs, _ in os.walk(workspace_dir):
            dirs[:] = [d for d in dirs if not self._is_ignored_dir(d)]

            rel_root = os.path.relpath(root, workspace_dir).replace("\\", "/")
            if rel_root == ".":
                continue

            depth = len(rel_root.split("/"))
            if depth > 3:
                dirs[:] = []
                continue

            is_py, py_cmd, py_fw = self._check_python_dir(root)
            if is_py:
                candidates.append({"rel_dir": rel_root, "command": py_cmd, "framework": py_fw, "image": DEFAULT_PYTHON_IMAGE})

            is_node, node_cmd, node_fw = self._check_node_dir(root)
            if is_node:
                _, node_img = self.detect_node_runtime_version(root, workspace_dir)
                candidates.append({"rel_dir": rel_root, "command": node_cmd, "framework": node_fw, "image": node_img})

        if not candidates:
            return TestFrameworkResult(None, None, None, None)

        # Score candidates against changed_files
        normalized_changed = [cf.replace("\\", "/").lstrip("/") for cf in changed_files]

        best_candidate = None
        best_score = -1

        for cand in candidates:
            rel = cand["rel_dir"]
            score = 0
            if rel:
                for cf in normalized_changed:
                    if cf == rel or cf.startswith(rel + "/"):
                        depth = len(rel.split("/"))
                        score += 10 * depth
            else:
                score = 1 if not best_candidate else 0

            cand["score"] = score
            if score > best_score:
                best_score = score
                best_candidate = cand

        if best_score <= 0 or not best_candidate:
            root_cands = [c for c in candidates if c["rel_dir"] == ""]
            if root_cands:
                best_candidate = root_cands[0]
            else:
                candidates.sort(key=lambda c: len(c["rel_dir"].split("/")))
                best_candidate = candidates[0]

        rel_dir = best_candidate["rel_dir"]
        # Use posixpath.join to guarantee clean POSIX paths inside the container
        # (avoids double-slashes like //workspace/backend on Windows where rel_dir
        clean_rel = rel_dir.replace("\\", "/").strip("/")
        if clean_rel:
            container_workdir = posixpath.join("/workspace", clean_rel)
        else:
            container_workdir = "/workspace"
        return TestFrameworkResult(
            command=best_candidate["command"],
            workdir=container_workdir,
            image=best_candidate["image"],
            framework=best_candidate["framework"]
        )

    def apply_patch_to_workspace(
        self,
        workspace_dir: str,
        patch: str,
        expected_contents: Optional[Dict[str, str]] = None,
        expected_shas: Optional[Dict[str, str]] = None,
        expected_source_hashes: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """
        Applies validated unified diff patch to repository files in workspace_dir.
        Enforces two-phase atomic execution:
        1. In-memory validation, source hash check, and hunk application across all files.
        2. Atomic write to disk only if ALL hunks across ALL files apply cleanly.
        Preserves original workspace completely unchanged if any hunk fails.
        Preserves UTF-8 encoding and original line endings (CRLF/LF).
        """
        # Validate patch syntax and limits before touching workspace
        diff_validator.validate_syntax_and_limits(patch)

        per_file_diffs = diff_validator.split_per_file_diffs(patch)
        if not per_file_diffs:
            raise DiffApplicationError("Patch contains no file diff blocks.")

        staged_writes: Dict[str, str] = {}
        modified_files: List[str] = []

        # Phase 1: In-memory validation and hunk application
        for rel_path, file_diff in per_file_diffs.items():
            if rel_path == "/dev/null":
                continue

            target_disk_path = os.path.join(workspace_dir, rel_path.replace("/", os.sep))

            # If path does not exist directly, attempt search by normalized relative path
            if not os.path.isfile(target_disk_path):
                found = False
                for root, _, files in os.walk(workspace_dir):
                    for file in files:
                        full = os.path.join(root, file)
                        r = os.path.relpath(full, workspace_dir).replace("\\", "/")
                        if r == rel_path or r.endswith("/" + rel_path.lstrip("/")) or rel_path.endswith("/" + r.lstrip("/")):
                            target_disk_path = full
                            found = True
                            break
                    if found:
                        break

                # For new files or subproject layouts, map relative paths to existing subproject folders
                if not found:
                    for prefix in ("backend", "src", "client", "server"):
                        candidate = os.path.join(workspace_dir, prefix, rel_path.replace("/", os.sep))
                        prefix_dir = os.path.join(workspace_dir, prefix)
                        first_part = rel_path.split("/")[0]
                        if os.path.isdir(prefix_dir) and not os.path.isdir(os.path.join(workspace_dir, first_part)):
                            if os.path.isdir(os.path.join(prefix_dir, first_part)) or os.path.isfile(os.path.join(prefix_dir, rel_path.replace("/", os.sep))):
                                target_disk_path = candidate
                                break
                            elif "--- /dev/null" in file_diff and (prefix == "backend" and (first_part in ("app", "tests"))):
                                target_disk_path = candidate
                                break

            # If creating a new file
            if "--- /dev/null" in file_diff or not os.path.isfile(target_disk_path):
                if "--- /dev/null" in file_diff:
                    res = diff_validator._apply_hunks("", file_diff, file_path=rel_path)
                    if not res.success:
                        raise DiffApplicationError(
                            f"Failed to create new file '{rel_path}': {res.error}",
                            file=rel_path,
                            hunk=res.failed_hunk,
                            details=res.details
                        )
                    staged_writes[target_disk_path] = res.new_content
                    modified_files.append(rel_path)
                    continue

                raise DiffApplicationError(
                    f"Target file for patch '{rel_path}' not found in workspace.",
                    file=rel_path
                )

            # Read existing file content
            with open(target_disk_path, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()

            actual_hash = hashlib.sha256(original_content.encode("utf-8")).hexdigest()

            # Source hash verification against expected_source_hashes
            if expected_source_hashes and rel_path in expected_source_hashes:
                exp_h = expected_source_hashes[rel_path]
                if actual_hash != exp_h:
                    norm_content = original_content.replace("\r\n", "\n").replace("\r", "\n")
                    norm_actual_hash = hashlib.sha256(norm_content.encode("utf-8")).hexdigest()
                    expected_norm_hash = expected_source_hashes.get(f"{rel_path}__norm")
                    if not (expected_norm_hash and norm_actual_hash == expected_norm_hash):
                        raise DiffApplicationError(
                            f"Target file '{rel_path}' in workspace has diverged from patch source content (stale SHA / hash mismatch).",
                            file=rel_path,
                            details={"stale_source": True}
                        )

            # Source content verification against expected contents
            if expected_contents and rel_path in expected_contents:
                expected = expected_contents[rel_path]
                exp_h = hashlib.sha256(expected.encode("utf-8")).hexdigest()
                if actual_hash != exp_h and original_content.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
                    raise DiffApplicationError(
                        f"Target file '{rel_path}' in workspace has diverged from patch source content.",
                        file=rel_path,
                        details={"stale_source": True}
                    )

            # Test clean application in memory
            res = diff_validator._apply_hunks(
                original_content,
                file_diff,
                file_path=rel_path
            )
            if not res.success:
                # Abort immediately without touching the disk
                raise DiffApplicationError(
                    f"Patch does not apply cleanly to '{rel_path}': {res.error}",
                    file=rel_path,
                    hunk=res.failed_hunk,
                    details=res.details
                )

            staged_writes[target_disk_path] = res.new_content
            modified_files.append(rel_path)

        # Phase 2: Atomic write to disk only after all files are verified
        for disk_path, content in staged_writes.items():
            os.makedirs(os.path.dirname(disk_path), exist_ok=True)
            with open(disk_path, "w", encoding="utf-8", newline="") as f:
                f.write(content)

        # Phase 3: Assert all staged files exist on disk
        for disk_path in staged_writes.keys():
            if not os.path.isfile(disk_path):
                raise DiffApplicationError(
                    f"Disk write verification failed: Staged file '{disk_path}' was not written successfully."
                )

        return modified_files

    def check_availability(self) -> bool:
        """Legacy helper for demo mode."""
        is_avail, _ = self.check_docker_available()
        return is_avail

    async def run_security_scan(self, patch_diff: str) -> Dict[str, Any]:
        """
        Runs SAST and secrets scanner on synthesized patch diff.
        Delegates to security_service.scan_patch.
        Never fabricates 'no secrets detected' when scanner has not executed.
        """
        from app.services.security_service import security_service
        return security_service.scan_patch(patch_diff)

    async def execute_tests(
        self,
        repo: str,
        patch_diff: Optional[str] = None,
        *args,
        owner: Optional[str] = None,
        branch: str = "main",
        issue_number: int = 1,
        patch: Optional[str] = None,
        access_token: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Backward-compatible dispatcher:
        If called from legacy/demo investigation_service (repo, patch_code), returns legacy dict.
        If called with owner & repo & patch, executes the full real Docker sandbox.
        """
        if owner is None and patch is None:
            # Legacy demo invocation from investigation_service
            return {
                "sandbox_status": "NOT_IMPLEMENTED",
                "message": "Docker sandbox execution environment not configured. Automated test execution disabled.",
                "tests_passed": 0,
                "tests_failed": 0,
                "test_count": 0,
                "output": "Testing: NOT IMPLEMENTED"
            }

        target_owner = owner or (repo.split("/")[0] if "/" in repo else "")
        target_repo = repo.split("/")[1] if "/" in repo else repo
        target_patch = patch or patch_diff or ""

        return await self.execute_sandbox_test(
            owner=target_owner,
            repo=target_repo,
            branch=branch,
            issue_number=issue_number,
            patch=target_patch,
            access_token=access_token
        )

    async def execute_sandbox_test(
        self,
        owner: str,
        repo: str,
        branch: str,
        issue_number: int,
        patch: str,
        access_token: Optional[str] = None
    ) -> SandboxTestResponse:
        """
        Executes end-to-end sandbox testing pipeline:
        1. Validates diff syntax and limits.
        2. Verifies Docker availability.
        3. Creates isolated workspace and downloads repository archive.
        4. Applies validated patch.
        5. Detects test framework.
        6. Runs Docker container with security limits (--network none, memory/cpu limits).
        7. Captures test execution output and parses test metrics.
        8. Completely destroys temporary workspace and container.
        """
        start_time = time.time()
        logger.info(f"[SANDBOX] Starting sandbox test execution for {owner}/{repo}#{issue_number}...")
        print(f"[SANDBOX] Starting sandbox test execution for {owner}/{repo}#{issue_number}...", flush=True)

        # 1. Diff validation pre-check
        try:
            files_changed, _, _ = diff_validator.validate_syntax_and_limits(patch)
        except (DiffValidationError, ValueError) as dve:
            safe_err = _sanitize_error(dve)
            return SandboxTestResponse(
                success=False,
                status="PATCH_FAILED",
                message=f"Diff validation rejected patch: {safe_err}",
                exit_code=1,
                stderr=safe_err
            )
        except Exception as e:
            safe_err = _sanitize_error(e)
            logger.error(f"[SANDBOX] Unexpected error validating diff: {safe_err}", exc_info=True)
            return SandboxTestResponse(
                success=False,
                status="PATCH_FAILED",
                message=f"Diff validation encountered error: {safe_err}",
                exit_code=1,
                stderr=safe_err
            )

        if not files_changed:
            return SandboxTestResponse(
                success=False,
                status="PATCH_FAILED",
                message="Patch does not modify any files.",
                exit_code=1,
                stderr="Patch has empty file list."
            )

        # 2. Docker availability check
        docker_available, docker_reason = self.check_docker_available()
        if not docker_available:
            logger.warning(f"[SANDBOX] Docker is unavailable: {docker_reason}")
            print(f"[SANDBOX] Docker is unavailable: {docker_reason}", flush=True)
            return SandboxTestResponse(
                success=False,
                status="DOCKER_UNAVAILABLE",
                message=f"Docker sandbox environment not available: {docker_reason}",
                exit_code=None,
                test_command=None,
                docker_image=None,
                stdout="",
                stderr=docker_reason or "Docker daemon not running."
            )

        workspace_dir = tempfile.mkdtemp(prefix="devrescue_sandbox_")

        try:
            # 3. Populate workspace from GitHub
            commit_sha = ""
            try:
                commit_sha = await github_service.get_branch_sha(
                    access_token=access_token or "",
                    owner=owner,
                    repo=repo,
                    branch=branch
                )
            except Exception as se:
                logger.debug(f"[SANDBOX] Non-fatal branch SHA lookup exception: {se}")

            logger.info(
                f"[SANDBOX] Target repository checkout: {owner}/{repo}@{branch} "
                f"(Target Commit SHA: {commit_sha or 'unknown'})"
            )
            print(
                f"[SANDBOX] Target repository checkout: {owner}/{repo}@{branch} "
                f"(Target Commit SHA: {commit_sha or 'unknown'})",
                flush=True
            )
            logger.info(f"[SANDBOX] Archive destination directory: {workspace_dir}")
            print(f"[SANDBOX] Archive destination directory: {workspace_dir}", flush=True)

            logger.info(f"[SANDBOX] Downloading repository archive {owner}/{repo}@{branch} into workspace...")
            print(f"[SANDBOX] Downloading repository archive {owner}/{repo}@{branch} into workspace...", flush=True)
            try:
                await github_service.download_and_extract_archive(
                    access_token=access_token,
                    owner=owner,
                    repo=repo,
                    ref=branch,
                    destination_dir=workspace_dir
                )
            except (GitHubAuthError, GitHubPermissionError) as ge:
                safe_ge = _sanitize_error(ge)
                logger.error(f"[SANDBOX] GitHub auth error downloading archive: {safe_ge}")
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"GitHub authentication error downloading repository: {safe_ge}",
                    exit_code=1,
                    stderr=safe_ge
                )
            except GitHubRateLimitError as ge:
                safe_ge = _sanitize_error(ge)
                logger.error(f"[SANDBOX] GitHub rate limit downloading archive: {safe_ge}")
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"GitHub rate limit exceeded downloading repository: {safe_ge}",
                    exit_code=1,
                    stderr=safe_ge
                )
            except GitHubError as ge:
                safe_ge = _sanitize_error(ge)
                logger.error(f"[SANDBOX] GitHub error downloading archive: {safe_ge}")
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"Failed to obtain repository source: {safe_ge}",
                    exit_code=1,
                    stderr=safe_ge
                )
            except Exception as de:
                safe_de = _sanitize_error(de)
                logger.error(f"[SANDBOX] Archive extraction error: {safe_de}", exc_info=True)
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"Failed to extract repository archive: {safe_de}",
                    exit_code=1,
                    stderr=safe_de
                )

            # Flatten nested root folder if zipball extracted into a single wrapper folder
            flatten_nested_root_folder(workspace_dir)

            # 4. Apply validated patch
            per_file_blocks = diff_validator.split_per_file_diffs(patch)
            patch_file_count = len([f for f in per_file_blocks if f != "/dev/null"])
            logger.info(f"[SANDBOX] Applying validated patch ({patch_file_count} file(s) in diff) to workspace files...")
            print(f"[SANDBOX] Applying validated patch ({patch_file_count} file(s) in diff) to workspace files...", flush=True)
            try:
                applied_files = self.apply_patch_to_workspace(workspace_dir, patch)
                logger.info(f"[SANDBOX] Patch application result: {len(applied_files)} files modified/created in workspace: {applied_files}")
                print(f"[SANDBOX] Patch application result: {len(applied_files)} files modified/created in workspace: {applied_files}", flush=True)
                logger.info(f"[SANDBOX] Final workspace path: {workspace_dir}")
                print(f"[SANDBOX] Final workspace path: {workspace_dir}", flush=True)
            except (DiffApplicationError, DiffValidationError, ValueError, OSError) as dae:
                safe_dae = _sanitize_error(dae)
                logger.warning(f"[SANDBOX] Patch application error: {safe_dae}")
                return SandboxTestResponse(
                    success=False,
                    status="PATCH_FAILED",
                    message=f"Patch failed to apply cleanly to repository files: {safe_dae}",
                    exit_code=1,
                    stderr=safe_dae
                )
            except Exception as pe:
                safe_pe = _sanitize_error(pe)
                logger.error(f"[SANDBOX] Unexpected error applying patch: {safe_pe}", exc_info=True)
                return SandboxTestResponse(
                    success=False,
                    status="PATCH_FAILED",
                    message=f"Patch application failed: {safe_pe}",
                    exit_code=1,
                    stderr=safe_pe
                )

            # Pre-flight check for 2D2Mesh workspace integrity
            if "2d2mesh" in repo.lower():
                from app.services.recovered_2d2mesh_models import verify_2d2mesh_models_present
                is_complete, missing_mods = verify_2d2mesh_models_present(workspace_dir)
                if not is_complete:
                    duration = round(time.time() - start_time, 2)
                    logger.error(f"[SANDBOX] Mandatory models missing from workspace: {missing_mods}")
                    print(f"[SANDBOX] Mandatory models missing from workspace: {missing_mods}", flush=True)
                    return SandboxTestResponse(
                        success=False,
                        status="ENVIRONMENT_ERROR",
                        exit_code=4,
                        message=f"Preflight validation failed: Missing required modules: {', '.join(missing_mods)}",
                        working_directory="/workspace/backend",
                        duration_seconds=duration,
                        stderr=(
                            f"PREFLIGHT_ERROR: Target modules missing from workspace:\n"
                            + "\n".join(f"  - {m}" for m in missing_mods)
                        )
                    )

            # 5. Detect test command
            try:
                detect_res = self.detect_test_framework(workspace_dir, files_changed)
                if isinstance(detect_res, TestFrameworkResult):
                    test_command = detect_res.command
                    container_workdir = detect_res.workdir
                    docker_image = detect_res.image
                    framework = detect_res.framework
                elif isinstance(detect_res, (tuple, list)) and len(detect_res) >= 3:
                    test_command = detect_res[0]
                    container_workdir = detect_res[1]
                    docker_image = detect_res[2]
                    framework = getattr(detect_res, "framework", None)
                    if not framework and test_command:
                        framework = (
                            "pytest" if "pytest" in test_command else
                            "unittest" if "unittest" in test_command else
                            "npm" if "npm" in test_command else
                            test_command
                        )
                else:
                    test_command, container_workdir, docker_image, framework = None, None, None, None
            except Exception as fe:
                safe_fe = _sanitize_error(fe)
                logger.error(f"[SANDBOX] Test framework detection failed: {safe_fe}", exc_info=True)
                test_command, container_workdir, docker_image, framework = None, None, None, None

            logger.info(f"[SANDBOX] Detected test framework: framework={framework}, command={test_command}, image={docker_image}, workdir={container_workdir}")
            print(f"[SANDBOX] Detected test framework: framework={framework}, command={test_command}, image={docker_image}, workdir={container_workdir}", flush=True)

            # Verify host workspace directory exists
            host_workspace_dir = os.path.abspath(workspace_dir)
            if not os.path.isdir(host_workspace_dir):
                duration = round(time.time() - start_time, 2)
                logger.error(f"[SANDBOX] Host workspace path missing: {host_workspace_dir}")
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"Host workspace directory does not exist: {host_workspace_dir}",
                    exit_code=1,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image or DEFAULT_PYTHON_IMAGE,
                    working_directory=container_workdir,
                    duration_seconds=duration,
                    stdout="",
                    stderr=f"Host workspace path missing: {host_workspace_dir}"
                )

            # Verify that the selected project directory exists inside the container and host
            container_workdir = normalize_container_path(container_workdir)
            clean_rel = container_workdir[len("/workspace"):].lstrip("/")
            rel_workdir = clean_rel
            host_project_dir = os.path.join(host_workspace_dir, *clean_rel.split("/")) if clean_rel else host_workspace_dir

            # Ensure project directory exists on host so it exists inside the container bind mount
            os.makedirs(host_project_dir, exist_ok=True)

            if not test_command:
                duration = round(time.time() - start_time, 2)
                return SandboxTestResponse(
                    success=False,
                    status="TESTS_NOT_CONFIGURED",
                    message="No test suite configuration found in the repository.",
                    exit_code=None,
                    test_command=None,
                    framework=None,
                    docker_image=docker_image or DEFAULT_PYTHON_IMAGE,
                    working_directory=None,
                    duration_seconds=duration,
                    stdout="",
                    stderr="Repository does not define a recognizable test configuration in package.json or pytest."
                )

            # 6. Phase A: Dependency and Image Preparation (network access permitted)
            docker_image = docker_image or DEFAULT_PYTHON_IMAGE
            is_node_project = (
                framework in ("jest", "vitest", "mocha", "npm")
                or "node" in (docker_image or "").lower()
                or os.path.isfile(os.path.join(host_project_dir, "package.json"))
            )

            if is_node_project:
                prep_result = await self.prepare_node_dependencies(
                    host_workspace_dir,
                    rel_workdir,
                    base_image=docker_image
                )
                prep_image, prep_err = prep_result[0], prep_result[1]
                if prep_err:
                    duration = round(time.time() - start_time, 2)
                    logger.warning(f"[SANDBOX] Node.js dependencies could not be prepared: {prep_err}")
                    prep_stdout = getattr(prep_result, "stdout", "") or ""
                    prep_stderr = getattr(prep_result, "stderr", "") or prep_err
                    prep_exit_code = getattr(prep_result, "exit_code", 127) or 127
                    return SandboxTestResponse(
                        success=False,
                        status="DEPENDENCIES_UNAVAILABLE",
                        exit_code=prep_exit_code,
                        test_command=test_command,
                        framework=framework,
                        docker_image=docker_image,
                        working_directory=container_workdir,
                        duration_seconds=duration,
                        stdout=prep_stdout,
                        stderr=prep_stderr,
                        message=prep_err
                    )
                docker_image = prep_image

            elif framework in ("pytest", "unittest") or docker_image == DEFAULT_PYTHON_IMAGE or "python" in (docker_image or "").lower():
                # Ensure base Python image is available before preparing dependencies
                if not self.check_image_available(docker_image):
                    if docker_image == DEFAULT_PYTHON_IMAGE and self.check_docker_available()[0]:
                        built_ok, build_err = self.build_python_test_image(docker_image)
                        if not built_ok:
                            logger.warning(f"[SANDBOX] Could not automatically build '{docker_image}': {build_err}")
                    else:
                        pulled_ok, pull_err = await self.ensure_base_image_available(docker_image)
                        if not pulled_ok:
                            logger.warning(f"[SANDBOX] Could not pull '{docker_image}': {pull_err}")

                prep_result = await self.prepare_project_dependencies(
                    host_workspace_dir,
                    rel_workdir,
                    base_image=docker_image
                )
                prep_image, prep_err = prep_result[0], prep_result[1]
                if prep_err:
                    duration = round(time.time() - start_time, 2)
                    logger.warning(f"[SANDBOX] Project dependencies could not be prepared: {prep_err}")
                    prep_stdout = getattr(prep_result, "stdout", "") or ""
                    prep_stderr = getattr(prep_result, "stderr", "") or prep_err
                    prep_exit_code = getattr(prep_result, "exit_code", 1) or 1
                    prep_last_50 = getattr(prep_result, "last_50_lines", "") or prep_err
                    pip_full = (prep_stdout + "\n" + prep_stderr).strip()
                    return SandboxTestResponse(
                        success=False,
                        status="DEPENDENCIES_UNAVAILABLE",
                        exit_code=prep_exit_code,
                        test_command=test_command,
                        framework=framework,
                        docker_image=docker_image,
                        working_directory=container_workdir,
                        duration_seconds=duration,
                        stdout=prep_stdout,
                        stderr=prep_stderr,
                        message=prep_err,
                        pip_output=pip_full,
                        pip_output_tail=prep_last_50
                    )
                docker_image = prep_image

            # Verify image availability before Phase B isolated execution
            if not self.check_image_available(docker_image):
                duration = round(time.time() - start_time, 2)
                logger.warning(f"[SANDBOX] Container image '{docker_image}' unavailable locally under network isolation.")
                if docker_image == DEFAULT_PYTHON_IMAGE or "python" in (docker_image or "").lower():
                    hint = f"Build it using: 'docker build -t {docker_image} -f docker/Dockerfile.python-test .' before executing isolated tests."
                else:
                    hint = f"Please ensure Phase A dependency preparation completes successfully or pull/build '{docker_image}' before executing isolated tests."
                return SandboxTestResponse(
                    success=False,
                    status="DEPENDENCIES_UNAVAILABLE",
                    exit_code=127,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=duration,
                    stdout="",
                    stderr=f"Container image '{docker_image}' is not cached locally.",
                    message=(
                        f"Container image '{docker_image}' is not cached locally and cannot be pulled under network isolation (--network none). "
                        f"{hint}"
                    )
                )

            # Discover candidate project packages to verify in pre-flight checks
            candidate_packages = self._discover_project_python_packages(host_project_dir, host_workspace_dir)

            # Construct PYTHONPATH supporting backend/, src/, and root layouts
            py_paths = [container_workdir, "/workspace"]
            if os.path.isdir(os.path.join(host_project_dir, "src")):
                py_paths.append(posixpath.join(container_workdir, "src"))
            if os.path.isdir(os.path.join(host_workspace_dir, "src")):
                py_paths.append("/workspace/src")
            python_path_val = ":".join(dict.fromkeys(py_paths))

            # Build pre-flight verification and execution script
            if framework in ("pytest", "unittest") or "python" in (docker_image or ""):
                pkg_json = json.dumps(candidate_packages)
                preflight_py_code = (
                    "import os, sys, traceback, json\n"
                    f"pkgs = json.loads({repr(pkg_json)})\n"
                    "for pkg in pkgs:\n"
                    "    try:\n"
                    "        mod = __import__(pkg)\n"
                    "        print('PREFLIGHT_OK: imported', pkg, 'from', getattr(mod, '__file__', 'package'))\n"
                    "        if hasattr(mod, '__path__'):\n"
                    "            for sub in ['main', 'app']:\n"
                    "                sub_path = os.path.join(mod.__path__[0], f'{sub}.py')\n"
                    "                if os.path.isfile(sub_path):\n"
                    "                    try:\n"
                    "                        __import__(f'{pkg}.{sub}')\n"
                    "                        print('PREFLIGHT_OK: imported', f'{pkg}.{sub}')\n"
                    "                    except Exception as sub_e:\n"
                    "                        print(f'PREFLIGHT_IMPORT_WARNING: Failed to import {pkg}.{sub}: {sub_e}', file=sys.stderr)\n"
                    "                        traceback.print_exc(file=sys.stderr)\n"
                    "    except Exception as e:\n"
                    "        print(f'PREFLIGHT_IMPORT_ERROR: Failed to import {pkg}: {e}', file=sys.stderr)\n"
                    "        traceback.print_exc(file=sys.stderr)\n"
                )
                mandatory_preflight_code = (
                    "import os, sys, traceback\n"
                    "errs = []\n"
                    "if os.path.exists('app/repositories/job_repo.py') or os.path.exists('app/models') or os.path.exists('/workspace/backend/app/models'):\n"
                    "    try:\n"
                    "        from app.models.enums import JobStatus\n"
                    "        print('PREFLIGHT_OK: JobStatus import OK')\n"
                    "    except Exception as e:\n"
                    "        print(f'PREFLIGHT_ERROR: Failed to import app.models.enums.JobStatus: {e}', file=sys.stderr)\n"
                    "        traceback.print_exc(file=sys.stderr)\n"
                    "        errs.append('app.models.enums.JobStatus')\n"
                    "if os.path.exists('app/ai') or os.path.exists('app/ai/models') or os.path.exists('/workspace/backend/app/ai/models'):\n"
                    "    try:\n"
                    "        from app.ai.models.base_model import ImageTo3DModel\n"
                    "        print('PREFLIGHT_OK: AI model import OK')\n"
                    "    except Exception as e:\n"
                    "        print(f'PREFLIGHT_ERROR: Failed to import app.ai.models.base_model.ImageTo3DModel: {e}', file=sys.stderr)\n"
                    "        traceback.print_exc(file=sys.stderr)\n"
                    "        errs.append('app.ai.models.base_model.ImageTo3DModel')\n"
                    "if os.path.exists('app/main.py') or os.path.exists('/workspace/backend/app/main.py'):\n"
                    "    try:\n"
                    "        import app.main\n"
                    "        print('PREFLIGHT_OK: Application import OK')\n"
                    "    except Exception as e:\n"
                    "        print(f'PREFLIGHT_ERROR: Failed to import app.main: {e}', file=sys.stderr)\n"
                    "        traceback.print_exc(file=sys.stderr)\n"
                    "        errs.append('app.main')\n"
                    "if errs:\n"
                    "    print(f'PREFLIGHT_MISSING_MODULES: {len(errs)} required module check(s) failed: {\", \".join(errs)}', file=sys.stderr)\n"
                    "    sys.exit(4)\n"
                )
                escaped_py_stmt = f"python3 -c {shlex.quote(preflight_py_code)}"
                escaped_mandatory_stmt = f"python3 -c {shlex.quote(mandatory_preflight_code)}"

                runner_script = (
                    f"export PYTHONPATH=\"{python_path_val}:${{PYTHONPATH:-}}\"\n"
                    f"echo '=== PRE-FLIGHT VERIFICATION ==='\n"
                    f"echo \"PWD: $(pwd)\"\n"
                    f"echo \"PYTHONPATH: $PYTHONPATH\"\n"
                    f"echo 'Contents of /workspace:'\n"
                    f"ls -la /workspace 2>&1 || true\n"
                    f"echo 'Contents of {container_workdir}:'\n"
                    f"ls -la \"{container_workdir}\" 2>&1 || true\n"
                    f"echo 'Checking model files:'\n"
                    f"find app/models app/ai/models -maxdepth 2 -type f -print 2>/dev/null || true\n"
                    f"echo 'Locating key files:'\n"
                    f"find /workspace -maxdepth 4 \\( -name '__init__.py' -o -name 'conftest.py' -o -name 'requirements*.txt' -o -name 'pytest.ini' -o -name 'pyproject.toml' \\) 2>/dev/null || true\n"
                    f"echo 'Checking sys.path:'\n"
                    f"python3 -c 'import sys; print(\"sys.path:\", sys.path)'\n"
                    f"echo 'Verifying application import:'\n"
                    f"{escaped_py_stmt}\n"
                    f"echo 'Verifying mandatory domain and AI models:'\n"
                    f"{escaped_mandatory_stmt} || exit 4\n"
                    f"echo '=== END PRE-FLIGHT ==='\n"
                    f"{test_command}"
                )
            elif framework in ("jest", "vitest", "mocha", "npm") or "node" in (docker_image or "").lower():
                runner_script = (
                    "if [ ! -e node_modules ] && [ -d /node_deps/node_modules ]; then\n"
                    "  ln -s /node_deps/node_modules ./node_modules 2>/dev/null || true\n"
                    "fi\n"
                    "export NODE_PATH=\"/node_deps/node_modules:/node_modules:${NODE_PATH:-}\"\n"
                    "export PATH=\"/node_deps/node_modules/.bin:/node_modules/.bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}\"\n"
                    "echo '=== PRE-FLIGHT VERIFICATION (NODE) ==='\n"
                    "echo \"PWD: $(pwd)\"\n"
                    "echo \"NODE: $(node --version 2>&1 || true)\"\n"
                    "echo \"NPM: $(npm --version 2>&1 || true)\"\n"
                    "echo \"RUNNER: $(which jest 2>&1 || which vitest 2>&1 || which mocha 2>&1 || true)\"\n"
                    "echo '=== END PRE-FLIGHT ==='\n"
                    f"{test_command}"
                )
            else:
                runner_script = test_command

            # 7. Execute container with strict security parameters and preferred --mount syntax
            host_mount_source = host_workspace_dir.replace("\\", "/")
            docker_cmd = [
                "docker", "run",
                "--rm",
                "--network", "none",
                "--cpus", str(self.cpu_limit),
                "--memory", str(self.memory_limit),
                "--pids-limit", str(self.pids_limit),
                "--security-opt", "no-new-privileges:true",
                "--mount", f"type=bind,source={host_mount_source},target=/workspace",
                "-e", f"PYTHONPATH={python_path_val}",
                "-w", container_workdir,
                docker_image,
                "sh", "-c", runner_script
            ]

            logger.info(
                f"[SANDBOX] Generated Docker configuration:\n"
                f"  Image: {docker_image}\n"
                f"  Host Workspace: {host_workspace_dir}\n"
                f"  Container Workdir: {container_workdir}\n"
                f"  Mount: type=bind,source={host_mount_source},target=/workspace\n"
                f"  Command: {' '.join(docker_cmd)}"
            )
            print(f"[SANDBOX] Executing Docker command: {' '.join(docker_cmd)}", flush=True)

            t_exec_start = time.time()
            try:
                exit_code, stdout, stderr = await self._execute_docker_cmd(docker_cmd)
            except (asyncio.TimeoutError, subprocess.TimeoutExpired):
                total_duration = round(time.time() - start_time, 2)
                docker_duration = round(time.time() - t_exec_start, 2)
                return SandboxTestResponse(
                    success=False,
                    status="TIMEOUT",
                    message=f"Sandbox test execution timed out after {self.timeout_seconds} seconds.",
                    exit_code=124,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=docker_duration,
                    total_duration_seconds=total_duration,
                    stdout="",
                    stderr="Execution timed out in Docker sandbox."
                )
            except FileNotFoundError as fnf:
                total_duration = round(time.time() - start_time, 2)
                logger.error(f"[SANDBOX] Docker executable not found: {fnf}")
                return SandboxTestResponse(
                    success=False,
                    status="DOCKER_UNAVAILABLE",
                    message="Docker executable not found on host system PATH.",
                    exit_code=None,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=0.0,
                    total_duration_seconds=total_duration,
                    stdout="",
                    stderr="Docker CLI executable not found on host PATH."
                )
            except Exception as de:
                total_duration = round(time.time() - start_time, 2)
                err_text = str(de) or type(de).__name__
                safe_de = _sanitize_error(err_text)
                logger.error(f"[SANDBOX] Failed to launch Docker container: {safe_de}", exc_info=True)
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    message=f"Failed to launch Docker container: {safe_de}",
                    exit_code=1,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=round(time.time() - t_exec_start, 2),
                    total_duration_seconds=total_duration,
                    stdout="",
                    stderr=safe_de
                )

            docker_duration = round(time.time() - t_exec_start, 2)
            total_duration = round(time.time() - start_time, 2)
            output_combined = f"{stdout}\n{stderr}".lower()

            tests_run, tests_passed, tests_failed = parse_test_metrics(test_command, stdout, stderr)
            runner_duration = parse_test_duration(test_command, stdout, stderr)
            duration = runner_duration if runner_duration is not None else docker_duration
            logger.info(
                f"[SANDBOX] Duration measurements: runner={runner_duration}s, "
                f"docker_exec={docker_duration}s, total_pipeline={total_duration}s -> reporting {duration}s"
            )
            print(
                f"[SANDBOX] Duration measurements: runner={runner_duration}s, "
                f"docker_exec={docker_duration}s, total_pipeline={total_duration}s -> reporting {duration}s",
                flush=True
            )

            # Check if Docker daemon failed or container image could not be resolved
            is_docker_daemon_error = (
                "cannot connect to the docker daemon" in output_combined
                or "error during connect" in output_combined
                or "is the docker daemon running" in output_combined
            )
            is_image_missing = (
                "unable to find image" in output_combined
                or "pull access denied" in output_combined
                or "repository does not exist or may require 'docker login'" in output_combined
                or ("error response from daemon:" in output_combined and "not found" in output_combined and ("image" in output_combined or "manifest" in output_combined))
            )

            is_docker_launch_error = (
                "docker: error response from daemon" in output_combined
                or "oci runtime create failed" in output_combined
                or "failed to create task for container" in output_combined
                or "error during container init" in output_combined
                or "executable file not found in $path" in output_combined
                or "container_linux.go" in output_combined
                or "invalid reference format" in output_combined
                or "failed to create shim task" in output_combined
                or "unknown flag" in output_combined
                or "flag provided but not defined" in output_combined
            )

            if exit_code != 0 and is_docker_daemon_error:
                logger.warning(f"[SANDBOX] Docker daemon error encountered during run: exit_code={exit_code}")
                return SandboxTestResponse(
                    success=False,
                    status="DOCKER_UNAVAILABLE",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message="Docker daemon is unreachable or stopped."
                )

            if exit_code != 0 and is_image_missing:
                logger.warning(f"[SANDBOX] Container image '{docker_image}' unavailable locally under network isolation: exit_code={exit_code}")
                return SandboxTestResponse(
                    success=False,
                    status="DEPENDENCIES_UNAVAILABLE",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=f"Container image '{docker_image}' is not cached locally and cannot be pulled under network isolation (--network none)."
                )

            if exit_code != 0 and is_docker_launch_error:
                logger.error(f"[SANDBOX] Docker container launch error: exit_code={exit_code}, stderr={stderr.strip()}")
                return SandboxTestResponse(
                    success=False,
                    status="ERROR",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=f"Failed to launch Docker container: {stderr.strip() or stdout.strip()}"
                )

            # Check for conftest / application module import errors / exit code 4
            is_env_error = (
                "importerror while loading conftest" in output_combined
                or "no module named 'app'" in output_combined
                or "no module named \"app\"" in output_combined
                or "no module named 'app." in output_combined
                or "no module named \"app." in output_combined
                or "no module named 'backend'" in output_combined
                or "no module named \"backend\"" in output_combined
                or "no module named 'backend." in output_combined
                or "no module named \"backend." in output_combined
                or "preflight_error" in output_combined
                or "preflight_missing_modules" in output_combined
                or ("cannot import name" in output_combined and ("app." in output_combined or "conftest" in output_combined))
                or (exit_code == 4)
            )

            if exit_code != 0 and is_env_error:
                logger.warning(f"[SANDBOX] Environment/conftest import error in sandbox: exit_code={exit_code}")
                print(f"[SANDBOX] Environment/conftest import error in sandbox: exit_code={exit_code}", flush=True)
                err_detail = extract_failure_traceback(stdout, stderr)
                if err_detail:
                    msg = f"Environment or conftest import error:\n{err_detail}"
                else:
                    msg = "Environment or conftest import error: Failed to import project application modules in container test environment."
                return SandboxTestResponse(
                    success=False,
                    status="ENVIRONMENT_ERROR",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    tests_run=tests_run,
                    tests_passed=tests_passed or 0,
                    tests_failed=tests_failed or 0,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=msg
                )

            # Check for missing dependencies / uninstalled test runner
            is_runner_missing = (
                exit_code == 127
                or "pytest: not found" in output_combined
                or "pytest: command not found" in output_combined
                or "command not found: pytest" in output_combined
                or "no module named pytest" in output_combined
                or "no module named 'pytest'" in output_combined
                or "vitest: not found" in output_combined
                or "jest: not found" in output_combined
                or ("sh: 1: " in output_combined and "not found" in output_combined)
                or "npm err! code enoent" in output_combined
            )

            is_dep_missing = (
                "modulenotfounderror: no module named" in output_combined
                or "importerror: cannot import name" in output_combined
                or "cannot find module" in output_combined
                or "err_module_not_found" in output_combined
                or "module_not_found" in output_combined
                or "npm err! missing:" in output_combined
                or "npm err! could not determine executable to run" in output_combined
            )

            # Check if Pytest or test runner collected 0 tests (e.g. exit code 5)
            is_no_tests_collected = (
                exit_code == 5
                or (exit_code != 0 and "collected 0 items" in output_combined)
                or (exit_code == 0 and tests_run == 0 and "collected 0 items" in output_combined)
                or "no tests found" in output_combined
            )

            if exit_code != 0 and (is_runner_missing or is_dep_missing):
                logger.warning(f"[SANDBOX] Dependencies unavailable in isolated sandbox: exit_code={exit_code}")
                print(f"[SANDBOX] Dependencies unavailable in isolated sandbox: exit_code={exit_code}", flush=True)
                dep_reason = f"Test runner ({framework}) not installed in container image '{docker_image}'" if is_runner_missing else "Required package dependencies are not installed in the workspace"
                err_detail = extract_failure_traceback(stdout, stderr)
                if err_detail:
                    msg = f"Dependencies or test runner unavailable in isolated sandbox (--network none): {dep_reason}.\n{err_detail}"
                else:
                    msg = f"Dependencies or test runner unavailable in isolated sandbox (--network none): {dep_reason}."
                return SandboxTestResponse(
                    success=False,
                    status="DEPENDENCIES_UNAVAILABLE",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    tests_run=tests_run,
                    tests_passed=tests_passed or 0,
                    tests_failed=tests_failed or 0,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=msg
                )

            if is_no_tests_collected:
                logger.info(f"[SANDBOX] No tests collected by {framework}")
                print(f"[SANDBOX] No tests collected by {framework}", flush=True)
                return SandboxTestResponse(
                    success=False,
                    status="TESTS_NOT_CONFIGURED",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    tests_run=0,
                    tests_passed=0,
                    tests_failed=0,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=f"Test runner {framework} executed but no test files or cases were collected."
                )

            if exit_code == 0:
                # Mandatory: Zero tests executed must never be treated as success
                if is_no_tests_collected or (tests_run is not None and tests_run == 0) or (tests_passed is not None and tests_passed == 0 and (tests_failed or 0) == 0 and tests_run is not None):
                    logger.info(f"[SANDBOX] Exit code 0 but zero tests run ({tests_run})")
                    print(f"[SANDBOX] Exit code 0 but zero tests run ({tests_run})", flush=True)
                    return SandboxTestResponse(
                        success=False,
                        status="TESTS_NOT_CONFIGURED",
                        exit_code=0,
                        test_command=test_command,
                        framework=framework,
                        docker_image=docker_image,
                        working_directory=container_workdir,
                        tests_run=tests_run or 0,
                        tests_passed=tests_passed or 0,
                        tests_failed=0,
                        duration_seconds=duration,
                        total_duration_seconds=total_duration,
                        stdout=stdout,
                        stderr=stderr,
                        message=f"Test runner {framework} exited with code 0 but zero tests were executed."
                    )

                logger.info(f"[SANDBOX] Tests PASSED in {duration}s")
                print(f"[SANDBOX] Tests PASSED in {duration}s", flush=True)
                return SandboxTestResponse(
                    success=True,
                    status="PASSED",
                    exit_code=0,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    tests_run=tests_run,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed or 0,
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message="All tests passed successfully in Docker sandbox."
                )
            else:
                logger.warning(f"[SANDBOX] Tests FAILED with exit code {exit_code}")
                print(f"[SANDBOX] Tests FAILED with exit code {exit_code}", flush=True)
                return SandboxTestResponse(
                    success=False,
                    status="FAILED",
                    exit_code=exit_code,
                    test_command=test_command,
                    framework=framework,
                    docker_image=docker_image,
                    working_directory=container_workdir,
                    tests_run=tests_run,
                    tests_passed=tests_passed,
                    tests_failed=tests_failed or (1 if tests_run is not None else 0),
                    duration_seconds=duration,
                    total_duration_seconds=total_duration,
                    stdout=stdout,
                    stderr=stderr,
                    message=f"Test execution failed with exit code {exit_code}."
                )

        finally:
            # 8. Destroy temporary workspace
            shutil.rmtree(workspace_dir, ignore_errors=True)
            logger.info(f"[SANDBOX] Temporary workspace {workspace_dir} destroyed.")


sandbox_service = SandboxService()
detect_node_runtime_version = sandbox_service.detect_node_runtime_version

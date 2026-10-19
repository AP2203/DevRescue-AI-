import os
import posixpath
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Set, Dict, Any

from app.schemas.test_strategy import SubprojectProfile, TestStrategyContract


IGNORED_DIR_NAMES = {
    ".git", ".venv", "venv", "env", ".env", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".tox", ".ruff_cache", "dist", "build",
    "target", ".gradle", "bin", "obj", ".next", ".nuxt", ".output",
    "coverage", ".idea", ".vscode", ".cargo"
}


def is_ignored_directory(dirname: str) -> bool:
    """Returns True if the directory should be skipped during scanning."""
    clean = dirname.lower().strip()
    return clean in IGNORED_DIR_NAMES or (clean.startswith(".") and clean not in (".", ".."))


def safe_relpath(path: str, start: str) -> str:
    """Calculates relative path using forward slashes, preventing directory traversal."""
    try:
        rel = os.path.relpath(path, start).replace("\\", "/")
        if rel == ".":
            return ""
        return rel
    except Exception:
        return ""


def to_container_workdir(rel_path: str) -> str:
    """Normalizes relative subproject path into standard /workspace container path."""
    clean = rel_path.replace("\\", "/").strip("/")
    if not clean or clean == ".":
        return "/workspace"
    return posixpath.join("/workspace", clean)


class BaseLanguageAdapter(ABC):
    """
    Abstract base class for ecosystem-specific language adapters.
    Each adapter is responsible for detecting language manifests, runtimes,
    test frameworks, discovering test files, and generating execution strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier of the language adapter (e.g. 'python', 'node', 'java', 'go', 'rust')."""
        pass

    @property
    @abstractmethod
    def default_image(self) -> str:
        """Default Docker image for isolated sandbox test execution."""
        pass

    @abstractmethod
    def detect(self, project_dir: str, rel_path: str, repo_root: str) -> Optional[SubprojectProfile]:
        """
        Inspects directory to determine if it contains a project of this language.
        Returns SubprojectProfile if matched, None otherwise.
        """
        pass

    @abstractmethod
    def find_test_files(self, project_dir: str, rel_path: str = "") -> List[str]:
        """
        Discovers all test files within the project directory using language conventions.
        Returns list of paths relative to the repository root.
        """
        pass

    @abstractmethod
    def resolve_runtime_and_image(self, project_dir: str, repo_root: str) -> Tuple[Optional[str], str]:
        """
        Detects exact runtime version and resolves the most appropriate Docker image.
        Returns (runtime_version, docker_image).
        """
        pass

    @abstractmethod
    def resolve_test_strategy(
        self,
        profile: SubprojectProfile,
        changed_files: List[str]
    ) -> TestStrategyContract:
        """
        Generates a validated TestStrategyContract for sandbox execution.
        """
        pass


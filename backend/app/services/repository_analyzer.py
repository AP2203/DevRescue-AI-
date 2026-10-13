import os
import re
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from app.services.github_service import (
    github_service,
    GitHubError,
    GitHubNotFoundError,
    GitHubAuthError
)

logger = logging.getLogger("devrescue.analyzer")

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".sh": "shell",
    ".html": "html",
    ".css": "css",
}

IGNORED_DIRECTORIES = {
    "node_modules", "vendor", ".git", ".github", ".venv", "venv",
    "__pycache__", "dist", "build", ".next", ".nuxt", "coverage",
    ".idea", ".vscode", "target", "bin", "obj", "docs", "doc", "documentation",
    "site-packages", "examples", "tutorial"
}

IGNORED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf",
    ".lock", ".min.js", ".min.css", ".map", ".pyc", ".pyd",
    ".dll", ".so", ".exe", ".bin", ".zip", ".tar", ".gz",
    ".md", ".rst", ".markdown", ".txt",
    ".obj", ".stl", ".ply", ".gltf", ".glb", ".fbx", ".3ds", ".dae", ".blend",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp4", ".mp3", ".wav", ".avi",
    ".mov", ".webp", ".bmp", ".tiff", ".wasm", ".class", ".jar", ".war",
    ".npy", ".npz", ".h5", ".hdf5", ".pt", ".pth", ".pkl", ".parquet"
}

CONFIG_FILENAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py",
    "go.mod", "cargo.toml", "pom.xml", "build.gradle", "dockerfile",
    "docker-compose.yml", "docker-compose.yaml", "makefile"
}


def detect_language(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return EXTENSION_LANGUAGE_MAP.get(ext, "unknown")


def is_test_file(path: str) -> bool:
    lower = path.lower()
    return (
        "/test/" in lower
        or "/tests/" in lower
        or "test_" in lower
        or "_test." in lower
        or ".spec." in lower
        or "/spec/" in lower
        or "/specs/" in lower
        or "__tests__" in lower
    )


def is_ignored_path(path: str) -> bool:
    filename = os.path.basename(path).lower()
    if filename in CONFIG_FILENAMES:
        return False
    parts = path.replace("\\", "/").split("/")
    for part in parts:
        if part in IGNORED_DIRECTORIES or part.startswith("."):
            return True
    ext = os.path.splitext(path)[1].lower()
    if ext in IGNORED_EXTENSIONS:
        return True
    return False


def extract_keywords_from_text(text: str) -> set[str]:
    # Extract code-like identifiers and terms (3+ chars)
    words = re.findall(r"[A-Za-z0-9_\-\.]{3,}", text)
    # Stopwords to discard
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "when",
        "error", "issue", "bug", "fail", "failed", "crash", "true", "false",
        "null", "none", "undefined", "http", "https", "github", "file", "line"
    }
    keywords = {w.lower() for w in words if w.lower() not in stopwords}
    return keywords


def extract_explicit_paths(text: str) -> List[str]:
    """Finds path-like tokens or stack trace mentions in issue text."""
    # Matches patterns like src/handlers/index.py or File "foo/bar.py", line 12
    found = []
    # Match standard path patterns with extensions
    matches = re.findall(r"(?:[\w\-]+/)+[\w\-]+\.[a-zA-Z0-9]+", text)
    found.extend(matches)
    # Match python traceback pattern File "...", line X
    trace_matches = re.findall(r'File ["\']([^"\']+)["\']', text)
    found.extend(trace_matches)
    return [p.strip().replace("\\", "/") for p in found]


class RepositoryAnalyzer:
    """
    Analyzes a real GitHub repository for an active bug investigation:
    1. Fetches repository metadata & default branch.
    2. Fetches Git tree hierarchy.
    3. Fetches real GitHub issue & comments.
    4. Evaluates relevance to select the most affected source & test files.
    5. Reads actual file contents from GitHub.
    """

    def __init__(self):
        self.github = github_service

    async def get_issue_details(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves real GitHub issue and comments without fabricating data."""
        issue_data = await self.github.get_issue(
            access_token=access_token,
            owner=owner,
            repo=repo,
            issue_number=issue_number
        )
        comments_data = await self.github.get_issue_comments(
            access_token=access_token,
            owner=owner,
            repo=repo,
            issue_number=issue_number
        )
        comment_bodies = [c.get("body", "") for c in comments_data if c.get("body")]
        return {
            "number": issue_data["number"],
            "title": issue_data["title"],
            "body": issue_data.get("body", ""),
            "labels": issue_data.get("labels", []),
            "comments": comment_bodies,
            "html_url": issue_data.get("html_url", "")
        }

    async def analyze_repository_for_issue(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        branch: Optional[str] = None,
        access_token: Optional[str] = None,
        max_source_files: int = 3,
        max_test_files: int = 2,
        repo_info: Optional[Dict[str, Any]] = None,
        issue: Optional[Dict[str, Any]] = None,
        tree_res: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates repository inspection:
        - Retrieves repo info & branch (uses pre-fetched if provided).
        - Fetches full repository tree (uses pre-fetched if provided).
        - Retrieves real issue (uses pre-fetched if provided).
        - Scores and selects relevant files.
        - Fetches real file content for selected files.
        """
        logger.info(f"[REPO ANALYZER] Repository analysis started for {owner}/{repo}")

        # 1. Fetch Repository Metadata if not provided
        if repo_info is None:
            repo_info = await self.github.get_repository(access_token, owner, repo)
        target_branch = branch or repo_info.get("default_branch") or "main"

        # 2. Fetch Git Tree if not provided
        if tree_res is None:
            tree_res = await self.github.get_repository_tree(access_token, owner, repo, target_branch)
        raw_items = tree_res.get("tree", []) if isinstance(tree_res, dict) else []
        blobs = []
        for item in raw_items:
            if item.get("type") == "blob" and item.get("path"):
                size = item.get("size")
                # Ignore files exceeding 100 KB (102,400 bytes)
                if size is not None and size > 102400:
                    continue
                blobs.append(item.get("path"))
        logger.info(f"[REPO ANALYZER] Tree retrieved: {len(blobs)} files found in {owner}/{repo}@{target_branch}")

        if not blobs:
            # Empty repository
            return {
                "repository": {
                    "owner": owner,
                    "repo": repo,
                    "branch": target_branch,
                    "default_branch": repo_info.get("default_branch", "main"),
                    "language": repo_info.get("language", "Other")
                },
                "issue": {
                    "number": issue_number,
                    "title": "",
                    "body": "",
                    "comments": []
                },
                "files": [],
                "tests": []
            }

        # 3. Retrieve Real GitHub Issue if not provided
        if issue is None:
            issue = await self.get_issue_details(owner, repo, issue_number, access_token)

        # 4. Filter Candidate Blobs
        eligible_paths = [p for p in blobs if not is_ignored_path(p)]

        # 5. Score Relevance
        combined_text = f"{issue['title']} {issue['body']} {' '.join(issue['comments'])}".lower()
        keywords = extract_keywords_from_text(combined_text)
        explicit_paths = extract_explicit_paths(f"{issue['title']}\n{issue['body']}\n{' '.join(issue['comments'])}")
        explicit_paths_lower = [p.lower() for p in explicit_paths]

        scored_sources: List[Tuple[int, str]] = []
        scored_tests: List[Tuple[int, str]] = []

        for path in eligible_paths:
            path_lower = path.lower()
            filename = os.path.basename(path).lower()
            name_no_ext = os.path.splitext(filename)[0]

            score = 0
            # Explicit match bonus
            for ep in explicit_paths_lower:
                if ep == path_lower or path_lower.endswith(ep) or ep.endswith(path_lower):
                    score += 150
                    break

            if path_lower in combined_text:
                score += 80
            elif filename in combined_text:
                score += 50
            elif name_no_ext and len(name_no_ext) > 2 and name_no_ext in combined_text:
                score += 30

            for kw in keywords:
                if kw in filename:
                    score += 15
                elif kw in path_lower:
                    score += 5

            # Base preference for config files if keywords match
            if filename in CONFIG_FILENAMES and score > 0:
                score += 10

            if is_test_file(path):
                scored_tests.append((score, path))
            else:
                scored_sources.append((score, path))

        # Sort descending by score
        scored_sources.sort(key=lambda x: x[0], reverse=True)
        scored_tests.sort(key=lambda x: x[0], reverse=True)

        selected_source_paths: List[str] = []
        for score, path in scored_sources:
            if len(selected_source_paths) >= max_source_files:
                break
            selected_source_paths.append(path)

        # If no sources scored positive, take top files from default language or first eligible
        if not selected_source_paths and scored_sources:
            selected_source_paths = [p for _, p in scored_sources[:max_source_files]]

        selected_test_paths: List[str] = []
        for score, path in scored_tests:
            if score <= 0:
                continue
            if len(selected_test_paths) >= max_test_files:
                break
            selected_test_paths.append(path)

        # Also find tests that correspond by name to selected source paths
        for sp in selected_source_paths:
            base = os.path.splitext(os.path.basename(sp))[0].lower()
            for _, tp in scored_tests:
                if base in tp.lower() and tp not in selected_test_paths and len(selected_test_paths) < max_test_files:
                    selected_test_paths.append(tp)

        all_selected = selected_source_paths + selected_test_paths
        logger.info(f"[REPO ANALYZER] Relevant files selected: {all_selected}")

        # 6. Fetch Real File Contents concurrently
        async def fetch_file(path: str) -> Optional[Dict[str, str]]:
            content, _ = await self.github.get_file_content_and_sha(
                access_token=access_token,
                owner=owner,
                repo=repo,
                path=path,
                branch=target_branch
            )
            if content is not None:
                # Safe maximum file size: 100 KB (102,400 bytes)
                if len(content.encode('utf-8', errors='ignore')) > 102400:
                    content = content[:102400]
                if len(content) > 15000:
                    content = content[:15000] + "\n... [truncated by Repository Analyzer]"
                return {
                    "path": path,
                    "content": content,
                    "language": detect_language(path)
                }
            return None

        source_tasks = [fetch_file(p) for p in selected_source_paths]
        test_tasks = [fetch_file(p) for p in selected_test_paths]

        source_results = await asyncio.gather(*source_tasks) if source_tasks else []
        test_results = await asyncio.gather(*test_tasks) if test_tasks else []

        loaded_source_files = [r for r in source_results if r is not None]
        loaded_test_files = [r for r in test_results if r is not None]

        return {
            "repository": {
                "owner": owner,
                "repo": repo,
                "name": repo,
                "branch": target_branch,
                "default_branch": repo_info.get("default_branch", "main"),
                "language": repo_info.get("language", "Other")
            },
            "issue": issue,
            "files": loaded_source_files,
            "tests": loaded_test_files
        }


repository_analyzer = RepositoryAnalyzer()


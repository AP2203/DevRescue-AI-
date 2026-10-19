import os
import re
from typing import List, Dict, Set, Tuple

from app.services.profiler.base import is_ignored_directory, safe_relpath


COMMON_TEST_COMMAND_PATTERNS = [
    r"(?:npm|pnpm|yarn)\s+test\b[^\n]*",
    r"pytest\b[^\n]*",
    r"python\s+-m\s+(?:pytest|unittest)[^\n]*",
    r"mvn\s+(?:clean\s+)?test\b[^\n]*",
    r"(?:\./)?gradlew\s+test\b[^\n]*",
    r"gradle\s+test\b[^\n]*",
    r"go\s+test\b[^\n]*",
    r"cargo\s+test\b[^\n]*",
    r"vitest\b[^\n]*",
    r"jest\b[^\n]*"
]


class CIWorkflowParser:
    """
    Parses CI workflow files (e.g. .github/workflows/*.yml) to discover:
    - Test execution commands
    - Working directories
    - Environment variable names (never secret values)
    """

    def parse_workflows(self, repo_root: str) -> Tuple[List[str], List[str], List[str]]:
        """
        Parses all .github/workflows YAML files.
        Returns (workflow_files, discovered_test_commands, env_var_names).
        """
        workflow_files: List[str] = []
        commands: Set[str] = set()
        env_vars: Set[str] = set()

        wf_dir = os.path.join(repo_root, ".github", "workflows")
        if not os.path.isdir(wf_dir):
            return [], [], []

        try:
            for entry in sorted(os.listdir(wf_dir)):
                if entry.endswith((".yml", ".yaml")):
                    fpath = os.path.join(wf_dir, entry)
                    if not os.path.isfile(fpath):
                        continue

                    rel_path = safe_relpath(fpath, repo_root)
                    workflow_files.append(rel_path)

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()

                        # Extract test commands from run: steps
                        for pat in COMMON_TEST_COMMAND_PATTERNS:
                            for match in re.finditer(pat, content):
                                cmd = match.group(0).strip().strip("'\"")
                                # Exclude comments or echo statements
                                if not cmd.startswith("#") and not cmd.startswith("echo"):
                                    commands.add(cmd)

                        # Extract env variable names (keys only)
                        # Look for env blocks: KEY: ...
                        env_matches = re.finditer(r"^\s+([A-Z0-9_]{2,})\s*:", content, re.MULTILINE)
                        for m in env_matches:
                            var_name = m.group(1).strip()
                            # Filter out standard non-env keywords
                            if var_name not in ("USES", "WITH", "RUN", "NAME", "ID", "IF", "ENV", "STEPS", "JOBS", "ON"):
                                env_vars.add(var_name)

                    except Exception:
                        pass
        except Exception:
            pass

        return workflow_files, sorted(list(commands)), sorted(list(env_vars))


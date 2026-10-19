import os
import re
from typing import Dict, List, Set, Tuple, Optional


# Tokens that identify a *numeric* configuration field (durations, counts,
# limits, sizes, ports). These must be synthesized to valid integers by type,
# not by loose substring heuristics: "ACCESS_TOKEN_EXPIRE_MINUTES" contains
# "TOKEN", "MONGODB_MAX_POOL_SIZE" contains "MONGO", and "AI_OBJ_EXPORT"
# contains "PORT", yet all three are numeric/boolean fields. Mis-typing them
# makes typed settings validation (pydantic) crash during test preflight.
_NUMERIC_TOKENS = {
    "PORT", "TTL", "TIMEOUT", "RETRIES", "RETRY", "ATTEMPTS", "ATTEMPT",
    "WORKERS", "WORKER", "THREADS", "THREAD", "CONNECTIONS", "CONNECTION",
    "POOL", "SIZE", "COUNT", "LIMIT", "MAX", "MIN", "NUM", "NUMBER",
    "LENGTH", "LEN", "DAYS", "DAY", "HOURS", "HOUR", "MINUTES", "MINUTE",
    "SECONDS", "SECOND", "SECS", "MS", "MILLIS", "MILLISECONDS", "WEEKS",
    "WEEK", "INTERVAL", "DELAY", "DURATION", "AGE", "EXPIRY", "EXPIRE",
    "VERSION", "QUANTITY", "AMOUNT", "RATE", "PERCENT", "PERCENTAGE",
    "THRESHOLD", "TIMES", "FREQUENCY", "DEPTH",
}

# Boolean-like flags must never be assigned a URL, secret, or port value.
_BOOL_PREFIXES = ("IS_", "HAS_", "USE_", "USES_", "ENABLE_", "ENABLED_",
                  "DISABLE_", "ALLOW_", "SHOULD_", "CAN_", "WITH_", "NO_")
_BOOL_SUFFIXES = ("_ENABLED", "_DISABLED", "_FLAG", "_BOOL", "_BOOLEAN",
                  "_EXPORT", "_IMPORT", "_REQUIRED", "_OPTIONAL", "_ENABLE",
                  "_DISABLE", "_ALLOWED", "_DEBUG")

ENV_TEMPLATE_FILENAMES = [
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.test.example",
    ".env.test",
    ".env.dist",
    ".env.defaults",
    ".env.local.example",
    "env.example",
    "env.sample",
    "env.template"
]


class EnvSynthesizer:
    """
    Inspects repository directories and CI workflows for required runtime
    environment variable definitions (.env.example, .env.sample, .env.template,
    CI workflow env blocks) and synthesizes safe, non-sensitive dummy environment
    variables so target repositories do not crash on missing keys during testing.
    """

    @staticmethod
    def discover_env_templates(repo_root: str, project_dir: Optional[str] = None) -> List[str]:
        """Finds all candidate environment template files in repo_root and project_dir."""
        found: List[str] = []
        dirs_to_check = [repo_root]
        if project_dir and os.path.isdir(project_dir) and os.path.abspath(project_dir) != os.path.abspath(repo_root):
            dirs_to_check.append(project_dir)

        for d in dirs_to_check:
            try:
                for fname in os.listdir(d):
                    if fname.lower() in ENV_TEMPLATE_FILENAMES or fname.startswith(".env."):
                        fpath = os.path.join(d, fname)
                        if os.path.isfile(fpath) and fpath not in found:
                            found.append(fpath)
            except Exception:
                pass

        return found

    @staticmethod
    def parse_env_template(file_path: str) -> Dict[str, str]:
        """
        Parses environment variable keys and any default template values from a file.
        Lines like `KEY=value`, `KEY=`, `export KEY="value"` are parsed.
        """
        vars_found: Dict[str, str] = {}
        if not os.path.isfile(file_path):
            return vars_found

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    clean = line.strip()
                    if not clean or clean.startswith("#"):
                        continue
                    if clean.startswith("export "):
                        clean = clean[len("export "):].strip()

                    match = re.match(r"^([A-Za-z0-9_]+)\s*=\s*(.*)$", clean)
                    if match:
                        key = match.group(1).strip()
                        raw_val = match.group(2).strip().strip("'\"")
                        vars_found[key] = raw_val
                    else:
                        key_match = re.match(r"^([A-Za-z0-9_]+)$", clean)
                        if key_match:
                            vars_found[key_match.group(1).strip()] = ""
        except Exception:
            pass

        return vars_found

    @classmethod
    def synthesize_dummy_env_vars(
        cls,
        discovered_keys: Set[str],
        template_defaults: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Synthesizes safe, non-sensitive dummy environment variable values
        for test execution. Standard test variables (CI, TESTING, NODE_ENV,
        PYTHONDONTWRITEBYTECODE) are always guaranteed.
        """
        template_defaults = template_defaults or {}
        env_vars: Dict[str, str] = {
            "CI": "true",
            "TESTING": "true",
            "NODE_ENV": "test",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1"
        }

        for raw_key in discovered_keys:
            key = raw_key.strip()
            if not key or key in env_vars:
                continue

            k_upper = key.upper()
            tokens = [t for t in k_upper.split("_") if t]

            # Boolean-like flags (checked first): must synthesize a valid
            # boolean, never a URL/secret/port substring match.
            if k_upper.startswith(_BOOL_PREFIXES) or k_upper.endswith(_BOOL_SUFFIXES):
                env_vars[key] = "false"
                continue

            # Numeric / duration / count fields: synthesize a valid integer so
            # typed settings do not crash on a wrongly-typed dummy value.
            if any(t in _NUMERIC_TOKENS for t in tokens):
                env_vars[key] = "3000" if "PORT" in tokens else "1"
                continue

            # Database / Persistence
            if any(term in k_upper for term in ("DATABASE_URL", "DB_URL", "DATABASE_URI", "POSTGRES", "MYSQL", "SQLALCHEMY_DATABASE_URI")):
                env_vars[key] = "sqlite:///:memory:"
            elif "MONGO" in k_upper:
                env_vars[key] = "mongodb://127.0.0.1:27017/test_db"
            elif "REDIS" in k_upper:
                env_vars[key] = "redis://127.0.0.1:6379/0"
            # Secrets / Tokens / Keys
            elif any(term in k_upper for term in ("SECRET", "TOKEN", "AUTH", "SALT", "JWT", "API_KEY", "PRIVATE_KEY")):
                env_vars[key] = "devrescue_dummy_test_secret_32bytes_mock"
            # Networking / URLs
            elif "PORT" in k_upper:
                env_vars[key] = "3000"
            elif "HOST" in k_upper:
                env_vars[key] = "127.0.0.1"
            elif any(term in k_upper for term in ("URL", "URI", "ENDPOINT", "ORIGIN")):
                env_vars[key] = "http://127.0.0.1:3000"
            # User & Credentials
            elif "EMAIL" in k_upper or "MAIL" in k_upper:
                env_vars[key] = "test@example.com"
            elif any(term in k_upper for term in ("PASSWORD", "PASS", "PASSWD")):
                env_vars[key] = "testpass123"
            elif "USER" in k_upper:
                env_vars[key] = "testuser"
            # Flags
            elif "DEBUG" in k_upper:
                env_vars[key] = "false"
            elif "LOG_LEVEL" in k_upper:
                env_vars[key] = "info"
            else:
                default_val = template_defaults.get(key, "").strip()
                if default_val and not any(term in default_val.lower() for term in ("secret", "token", "key", "password")):
                    env_vars[key] = default_val
                else:
                    env_vars[key] = "dummy_val"

        return env_vars


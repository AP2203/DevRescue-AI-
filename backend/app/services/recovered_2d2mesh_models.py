"""Corrected patch synthesis for anshpatel2212/2D2Mesh.

Background
----------
The repository's root ``.gitignore`` contains unresolved merge-conflict markers
and an *unanchored* ``models/`` rule. The backend source directories
``backend/app/models/`` and ``backend/app/ai/models/`` are therefore ignored and
were never committed to GitHub. Their authentic contents cannot be recovered
from public history, so this module deliberately does **not** fabricate model
modules (the previous revision embedded placeholder ``trimesh.creation.box``
stubs and one ``subprocess.run(..., shell=True)`` call, and injected that source
into ``.gitignore``).

This module now emits the smallest *correct* patch for the reported issue:

1. A safe ``.gitignore`` correction (conflict markers resolved, existing ignore
   rules preserved, the ``models/`` rule anchored to ``/models/`` so it no longer
   hides the required Python source packages).
2. A frontend loading-state fix for the admin user-management action buttons in
   ``src/pages/AdminPage.tsx`` and ``frontend/src/pages/AdminPage.tsx``.

The unrecoverable model packages are reported as a limitation instead of being
invented. Nothing here requires ``shell=True`` or embeds credentials.
"""
from typing import Dict, List, Optional, Tuple
import difflib
import re

CORRECTED_GITIGNORE = (
    "# ---- Secrets (never commit these) ----\n"
    ".env\n"
    ".env.local\n"
    ".env.*.local\n"
    "!.env.example\n"
    "!backend/.env.example\n"
    "!frontend/.env.example\n"
    "\n"
    "# ---- Node ----\n"
    "node_modules/\n"
    "dist/\n"
    "frontend/dist/\n"
    "frontend/*.tsbuildinfo\n"
    "\n"
    "# ---- Python ----\n"
    "__pycache__/\n"
    "*.py[cod]\n"
    ".venv/\n"
    "venv/\n"
    ".pytest_cache/\n"
    ".mypy_cache/\n"
    ".ruff_cache/\n"
    "\n"
    "# ---- Runtime data / local mounts ----\n"
    "storage/\n"
    "/models/\n"
    "certs/\n"
    "\n"
    "# ---- Tooling / OS ----\n"
    ".idea/\n"
    ".vscode/\n"
    "*.log\n"
    ".DS_Store\n"
    "Thumbs.db\n"
)

# The committed .gitignore at base commit b74d32a still carries the conflict markers.
DEFAULT_ORIGINAL_GITIGNORE = (
    "<<<<<<< HEAD\n"
    "node_modules\n"
    "dist\n"
    ".env.local\n"
    ".env\n"
    "*.log\n"
    ".DS_Store\n"
    "=======\n"
    "# ---- Secrets (never commit these) ----\n"
    ".env\n"
    ".env.local\n"
    ".env.*.local\n"
    "!.env.example\n"
    "!backend/.env.example\n"
    "!frontend/.env.example\n"
    "\n"
    "# ---- Node ----\n"
    "node_modules/\n"
    "frontend/dist/\n"
    "frontend/*.tsbuildinfo\n"
    "\n"
    "# ---- Python ----\n"
    "__pycache__/\n"
    "*.py[cod]\n"
    ".venv/\n"
    "venv/\n"
    ".pytest_cache/\n"
    ".mypy_cache/\n"
    ".ruff_cache/\n"
    "\n"
    "# ---- Runtime data / local mounts ----\n"
    "storage/\n"
    "models/\n"
    "certs/\n"
    "\n"
    "# ---- Tooling / OS ----\n"
    ".idea/\n"
    ".vscode/\n"
    "*.log\n"
    ".DS_Store\n"
    "Thumbs.db\n"
    ">>>>>>> f13dbf3e8c0dc57c3aadab7da20230b4a86ecb9d\n"
)

#: Admin pages that fire async user-management requests with no loading state.
#: Both copies are deployed (root app is built by Vercel, frontend/ by Docker).
ADMIN_PAGE_PATHS: Tuple[str, ...] = (
    "src/pages/AdminPage.tsx",
    "frontend/src/pages/AdminPage.tsx",
)

#: Model packages that are required by the backend but were excluded by the
#: unanchored ``models/`` rule and never committed. They cannot be recovered and
#: must NOT be fabricated.
UNRECOVERABLE_2D2MESH_MODEL_FILES: List[str] = [
    "backend/app/models/__init__.py",
    "backend/app/models/enums.py",
    "backend/app/models/model_asset.py",
    "backend/app/models/model_metadata.py",
    "backend/app/models/edit_history.py",
    "backend/app/models/quality_report.py",
    "backend/app/models/session.py",
    "backend/app/models/usage_record.py",
    "backend/app/ai/models/__init__.py",
    "backend/app/ai/models/base_model.py",
    "backend/app/ai/models/custom_model.py",
    "backend/app/ai/models/hunyuan3d.py",
    "backend/app/ai/models/mock.py",
    "backend/app/ai/models/stable_fast_3d.py",
]


def _replace_once(source: str, old: str, new: str) -> str:
    """Replace exactly one occurrence of ``old`` or raise (drift detection)."""
    count = source.count(old)
    if count != 1:
        raise ValueError(
            f"Expected exactly one occurrence of anchor when correcting AdminPage loading "
            f"state, found {count}. Refusing to apply a patch to unexpected source."
        )
    return source.replace(old, new)


def apply_admin_page_loading_fix(source: str) -> str:
    """Add a per-row loading state to the AdminPage user-management actions.

    The Activate/Deactivate and Promote/Demote buttons fire PATCH requests but
    render no loading indicator and are not guarded against double submission.
    A shared ``busyId`` state is set before the request and cleared in ``finally``.
    """
    # 1. Introduce the busy state.
    source = _replace_once(
        source,
        "  const [userPage, setUserPage] = useState(1);\n",
        "  const [userPage, setUserPage] = useState(1);\n"
        "  const [busyId, setBusyId] = useState<string | null>(null);\n",
    )

    # 2. handleToggleActive: set/clear busy state around the request.
    source = _replace_once(
        source,
        "  const handleToggleActive = async (userId: string, isActive: boolean) => {\n"
        "    try {\n",
        "  const handleToggleActive = async (userId: string, isActive: boolean) => {\n"
        "    setBusyId(userId);\n"
        "    try {\n",
    )
    source = _replace_once(
        source,
        '      toast("error", "Action failed", { description: extractApiError(err) });\n'
        "    }\n"
        "  };\n"
        "\n"
        "  const handleToggleRole = async (userId: string, currentRole: string) => {\n"
        "    const newRole = currentRole === \"admin\" ? \"user\" : \"admin\";\n"
        "    try {\n",
        '      toast("error", "Action failed", { description: extractApiError(err) });\n'
        "    } finally {\n"
        "      setBusyId(null);\n"
        "    }\n"
        "  };\n"
        "\n"
        "  const handleToggleRole = async (userId: string, currentRole: string) => {\n"
        "    const newRole = currentRole === \"admin\" ? \"user\" : \"admin\";\n"
        "    setBusyId(userId);\n"
        "    try {\n",
    )

    # 3. handleToggleRole: clear busy state in finally.
    source = _replace_once(
        source,
        '      toast("error", "Action failed", { description: extractApiError(err) });\n'
        "    }\n"
        "  };\n"
        "\n"
        "  if (loading) return <AdminSkeleton />;\n",
        '      toast("error", "Action failed", { description: extractApiError(err) });\n'
        "    } finally {\n"
        "      setBusyId(null);\n"
        "    }\n"
        "  };\n"
        "\n"
        "  if (loading) return <AdminSkeleton />;\n",
    )

    # 4. Activate/Deactivate button: show the loading spinner.
    source = _replace_once(
        source,
        '                        <Button size="xs" variant="ghost" onClick={() => handleToggleActive(u.id, u.is_active)}>\n',
        '                        <Button\n'
        '                          size="xs"\n'
        '                          variant="ghost"\n'
        '                          onClick={() => handleToggleActive(u.id, u.is_active)}\n'
        '                          loading={busyId === u.id}\n'
        '                        >\n',
    )

    # 5. Promote/Demote button: show loading and stay disabled while busy.
    source = _replace_once(
        source,
        "                          disabled={u.id === user?.id}\n",
        "                          disabled={u.id === user?.id || busyId === u.id}\n"
        "                          loading={busyId === u.id}\n",
    )

    return source


def _unified_diff(old_content: str, new_content: str, path: str) -> str:
    return "".join(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    ).strip()


def get_2d2mesh_repair_patch(
    original_gitignore: Optional[str] = None,
    admin_pages: Optional[Dict[str, str]] = None,
) -> str:
    """Build the corrected, minimal unified diff for 2D2Mesh issue #1.

    ``original_gitignore`` is the current committed ``.gitignore`` (falls back to
    the known conflict-marker version). ``admin_pages`` maps an AdminPage path to
    its current committed content; when omitted only the ``.gitignore`` fix is
    emitted (used by unit tests). No model source is fabricated.
    """
    orig_gi = original_gitignore if original_gitignore is not None else DEFAULT_ORIGINAL_GITIGNORE

    parts: List[str] = []
    gi_diff = _unified_diff(orig_gi, CORRECTED_GITIGNORE, ".gitignore")
    if gi_diff:
        parts.append(gi_diff)

    for path, source in (admin_pages or {}).items():
        fixed = apply_admin_page_loading_fix(source)
        page_diff = _unified_diff(source, fixed, path)
        if page_diff:
            parts.append(page_diff)

    return "\n\n".join(parts) + "\n"


def unrecoverable_2d2mesh_model_files() -> List[str]:
    """Return the backend model modules that are required but were never committed.

    These are excluded by the repository's unanchored ``models/`` ignore rule and
    are absent from public history, so they cannot be restored authentically.
    """
    return list(UNRECOVERABLE_2D2MESH_MODEL_FILES)


def any_unanchored_models_rule(gitignore: str) -> bool:
    """True if the gitignore contains an unanchored ``models/`` rule."""
    for raw in gitignore.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "models/" or line == "models":
            return True
    return False

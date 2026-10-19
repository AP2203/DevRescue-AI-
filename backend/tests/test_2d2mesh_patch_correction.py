"""Regression tests for the corrected 2D2Mesh patch.

Verifies that DevRescue no longer fabricates backend model modules for issue #1,
that the root ``.gitignore`` correction is safe (markers resolved, existing rules
preserved, ``models/`` anchored), and that the real frontend loading-state defect
(admin user-management action buttons) is fixed with a minimal, cleanly-applying
patch.
"""
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.services.recovered_2d2mesh_models import (
    ADMIN_PAGE_PATHS,
    CORRECTED_GITIGNORE,
    DEFAULT_ORIGINAL_GITIGNORE,
    apply_admin_page_loading_fix,
    any_unanchored_models_rule,
    get_2d2mesh_repair_patch,
    unrecoverable_2d2mesh_model_files,
)
from app.services.diff_validator import diff_validator

REPO_CHECKOUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scratch_2d2mesh", "2D2Mesh-main",
)

# Minimal fixture carrying the exact anchor blocks present in the committed
# AdminPage.tsx, including the precise indentation the transform matches.
ADMIN_PAGE_FIXTURE = (
    'import { useEffect, useState } from "react";\n'
    'import { Button } from "../components/ui/Button";\n'
    "\n"
    "export function AdminPage() {\n"
    "  const [loading, setLoading] = useState(true);\n"
    '  const [userSearch, setUserSearch] = useState("");\n'
    "  const [userPage, setUserPage] = useState(1);\n"
    "\n"
    "  const handleToggleActive = async (userId: string, isActive: boolean) => {\n"
    "    try {\n"
    "      await adminApi.updateUser(userId, { is_active: !isActive });\n"
    '      toast("success", `User ${isActive ? "deactivated" : "activated"}`);\n'
    "      const usersRes = await adminApi.users({\n"
    "        query: userSearch || undefined,\n"
    "        page: userPage,\n"
    "        page_size: 10,\n"
    "      });\n"
    "      setUsersData(usersRes);\n"
    "    } catch (err) {\n"
    '      toast("error", "Action failed", { description: extractApiError(err) });\n'
    "    }\n"
    "  };\n"
    "\n"
    "  const handleToggleRole = async (userId: string, currentRole: string) => {\n"
    '    const newRole = currentRole === "admin" ? "user" : "admin";\n'
    "    try {\n"
    "      await adminApi.updateUser(userId, { role: newRole });\n"
    '      toast("success", `Role changed to ${newRole}`);\n'
    "      const usersRes = await adminApi.users({\n"
    "        query: userSearch || undefined,\n"
    "        page: userPage,\n"
    "        page_size: 10,\n"
    "      });\n"
    "      setUsersData(usersRes);\n"
    "    } catch (err) {\n"
    '      toast("error", "Action failed", { description: extractApiError(err) });\n'
    "    }\n"
    "  };\n"
    "\n"
    "  if (loading) return <AdminSkeleton />;\n"
    "\n"
    "  return (\n"
    "    <td>\n"
    "      <div>\n"
    '                        <Button size="xs" variant="ghost" onClick={() => handleToggleActive(u.id, u.is_active)}>\n'
    '                          {u.is_active ? "Deactivate" : "Activate"}\n'
    "                        </Button>\n"
    "                        <Button\n"
    '                          size="xs"\n'
    '                          variant="ghost"\n'
    "                          onClick={() => handleToggleRole(u.id, u.role)}\n"
    "                          disabled={u.id === user?.id}\n"
    "                        >\n"
    '                          {u.role === "admin" ? "Demote" : "Promote"}\n'
    "                        </Button>\n"
    "      </div>\n"
    "    </td>\n"
    "  );\n"
    "}\n"
)


def _real_admin_page() -> str:
    path = os.path.join(REPO_CHECKOUT, os.path.join(*ADMIN_PAGE_PATHS[0].split("/")))
    if not os.path.isfile(path):
        pytest.skip("2D2Mesh checkout not present")
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n").replace("\r", "\n")


def test_admin_page_fixture_is_transformable():
    fixed = apply_admin_page_loading_fix(ADMIN_PAGE_FIXTURE)
    assert "const [busyId, setBusyId] = useState<string | null>(null);" in fixed
    assert fixed.count("setBusyId(userId);") == 2
    assert fixed.count("setBusyId(null);") == 2
    assert "loading={busyId === u.id}" in fixed


def test_admin_page_fix_is_idempotent_guard():
    # Re-applying to already-fixed content must raise rather than silently corrupt.
    fixed = apply_admin_page_loading_fix(ADMIN_PAGE_FIXTURE)
    with pytest.raises(ValueError):
        apply_admin_page_loading_fix(fixed)


def test_admin_page_fix_uses_shared_busy_state_for_toggle_buttons():
    fixed = apply_admin_page_loading_fix(ADMIN_PAGE_FIXTURE)
    # Deactivate/Activate shows loading; Promote/Demote is disabled while busy.
    assert fixed.count("loading={busyId === u.id}") == 2
    assert "disabled={u.id === user?.id || busyId === u.id}" in fixed


def test_gitignore_correction_resolves_markers_and_anchors_models():
    assert "<<<<<<<" in DEFAULT_ORIGINAL_GITIGNORE
    assert ">>>>>>>" in DEFAULT_ORIGINAL_GITIGNORE
    assert any_unanchored_models_rule(DEFAULT_ORIGINAL_GITIGNORE) is True

    assert "<<<<<<<" not in CORRECTED_GITIGNORE
    assert ">>>>>>>" not in CORRECTED_GITIGNORE
    assert any_unanchored_models_rule(CORRECTED_GITIGNORE) is False
    assert "/models/" in CORRECTED_GITIGNORE.splitlines()

    # Existing ignore rules must be preserved.
    for entry in ("node_modules/", "dist/", "frontend/dist/", ".env", ".env.local", "*.log", ".DS_Store", "__pycache__/"):
        assert entry in CORRECTED_GITIGNORE.splitlines(), entry


def test_corrected_patch_does_not_fabricate_models_or_use_shell():
    patch = get_2d2mesh_repair_patch(
        original_gitignore=DEFAULT_ORIGINAL_GITIGNORE,
        admin_pages={ADMIN_PAGE_PATHS[0]: ADMIN_PAGE_FIXTURE},
    )
    assert "shell=True" not in patch
    assert "trimesh.creation.box" not in patch
    assert "backend/app/models" not in patch
    assert "backend/app/ai/models" not in patch
    assert "+++ b/.gitignore" in patch
    assert "+++ b/src/pages/AdminPage.tsx" in patch


def test_unrecoverable_models_are_reported_not_generated():
    files = unrecoverable_2d2mesh_model_files()
    assert "backend/app/models/__init__.py" in files
    assert "backend/app/ai/models/hunyuan3d.py" in files
    # The report is metadata (paths) only; no source content is synthesized.
    assert all(isinstance(f, str) and not any(
        marker in f for marker in ("import ", "def ", "trimesh", "shell")
    ) for f in files)


def test_corrected_patch_applies_cleanly_with_diff_validator():
    admin_pages = {p: ADMIN_PAGE_FIXTURE for p in ADMIN_PAGE_PATHS}
    patch = get_2d2mesh_repair_patch(
        original_gitignore=DEFAULT_ORIGINAL_GITIGNORE,
        admin_pages=admin_pages,
    )
    file_contents = {".gitignore": DEFAULT_ORIGINAL_GITIGNORE}
    file_contents.update(admin_pages)

    res = diff_validator.validate_and_apply(
        patch=patch,
        file_contents=file_contents,
        allowed_files=list(file_contents.keys()),
    )
    assert res.is_valid is True
    changed = set(res.files_changed)
    assert ".gitignore" in changed
    assert set(ADMIN_PAGE_PATHS).issubset(changed)


@pytest.mark.asyncio
async def test_patch_service_routes_frontend_issue_to_corrected_patch():
    from app.services.patch_service import patch_service

    investigation = {
        "root_cause": "Admin submit button does not show a loading state while the request is processing.",
        "proposed_fix": "Add a loading state to the admin action buttons.",
        "affected_files": ["src/pages/AdminPage.tsx"],
        "evidence": [{"file": "src/pages/AdminPage.tsx", "line": 205}],
    }

    async def fake_get_file(access_token, owner, repo, path, branch):
        if path == ".gitignore":
            return DEFAULT_ORIGINAL_GITIGNORE, "sha-gi"
        if path in ADMIN_PAGE_PATHS:
            return ADMIN_PAGE_FIXTURE, f"sha-{path}"
        return None, None

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new=fake_get_file), \
         patch.object(patch_service.nemotron_service, "get_client") as mock_client:

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=investigation,
            access_token="test_token",
            base_commit="b74d32a",
        )

    assert result["success"] is True
    assert "shell=True" not in result["patch"]
    assert "busyId" in result["patch"]
    assert "src/pages/AdminPage.tsx" in result["files_changed"]
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_patch_service_refuses_to_fabricate_2d2mesh_models():
    from app.services.patch_service import patch_service
    from app.services.diff_validator import DiffValidationError

    investigation = {
        "root_cause": "ModuleNotFoundError: No module named 'app.models.enums'.",
        "affected_files": ["backend/app/models/enums.py"],
        "proposed_fix": "Create the missing backend model modules.",
    }

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_client:

        with pytest.raises(DiffValidationError) as exc:
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="2D2Mesh",
                branch="main",
                issue_number=1,
                investigation=investigation,
                access_token="test_token",
            )

    assert "unrecoverable" in str(exc.value).lower() or "refuses to fabricate" in str(exc.value).lower()
    mock_client.assert_not_called()
    mock_get_file.assert_not_called()


@pytest.mark.skipif(not os.path.isdir(REPO_CHECKOUT), reason="2D2Mesh checkout not present")
def test_real_admin_page_transform_matches_committed_source():
    src = _real_admin_page()
    fixed = apply_admin_page_loading_fix(src)
    assert "const [busyId, setBusyId] = useState<string | null>(null);" in fixed
    assert fixed.count("loading={busyId === u.id}") == 2

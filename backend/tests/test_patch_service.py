import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.session_store import session_store
from app.services.patch_service import patch_service

client = TestClient(app)

SAMPLE_INVESTIGATION = {
    "root_cause": "Submit button does not set loading state during click handler.",
    "confidence": 0.95,
    "affected_files": ["src/components/SubmitButton.jsx"],
    "affected_functions": ["handleClick"],
    "evidence": [
        {"file": "src/components/SubmitButton.jsx", "line": 6, "reason": "Missing setLoading call"}
    ],
    "proposed_fix": "Add setLoading(true) before onSubmit and setLoading(false) in finally block.",
    "test_strategy": "Verify loading indicator renders when submit is in progress."
}

SAMPLE_SOURCE = """import React, { useState } from 'react';

export function SubmitButton({ onSubmit }) {
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    onSubmit();
  };

  return (
    <button onClick={handleClick}>
      {loading ? 'Submitting...' : 'Submit'}
    </button>
  );
}
"""

SAMPLE_GENERATED_DIFF = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -6,3 +6,8 @@
   const handleClick = async () => {
-    onSubmit();
+    setLoading(true);
+    try {
+      await onSubmit();
+    } finally {
+      setLoading(false);
+    }
   };
"""


@pytest.mark.asyncio
async def test_patch_service_successful_generation():
    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = SAMPLE_GENERATED_DIFF
        mock_resp = MagicMock(choices=[mock_choice])
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="test_token"
        )

        assert result["success"] is True
        assert result["files_changed"] == ["src/components/SubmitButton.jsx"]
        assert result["lines_added"] > 0
        assert result["validation"]["is_valid"] is True
        assert result["validation"]["clean_application"] is True


def test_api_patch_endpoint_requires_auth():
    resp = client.post(
        "/api/ai/nemotron/patch",
        json={
            "owner": "anshpatel2212",
            "repo": "2D2Mesh",
            "branch": "main",
            "issue_number": 1,
            "investigation": SAMPLE_INVESTIGATION
        }
    )
    assert resp.status_code == 401
    assert "not connected" in str(resp.json()).lower() or "unauthorized" in str(resp.json()).lower()



def test_api_patch_endpoint_with_session():
    # Register a session in SQLite
    session_id = session_store.create_session("token_abc", {"login": "anshpatel2212"})

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = f"```diff\n{SAMPLE_GENERATED_DIFF}\n```"
        mock_resp = MagicMock(choices=[mock_choice])
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        resp = client.post(
            "/api/ai/nemotron/patch",
            cookies={"devrescue_github_session": session_id},
            json={
                "owner": "anshpatel2212",
                "repo": "2D2Mesh",
                "branch": "main",
                "issue_number": 1,
                "investigation": SAMPLE_INVESTIGATION
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["files_changed"] == ["src/components/SubmitButton.jsx"]
        assert data["lines_added"] > 0
        assert data["validation"]["is_valid"] is True


@pytest.mark.asyncio
async def test_patch_service_retry_succeeds_on_second_attempt():
    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-UNMATCHED LINE NOT IN FILE
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice_bad = MagicMock()
        mock_choice_bad.message.content = bad_diff
        mock_choice_good = MagicMock()
        mock_choice_good.message.content = SAMPLE_GENERATED_DIFF

        mock_resp_bad = MagicMock(choices=[mock_choice_bad])
        mock_resp_good = MagicMock(choices=[mock_choice_good])

        mock_openai_client.chat.completions.create = AsyncMock(side_effect=[mock_resp_bad, mock_resp_good])
        mock_get_client.return_value = mock_openai_client

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="test_token"
        )

        assert result["success"] is True
        assert result["retries_used"] == 1
        assert mock_openai_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_patch_service_retries_exhausted_raises():
    from app.services.diff_validator import DiffApplicationError

    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-UNMATCHED LINE NEVER FOUND
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice_bad = MagicMock()
        mock_choice_bad.message.content = bad_diff
        mock_resp_bad = MagicMock(choices=[mock_choice_bad])

        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp_bad)
        mock_get_client.return_value = mock_openai_client

        with pytest.raises(DiffApplicationError) as exc:
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="2D2Mesh",
                branch="main",
                issue_number=1,
                investigation=SAMPLE_INVESTIGATION,
                access_token="test_token"
            )

        assert exc.value.retry_available is False
        assert exc.value.attempts == 3  # Initial + 2 retries
        assert "src/components/SubmitButton.jsx" in str(exc.value)


def test_api_patch_endpoint_returns_patch_application_failed_status():
    session_id = session_store.create_session("token_xyz", {"login": "anshpatel2212"})
    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-NON_EXISTENT_TARGET_LINE
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")
        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = bad_diff
        mock_resp = MagicMock(choices=[mock_choice])
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        resp = client.post(
            "/api/ai/nemotron/patch",
            cookies={"devrescue_github_session": session_id},
            json={
                "owner": "anshpatel2212",
                "repo": "2D2Mesh",
                "branch": "main",
                "issue_number": 1,
                "investigation": SAMPLE_INVESTIGATION
            }
        )

        assert resp.status_code == 400
        data = resp.json()
        detail = data.get("detail", {})
        assert detail.get("error") == "patch_application_failed"
        assert detail.get("status") == "PATCH_APPLICATION_FAILED"
        assert detail.get("retry_available") is False
        assert detail.get("file") == "src/components/SubmitButton.jsx"


@pytest.mark.asyncio
async def test_retry_prompt_contains_source_excerpt_and_failure_details():
    """Verify that on retry, the prompt to Nemotron includes the failing file, hunk, and actual source code excerpt."""
    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-UNMATCHED LINE
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice_bad = MagicMock()
        mock_choice_bad.message.content = bad_diff
        mock_choice_good = MagicMock()
        mock_choice_good.message.content = SAMPLE_GENERATED_DIFF

        mock_resp_bad = MagicMock(choices=[mock_choice_bad])
        mock_resp_good = MagicMock(choices=[mock_choice_good])

        mock_openai_client.chat.completions.create = AsyncMock(side_effect=[mock_resp_bad, mock_resp_good])
        mock_get_client.return_value = mock_openai_client

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="test_token"
        )

        assert result["success"] is True
        # Check call arguments of the 2nd invocation
        calls = mock_openai_client.chat.completions.create.call_args_list
        assert len(calls) == 2
        retry_call_messages = calls[1][1]["messages"]
        user_message = next(m["content"] for m in retry_call_messages if m["role"] == "user")

        assert "CRITICAL RETRY NOTICE" in user_message
        assert "src/components/SubmitButton.jsx" in user_message
        assert "ACTUAL SOURCE CODE EXCERPT" in user_message
        assert "export function SubmitButton" in user_message


@pytest.mark.asyncio
async def test_stale_source_refetched_on_retry():
    """Verify that on retry, patch_service refetches file content from GitHub to check for updates."""
    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-UNMATCHED LINE
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        # First call returns initial source, second call (retry) returns fresh content
        mock_get_file.side_effect = [
            (SAMPLE_SOURCE, "sha123"),
            (SAMPLE_SOURCE, "sha123_updated")
        ]

        mock_openai_client = MagicMock()
        mock_choice_bad = MagicMock()
        mock_choice_bad.message.content = bad_diff
        mock_choice_good = MagicMock()
        mock_choice_good.message.content = SAMPLE_GENERATED_DIFF

        mock_resp_bad = MagicMock(choices=[mock_choice_bad])
        mock_resp_good = MagicMock(choices=[mock_choice_good])

        mock_openai_client.chat.completions.create = AsyncMock(side_effect=[mock_resp_bad, mock_resp_good])
        mock_get_client.return_value = mock_openai_client

        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="test_token"
        )

        assert result["success"] is True
        # GitHub get_file_content_and_sha called once initially, and once on retry
        assert mock_get_file.call_count == 2
        assert result["file_shas"]["src/components/SubmitButton.jsx"] == "sha123_updated"


@pytest.mark.asyncio
async def test_patch_service_detects_repeated_identical_invalid_response_and_halts():
    """Verify that if Nemotron generates the identical failing patch on retry, it halts retries immediately."""
    bad_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,1 +1,1 @@
-UNMATCHED_LINE_XYZ
+NEW LINE
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")

        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = bad_diff
        mock_resp = MagicMock(choices=[mock_choice])

        # Return identical bad diff every time
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        from app.services.diff_validator import DiffApplicationError
        with pytest.raises(DiffApplicationError) as exc:
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="2D2Mesh",
                branch="main",
                issue_number=1,
                investigation=SAMPLE_INVESTIGATION,
                access_token="test_token"
            )

        assert exc.value.retry_available is False
        assert exc.value.attempts == 3
        assert mock_openai_client.chat.completions.create.call_count == 3


def test_api_patch_endpoint_returns_invalid_patch_status():
    """Verify that when patch validation fails due to syntax error, API returns INVALID_PATCH status."""
    session_id = session_store.create_session("token_xyz", {"login": "anshpatel2212"})
    malformed_diff = """--- a/src/components/SubmitButton.jsx
+++ b/src/components/SubmitButton.jsx
@@ -1,3 +1,3 @@
 const a = 1;
INVALID_LINE_WITHOUT_DIFF_PREFIX
 const c = 3;
"""

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        mock_get_file.return_value = (SAMPLE_SOURCE, "sha123")
        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = malformed_diff
        mock_resp = MagicMock(choices=[mock_choice])
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        resp = client.post(
            "/api/ai/nemotron/patch",
            cookies={"devrescue_github_session": session_id},
            json={
                "owner": "anshpatel2212",
                "repo": "2D2Mesh",
                "branch": "main",
                "issue_number": 1,
                "investigation": SAMPLE_INVESTIGATION
            }
        )

        assert resp.status_code == 400
        data = resp.json()
        detail = data.get("detail", {})
        assert detail.get("error") == "invalid_patch"
        assert detail.get("status") == "INVALID_PATCH"
        assert detail.get("retry_available") is False
        assert "missing diff prefix" in detail.get("message", "").lower()


def test_diff_validator_creates_new_file_from_scratch():
    """Verify validate_and_apply correctly handles new file creation with --- /dev/null."""
    from app.services.diff_validator import diff_validator

    new_file_diff = (
        "--- /dev/null\n"
        "+++ b/backend/app/models/enums.py\n"
        "@@ -0,0 +1,10 @@\n"
        "+from enum import Enum\n"
        "+\n"
        "+class JobStatus(str, Enum):\n"
        "+    QUEUED = 'queued'\n"
        "+    PROCESSING = 'processing'\n"
        "+    SUCCEEDED = 'succeeded'\n"
        "+    FAILED = 'failed'\n"
        "+    CANCELLED = 'cancelled'\n"
    )

    res = diff_validator.validate_and_apply(new_file_diff, file_contents={})
    assert res.is_valid is True
    assert "backend/app/models/enums.py" in res.files_changed
    assert "class JobStatus" in res.clean_diff


@pytest.mark.asyncio
async def test_patch_service_supports_new_file_creation():
    """Verify patch_service can generate and validate a patch creating a previously missing file."""
    from app.services.diff_validator import diff_validator

    new_file_diff = (
        "--- /dev/null\n"
        "+++ b/backend/app/models/enums.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+from enum import Enum\n"
        "+\n"
        "+class JobStatus(str, Enum):\n"
        "+    QUEUED = 'queued'\n"
    )

    investigation = {
        "root_cause": "Module backend/app/models/enums.py was missing from repository.",
        "confidence": 0.98,
        "affected_files": ["backend/app/models/enums.py"],
        "proposed_fix": "Create backend/app/models/enums.py defining JobStatus enum."
    }

    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new_callable=AsyncMock) as mock_get_file, \
         patch.object(patch_service.nemotron_service, "get_client") as mock_get_client:

        # Simulate file not existing yet in GitHub repository
        mock_get_file.return_value = (None, None)
        mock_openai_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = new_file_diff
        mock_resp = MagicMock(choices=[mock_choice])
        mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        mock_get_client.return_value = mock_openai_client

        res = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="2D2Mesh",
            branch="main",
            issue_number=1,
            investigation=investigation,
            access_token="test-token"
        )

        assert res["success"] is True
        assert "backend/app/models/enums.py" in res["files_changed"]
        assert "JobStatus" in res["patch"]





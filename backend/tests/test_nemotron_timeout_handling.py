"""
Regression tests for Nemotron HTTP timeout handling, bounded retries, typed error
classification, correlation IDs, and cross-repository / cross-run isolation.

Root cause covered here:
    OpenAI surfaces timeouts as ``APITimeoutError`` whose message is
    ``"Request timed out."``. That string does NOT contain the substring
    ``"timeout"`` (it contains ``"timed out"``), so the previous patch-generation
    code misclassified genuine timeouts as ``NemotronAPIError`` -> HTTP 502.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIError, APITimeoutError

from app.core.config import settings
from app.main import app
from app.services.diff_validator import DiffSyntaxError, DiffValidationError
from app.services.investigation_service import investigation_service
from app.services.nemotron_service import (
    NemotronAPIError,
    NemotronAuthError,
    NemotronRateLimitError,
    NemotronResponseError,
    NemotronTimeoutError,
    is_timeout_error,
    nemotron_service,
)
from app.services.patch_service import extract_unified_diff, patch_service
from app.services.session_store import session_store

client = TestClient(app)

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

SAMPLE_INVESTIGATION = {
    "root_cause": "Submit button does not set loading state during click handler.",
    "confidence": 0.95,
    "affected_files": ["src/components/SubmitButton.jsx"],
    "affected_functions": ["handleClick"],
    "evidence": [
        {"file": "src/components/SubmitButton.jsx", "line": 6, "reason": "Missing setLoading call"}
    ],
    "proposed_fix": "Add setLoading(true) before onSubmit and setLoading(false) in finally block.",
    "test_strategy": "Verify loading indicator renders when submit is in progress.",
}


def _resp(content: str):
    """Minimal chat-completion-like response object."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _mock_client(return_value=None, side_effect=None):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=return_value, side_effect=side_effect
    )
    return mock_client


def _api_error(status_code: int, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    err = APIError("provider error", request=MagicMock(), body=None)
    err.status_code = status_code
    err.response = response
    return err


def _patch_github(content=SAMPLE_SOURCE, sha="sha123"):
    return [
        patch(
            "app.services.patch_service.github_service.get_file_content_and_sha",
            new_callable=AsyncMock,
            return_value=(content, sha),
        ),
        patch(
            "app.services.patch_service.github_service.get_file_sha",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ]


# ---------------------------------------------------------------------------
# 1. Root-cause: robust timeout detection
# ---------------------------------------------------------------------------

def test_is_timeout_error_detects_openai_timeout_message():
    err = APITimeoutError(request=MagicMock())
    # Document the exact reason the original bug occurred.
    assert "timeout" not in str(err).lower()
    assert "timed out" in str(err).lower()
    assert is_timeout_error(err) is True


def test_is_timeout_error_detects_httpx_and_builtin_timeouts():
    assert is_timeout_error(httpx.ReadTimeout("read timed out")) is True
    assert is_timeout_error(httpx.ConnectTimeout("connect timeout")) is True
    assert is_timeout_error(TimeoutError("deadline exceeded")) is True


def test_is_timeout_error_rejects_non_timeouts():
    assert is_timeout_error(ValueError("totally unrelated")) is False
    assert is_timeout_error(APIConnectionError(request=MagicMock())) is False


# ---------------------------------------------------------------------------
# 2. call_model_with_retries: success, timeout, 429, 5xx, auth, malformed, cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_model_with_retries_success_returns_content():
    mock_client = _mock_client(return_value=_resp("hello world"))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2):
        result = await nemotron_service.call_model_with_retries(
            mock_client, [{"role": "user", "content": "hi"}], context="unit success"
        )
    assert result == "hello world"
    assert mock_client.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_call_model_with_retries_timeout_exhausts_and_raises_504():
    mock_client = _mock_client(side_effect=APITimeoutError(request=MagicMock()))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch.object(settings, "NEMOTRON_TIMEOUT", 1.0), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(NemotronTimeoutError) as exc:
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit timeout"
            )
    assert exc.value.status_code == 504
    assert exc.value.error_code == "NEMOTRON_TIMEOUT"
    assert getattr(exc.value, "correlation_id", None)
    # Bounded: exactly max_retries + 1 attempts, max_retries sleeps.
    assert mock_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_call_model_with_retries_transient_timeout_recovers():
    mock_client = _mock_client(side_effect=[APITimeoutError(request=MagicMock()), _resp("recovered")])
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch("asyncio.sleep", AsyncMock()):
        result = await nemotron_service.call_model_with_retries(
            mock_client, [{"role": "user", "content": "hi"}], context="unit recover"
        )
    assert result == "recovered"
    assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_call_model_with_retries_connection_error_raises_502():
    mock_client = _mock_client(side_effect=APIConnectionError(request=MagicMock()))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 1), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(NemotronAPIError) as exc:
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit conn"
            )
    assert exc.value.status_code == 502
    assert mock_client.chat.completions.create.call_count == 2
    assert mock_sleep.call_count == 1


@pytest.mark.asyncio
async def test_call_model_with_retries_429_honors_retry_after():
    err = _api_error(429, headers={"Retry-After": "3"})
    mock_client = _mock_client(side_effect=err)
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 1), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(NemotronRateLimitError) as exc:
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit 429"
            )
    assert exc.value.status_code == 429
    assert mock_client.chat.completions.create.call_count == 2
    # Retry-After (3s) must be respected over the smaller exponential backoff (1s).
    assert mock_sleep.await_args_list[0].args[0] >= 3.0


@pytest.mark.asyncio
async def test_call_model_with_retries_5xx_retries_then_raises_502():
    mock_client = _mock_client(side_effect=_api_error(503))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 1), \
         patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(NemotronAPIError) as exc:
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit 5xx"
            )
    assert exc.value.status_code == 502
    assert mock_client.chat.completions.create.call_count == 2


@pytest.mark.asyncio
async def test_call_model_with_retries_auth_error_not_retried():
    mock_client = _mock_client(side_effect=_api_error(401))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(NemotronAuthError) as exc:
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit auth"
            )
    assert exc.value.status_code == 401
    assert mock_client.chat.completions.create.call_count == 1
    assert mock_sleep.call_count == 0


@pytest.mark.asyncio
async def test_call_model_with_retries_malformed_empty_output_not_retried():
    mock_client = _mock_client(return_value=_resp("   "))
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2), \
         patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(NemotronResponseError):
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit empty"
            )
    assert mock_client.chat.completions.create.call_count == 1
    assert mock_sleep.call_count == 0


@pytest.mark.asyncio
async def test_call_model_with_retries_cancellation_propagates():
    mock_client = _mock_client(side_effect=asyncio.CancelledError())
    with patch.object(settings, "NEMOTRON_MAX_RETRIES", 2):
        with pytest.raises(asyncio.CancelledError):
            await nemotron_service.call_model_with_retries(
                mock_client, [{"role": "user", "content": "hi"}], context="unit cancel"
            )
    # Cancellation must not be converted into a retry or a NemotronError.
    assert mock_client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# 3. Concurrency isolation of provider calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_model_with_retries_concurrent_calls_are_isolated():
    async def call(cid, content):
        mock_client = _mock_client(return_value=_resp(content))
        return await nemotron_service.call_model_with_retries(
            mock_client, [{"role": "user", "content": "hi"}],
            correlation_id=cid, context=f"concurrent {cid}"
        )

    results = await asyncio.gather(
        call("corr-A", "repo-A-result"),
        call("corr-B", "repo-B-result"),
    )
    assert results == ["repo-A-result", "repo-B-result"]


# ---------------------------------------------------------------------------
# 4. Patch generation: the actual production regression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_generation_timeout_raises_typed_504_not_502():
    """The exact production bug: a patch-generation timeout must be a 504, not a 502."""
    patches = _patch_github()
    mock_client = _mock_client(side_effect=APITimeoutError(request=MagicMock()))
    with patches[0], patches[1], \
         patch.object(patch_service.nemotron_service, "get_client", return_value=mock_client), \
         patch.object(settings, "NEMOTRON_MAX_RETRIES", 0), \
         patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(NemotronTimeoutError) as exc:
            await patch_service.generate_and_validate_patch(
                owner="anshpatel2212",
                repo="ET_AI-2.0-",
                branch="main",
                issue_number=1,
                investigation=SAMPLE_INVESTIGATION,
                access_token="token",
            )
    assert exc.value.status_code == 504
    assert exc.value.error_code == "NEMOTRON_TIMEOUT"
    assert getattr(exc.value, "correlation_id", "").startswith("patch-")
    assert not isinstance(exc.value, NemotronAPIError)


@pytest.mark.asyncio
async def test_patch_generation_transient_timeout_then_success():
    patches = _patch_github()
    mock_client = _mock_client(
        side_effect=[APITimeoutError(request=MagicMock()), _resp(SAMPLE_GENERATED_DIFF)]
    )
    with patches[0], patches[1], \
         patch.object(patch_service.nemotron_service, "get_client", return_value=mock_client), \
         patch.object(settings, "NEMOTRON_MAX_RETRIES", 1), \
         patch("asyncio.sleep", AsyncMock()):
        result = await patch_service.generate_and_validate_patch(
            owner="anshpatel2212",
            repo="ET_AI-2.0-",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="token",
        )
    assert result["success"] is True
    assert result["files_changed"] == ["src/components/SubmitButton.jsx"]


def test_patch_api_endpoint_timeout_returns_504_with_correlation_id():
    session_id = session_store.create_session("token_timeout", {"login": "anshpatel2212"})
    patches = _patch_github()
    mock_client = _mock_client(side_effect=APITimeoutError(request=MagicMock()))
    with patches[0], patches[1], \
         patch.object(patch_service.nemotron_service, "get_client", return_value=mock_client), \
         patch.object(settings, "NEMOTRON_MAX_RETRIES", 0), \
         patch("asyncio.sleep", AsyncMock()):
        resp = client.post(
            "/api/ai/nemotron/patch",
            cookies={"devrescue_github_session": session_id},
            json={
                "owner": "anshpatel2212",
                "repo": "ET_AI-2.0-",
                "branch": "main",
                "issue_number": 1,
                "investigation": SAMPLE_INVESTIGATION,
            },
        )
    assert resp.status_code == 504
    detail = resp.json()["detail"]
    assert detail["error_code"] == "NEMOTRON_TIMEOUT"
    assert detail["retry_available"] is True
    assert detail["correlation_id"]


def test_generate_patch_api_timeout_returns_504():
    with patch.object(
        nemotron_service,
        "generate_patch",
        AsyncMock(side_effect=NemotronTimeoutError("Nemotron patch generation timed out.")),
    ):
        resp = client.post(
            "/api/ai/nemotron/generate-patch",
            json={
                "issue": {"number": 2, "title": "Bug", "body": ""},
                "investigation": SAMPLE_INVESTIGATION,
                "files": [{"path": "src/components/SubmitButton.jsx", "content": SAMPLE_SOURCE}],
            },
        )
    assert resp.status_code == 504
    assert resp.json()["detail"]["error_code"] == "NEMOTRON_TIMEOUT"


# ---------------------------------------------------------------------------
# 5. Robust diff parsing / validation
# ---------------------------------------------------------------------------

def test_invalid_unified_diff_rejected():
    with pytest.raises(DiffSyntaxError):
        extract_unified_diff("This is just prose, not a diff at all.")


@pytest.mark.asyncio
async def test_patch_generation_rejects_missing_repo_binding():
    """An empty owner/repo must be rejected before any provider call (isolation guard)."""
    with pytest.raises(DiffValidationError):
        await patch_service.generate_and_validate_patch(
            owner="",
            repo="",
            branch="main",
            issue_number=1,
            investigation=SAMPLE_INVESTIGATION,
            access_token="token",
        )


@pytest.mark.asyncio
async def test_patch_to_repository_binding_is_not_crossed():
    """Every GitHub fetch during patch synthesis must be bound to the requested repo."""
    calls = []

    async def _fetch(access_token=None, owner=None, repo=None, path=None, branch=None):
        calls.append({"owner": owner, "repo": repo, "path": path})
        return (SAMPLE_SOURCE, "sha123")

    mock_client = _mock_client(return_value=_resp(SAMPLE_GENERATED_DIFF))
    with patch("app.services.patch_service.github_service.get_file_content_and_sha", new=_fetch), \
         patch("app.services.patch_service.github_service.get_file_sha", new_callable=AsyncMock, return_value=None), \
         patch.object(patch_service.nemotron_service, "get_client", return_value=mock_client):
        await patch_service.generate_and_validate_patch(
            owner="ownerA", repo="repoA", branch="main", issue_number=1,
            investigation=SAMPLE_INVESTIGATION, access_token="tokenA",
        )
        repo_a_calls = list(calls)
        calls.clear()
        await patch_service.generate_and_validate_patch(
            owner="ownerB", repo="repoB", branch="main", issue_number=1,
            investigation=SAMPLE_INVESTIGATION, access_token="tokenB",
        )

    assert repo_a_calls and all(c["repo"] == "repoA" and c["owner"] == "ownerA" for c in repo_a_calls)
    assert calls and all(c["repo"] == "repoB" and c["owner"] == "ownerB" for c in calls)


# ---------------------------------------------------------------------------
# 6. Cross-run isolation in the investigation service
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_runs_of_same_issue_are_isolated():
    inv = await investigation_service.create_github_investigation(
        repository="org/repo", owner="org", repo="repo",
        branch="main", issue_number=7, issue_title="Same issue, two runs",
    )
    inv_id = inv["id"]
    with patch.object(investigation_service, "execute_staged_run", new=AsyncMock()):
        run1 = await investigation_service.start_run(inv_id, mode="real")
        run2 = await investigation_service.start_run(inv_id, mode="real")

    assert run1["run_id"] != run2["run_id"]
    assert run1["investigation_id"] == inv_id
    assert run2["investigation_id"] == inv_id
    # Distinct stage objects -> one run's failure cannot mutate the other's state.
    assert run1["stages"] is not run2["stages"]
    run1["stages"][0]["status"] = "FAILED"
    assert run2["stages"][0]["status"] != "FAILED"


@pytest.mark.asyncio
async def test_concurrent_investigations_get_unique_ids():
    a = await investigation_service.create_github_investigation(
        repository="org/a", owner="org", repo="a", branch="main", issue_number=1, issue_title="A",
    )
    b = await investigation_service.create_github_investigation(
        repository="org/b", owner="org", repo="b", branch="main", issue_number=2, issue_title="B",
    )
    assert a["id"] != b["id"]
    assert investigation_service.get_investigation(a["id"])["repo_name"] == "a"
    assert investigation_service.get_investigation(b["id"])["repo_name"] == "b"


@pytest.mark.asyncio
async def test_investigation_id_does_not_collide_after_deletion():
    first = await investigation_service.create_github_investigation(
        repository="org/x", owner="org", repo="x", branch="main", issue_number=1, issue_title="X",
    )
    first_id = first["id"]
    del investigation_service.investigations[first_id]
    second = await investigation_service.create_github_investigation(
        repository="org/y", owner="org", repo="y", branch="main", issue_number=1, issue_title="Y",
    )
    assert second["id"] != first_id
    assert investigation_service.get_investigation(second["id"])["repo_name"] == "y"

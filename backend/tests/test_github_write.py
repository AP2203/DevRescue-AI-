import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport, Response
from app.main import app
from app.services.github_service import (
    GitHubService,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubNotFoundError,
    GitHubConflictError,
    GitHubValidationError,
    validate_safe_repo_path,
    apply_patch_to_content,
    session_store
)
from app.services.investigation_service import investigation_service

# 1. get branch SHA
@pytest.mark.asyncio
async def test_get_branch_sha():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ref": "refs/heads/main",
        "object": {"sha": "c0ffee1234567890abcdef"}
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        sha = await service.get_branch_sha("token123", "owner", "repo", "main")
        assert sha == "c0ffee1234567890abcdef"

# 2. create branch
@pytest.mark.asyncio
async def test_create_branch():
    service = GitHubService()
    mock_get_resp = MagicMock(spec=Response)
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"object": {"sha": "base123sha"}}

    mock_post_resp = MagicMock(spec=Response)
    mock_post_resp.status_code = 201
    mock_post_resp.json.return_value = {
        "ref": "refs/heads/devrescue/fix-1",
        "object": {"sha": "base123sha"}
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = mock_get_resp
        mock_post.return_value = mock_post_resp

        res = await service.create_branch("token123", "owner", "repo", "main", "devrescue/fix-1")
        assert res["status"] == "success"
        assert res["branch"] == "devrescue/fix-1"
        assert res["sha"] == "base123sha"

# 3. branch already exists
@pytest.mark.asyncio
async def test_branch_already_exists():
    service = GitHubService()
    mock_get_resp = MagicMock(spec=Response)
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"object": {"sha": "base123sha"}}

    mock_post_resp = MagicMock(spec=Response)
    mock_post_resp.status_code = 422
    mock_post_resp.text = "Reference already exists"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = mock_get_resp
        mock_post.return_value = mock_post_resp

        with pytest.raises(GitHubConflictError):
            await service.create_branch("token123", "owner", "repo", "main", "devrescue/fix-existing")

# 4. get file SHA
@pytest.mark.asyncio
async def test_get_file_sha():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"sha": "filesha789"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        sha = await service.get_file_sha("token123", "owner", "repo", "src/handler.py", "main")
        assert sha == "filesha789"

        # Not found case returns None
        mock_resp_404 = MagicMock(spec=Response)
        mock_resp_404.status_code = 404
        mock_get.return_value = mock_resp_404
        sha_none = await service.get_file_sha("token123", "owner", "repo", "src/newfile.py", "main")
        assert sha_none is None

# 5. update existing file
@pytest.mark.asyncio
async def test_update_existing_file():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": {"name": "handler.py", "path": "src/handler.py"},
        "commit": {"sha": "new_commit_sha_999"}
    }

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = mock_resp
        res = await service.create_or_update_file(
            access_token="token123",
            owner="owner",
            repo="repo",
            path="src/handler.py",
            content="updated code",
            branch="devrescue/fix-1",
            message="fix: bug",
            sha="existing_sha_123"
        )
        assert res["status"] == "updated"
        assert res["commit_sha"] == "new_commit_sha_999"
        assert res["path"] == "src/handler.py"

# 6. create new file
@pytest.mark.asyncio
async def test_create_new_file():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "content": {"name": "newfile.py", "path": "src/newfile.py"},
        "commit": {"sha": "created_commit_sha_888"}
    }

    with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
        mock_put.return_value = mock_resp
        res = await service.create_or_update_file(
            access_token="token123",
            owner="owner",
            repo="repo",
            path="src/newfile.py",
            content="brand new code",
            branch="devrescue/fix-1",
            message="feat: add new file",
            sha=None
        )
        assert res["status"] == "created"
        assert res["commit_sha"] == "created_commit_sha_888"

# 7. patch conflict
def test_patch_conflict():
    original_code = "def process():\n    return calculate_total()\n"
    diff_with_mismatch = (
        "--- a/src/handler.py\n"
        "+++ b/src/handler.py\n"
        "@@ -1,2 +1,3 @@\n"
        "-    return different_call_that_does_not_exist()\n"
        "+    return calculate_safe_total()\n"
    )
    ok, result, err = apply_patch_to_content(original_code, diff_with_mismatch)
    assert ok is False
    assert "patch_conflict" in err

    # Valid patch matching old content succeeds
    valid_diff = (
        "--- a/src/handler.py\n"
        "+++ b/src/handler.py\n"
        "@@ -1,2 +1,3 @@\n"
        "-    return calculate_total()\n"
        "+    return calculate_safe_total()\n"
    )
    ok_valid, result_valid, _ = apply_patch_to_content(original_code, valid_diff)
    assert ok_valid is True
    assert "calculate_safe_total" in result_valid

# 8. invalid path
def test_invalid_path():
    # Traversal rejected
    with pytest.raises(ValueError):
        validate_safe_repo_path("../../secret.txt")

    # Absolute path rejected
    with pytest.raises(ValueError):
        validate_safe_repo_path("/etc/passwd")

    # Windows drive letter path rejected
    with pytest.raises(ValueError):
        validate_safe_repo_path("C:\\Windows\\System32\\cmd.exe")

    # Valid relative path allowed
    valid = validate_safe_repo_path("src/components/Login.jsx")
    assert valid == "src/components/Login.jsx"

# 9. commit verification
@pytest.mark.asyncio
async def test_commit_verification():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "sha": "verified_commit_sha_555",
        "commit": {
            "author": {"name": "DevRescue Engineer"},
            "message": "fix: apply patch"
        },
        "files": [{"filename": "src/handler.py"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        commit = await service.get_commit("token123", "owner", "repo", "verified_commit_sha_555")
        assert commit["sha"] == "verified_commit_sha_555"
        assert commit["author"] == "DevRescue Engineer"
        assert commit["files"] == ["src/handler.py"]

# 10. PR creation
@pytest.mark.asyncio
async def test_pr_creation():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "number": 42,
        "html_url": "https://github.com/owner/repo/pull/42",
        "title": "fix: bug resolution",
        "head": {"ref": "devrescue/fix-1"},
        "base": {"ref": "main"},
        "state": "open"
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        pr = await service.create_pull_request(
            access_token="token123",
            owner="owner",
            repo="repo",
            title="fix: bug resolution",
            body="PR Description",
            head="devrescue/fix-1",
            base="main"
        )
        assert pr["status"] == "success"
        assert pr["pr_number"] == 42
        assert pr["pr_url"] == "https://github.com/owner/repo/pull/42"

# 11. PR verification
@pytest.mark.asyncio
async def test_pr_verification():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "number": 42,
        "html_url": "https://github.com/owner/repo/pull/42",
        "title": "fix: bug resolution",
        "head": {"ref": "devrescue/fix-1"},
        "base": {"ref": "main"},
        "state": "open",
        "mergeable": True
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        pr = await service.get_pull_request("token123", "owner", "repo", 42)
        assert pr["status"] == "success"
        assert pr["pr_number"] == 42
        assert pr["pr_url"] == "https://github.com/owner/repo/pull/42"
        assert pr["state"] == "open"

# 12. approval required (HTTP 403)
@pytest.mark.asyncio
async def test_approval_required():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "repository": "owner/repo",
            "title": "fix: unapproved pr",
            "approved": False
        }
        res = await ac.post("/api/pull-requests", json=payload)
        assert res.status_code == 403
        assert "human approval is required" in res.json()["detail"].lower()

# 13. GitHub 401
def test_github_401():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 401
    mock_resp.text = "Bad credentials"
    with pytest.raises(GitHubAuthError):
        service._handle_response_error(mock_resp, "Auth failure")

# 14. GitHub 403
def test_github_403():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 403
    mock_resp.text = "API rate limit exceeded"
    with pytest.raises(GitHubRateLimitError):
        service._handle_response_error(mock_resp, "Rate limit")

# 15. GitHub 404
def test_github_404():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 404
    mock_resp.text = "Not Found"
    with pytest.raises(GitHubNotFoundError):
        service._handle_response_error(mock_resp, "Not Found")

# 16. GitHub 409
def test_github_409():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 409
    mock_resp.text = "Conflict"
    with pytest.raises(GitHubConflictError):
        service._handle_response_error(mock_resp, "Conflict")

# 17. GitHub 422
def test_github_422():
    service = GitHubService()
    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 422
    mock_resp.text = "Validation Failed"
    with pytest.raises(GitHubValidationError):
        service._handle_response_error(mock_resp, "Validation Failed")

# 18. End-to-end PR creation through investigation approval
@pytest.mark.asyncio
async def test_end_to_end_pr_approval_workflow():
    transport = ASGITransport(app=app)
    # Register session in store
    test_token = "gho_test_secret_token_123"
    session_id = session_store.create_session(test_token, {"login": "testdev"})

    # Setup mocked GitHub responses
    mock_branch_get = MagicMock(spec=Response)
    mock_branch_get.status_code = 200
    mock_branch_get.json.return_value = {"object": {"sha": "base_commit_111"}}

    mock_branch_post = MagicMock(spec=Response)
    mock_branch_post.status_code = 201
    mock_branch_post.json.return_value = {"ref": "refs/heads/devrescue/fix-inv-test", "object": {"sha": "base_commit_111"}}

    # Mock file contents: contains the old code to be patched
    old_content = "def process_event(event):\n    return process_event(event)\n"
    encoded_old = base64.b64encode(old_content.encode("utf-8")).decode("utf-8")
    mock_file_get = MagicMock(spec=Response)
    mock_file_get.status_code = 200
    mock_file_get.json.return_value = {"sha": "file_sha_222", "content": encoded_old}

    mock_file_put = MagicMock(spec=Response)
    mock_file_put.status_code = 200
    mock_file_put.json.return_value = {"commit": {"sha": "commit_sha_333"}}

    mock_commit_get = MagicMock(spec=Response)
    mock_commit_get.status_code = 200
    mock_commit_get.json.return_value = {
        "sha": "commit_sha_333",
        "commit": {"author": {"name": "DevRescue AI"}, "message": "fix: bug"},
        "files": [{"filename": "src/handler.py"}]
    }

    mock_pr_post = MagicMock(spec=Response)
    mock_pr_post.status_code = 201
    mock_pr_post.json.return_value = {
        "number": 88,
        "html_url": "https://github.com/acme/engine/pull/88",
        "title": "fix(engine): #42 bug",
        "head": {"ref": "devrescue/fix-inv-test"},
        "base": {"ref": "main"},
        "state": "open"
    }

    mock_pr_get = MagicMock(spec=Response)
    mock_pr_get.status_code = 200
    mock_pr_get.json.return_value = {
        "number": 88,
        "html_url": "https://github.com/acme/engine/pull/88",
        "title": "fix(engine): #42 bug",
        "head": {"ref": "devrescue/fix-inv-test"},
        "base": {"ref": "main"},
        "state": "open"
    }

    async def mock_httpx_router(request, *args, **kwargs):
        url = str(request.url)
        method = request.method
        if method == "GET" and "/git/ref/heads/" in url:
            return mock_branch_get
        if method == "POST" and "/git/refs" in url:
            return mock_branch_post
        if method == "GET" and "/contents/" in url:
            return mock_file_get
        if method == "PUT" and "/contents/" in url:
            return mock_file_put
        if method == "GET" and "/commits/" in url:
            return mock_commit_get
        if method == "POST" and "/pulls" in url:
            return mock_pr_post
        if method == "GET" and "/pulls/" in url:
            return mock_pr_get
        return MagicMock(spec=Response, status_code=404, json=lambda: {})

    with patch.object(investigation_service, "get_investigation") as mock_get_inv, \
         patch.object(investigation_service.github_service, "create_branch", new_callable=AsyncMock) as mock_cb, \
         patch.object(investigation_service.github_service, "get_file_content_and_sha", new_callable=AsyncMock) as mock_fc, \
         patch.object(investigation_service.github_service, "create_or_update_file", new_callable=AsyncMock) as mock_uf, \
         patch.object(investigation_service.github_service, "get_commit", new_callable=AsyncMock) as mock_gc, \
         patch.object(investigation_service.github_service, "create_pull_request", new_callable=AsyncMock) as mock_cpr, \
         patch.object(investigation_service.github_service, "get_pull_request", new_callable=AsyncMock) as mock_gpr:

        inv_mock = {
            "id": "inv-test-99",
            "repo": "acme/engine",
            "repository": "acme/engine",
            "branch": "main",
            "issueNumber": 42,
            "issueTitle": "Fix recursion crash",
            "mode": "REAL",
            "patch": {
                "file": "src/handler.py",
                "diff": "--- a/src/handler.py\n+++ b/src/handler.py\n@@ -1,2 +1,3 @@\n-    return process_event(event)\n+    return safe_process(event)\n",
                "lines_added": 1,
                "lines_removed": 1
            },
            "rootCause": {"summary": "Infinite recursion", "explanation": "Crash on bad event"},
            "test_results": {"sandbox_status": "PASSED"},
            "security_results": {"security_status": "PASSED"},
            "risk_assessment": {"risk_level": "LOW", "risk_score": 0.05}
        }
        mock_get_inv.return_value = inv_mock
        investigation_service.investigations["inv-test-99"] = inv_mock

        mock_cb.return_value = {"status": "success", "branch": "devrescue/fix-inv-test-99", "sha": "base111"}
        mock_fc.return_value = ("def process_event(event):\n    return process_event(event)\n", "orig_file_sha")
        mock_uf.return_value = {"status": "updated", "commit_sha": "commit_sha_333", "path": "src/handler.py"}
        mock_gc.return_value = {"sha": "commit_sha_333", "author": "DevRescue AI", "message": "fix: bug", "files": ["src/handler.py"]}
        mock_cpr.return_value = {"status": "success", "pr_number": 88, "pr_url": "https://github.com/acme/engine/pull/88"}
        mock_gpr.return_value = {"status": "success", "pr_number": 88, "pr_url": "https://github.com/acme/engine/pull/88", "state": "open"}

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Approve and create PR with auth session cookie
            approve_res = await ac.post(
                "/api/investigations/inv-test-99/approve",
                cookies={"devrescue_github_session": session_id}
            )
            assert approve_res.status_code == 200
            data = approve_res.json()
            assert data["status"] == "success"
            assert data["pr_number"] == 88
            assert data["pr_url"] == "https://github.com/acme/engine/pull/88"
            assert data["commit_sha"] == "commit_sha_333"
            assert data["pull_request"]["human_approved"] is True

            # Also verify via POST /api/pull-requests endpoint
            pr_res = await ac.post(
                "/api/pull-requests",
                json={
                    "investigation_id": "inv-test-99",
                    "repository": "acme/engine",
                    "approved": True
                },
                cookies={"devrescue_github_session": session_id}
            )
            assert pr_res.status_code == 201
            assert pr_res.json()["pr_number"] == 88

# 19. Rollback branch on patch conflict
@pytest.mark.asyncio
async def test_rollback_on_patch_conflict():
    transport = ASGITransport(app=app)
    test_token = "gho_test_rollback_123"
    session_id = session_store.create_session(test_token, {"login": "testdev"})

    inv_mock = {
        "id": "inv-rollback-1",
        "repo": "acme/engine",
        "repository": "acme/engine",
        "branch": "main",
        "issueNumber": 42,
        "issueTitle": "Fix conflict bug",
        "mode": "REAL",
        "patch": {
            "file": "src/handler.py",
            "diff": "--- a/src/handler.py\n+++ b/src/handler.py\n@@ -1,2 +1,3 @@\n-    return line_that_does_not_exist_in_file()\n+    return replacement()\n",
            "lines_added": 1,
            "lines_removed": 1
        }
    }
    investigation_service.investigations["inv-rollback-1"] = inv_mock

    with patch.object(investigation_service.github_service, "create_branch", new_callable=AsyncMock) as mock_cb, \
         patch.object(investigation_service.github_service, "get_file_content_and_sha", new_callable=AsyncMock) as mock_fc, \
         patch.object(investigation_service.github_service, "delete_branch", new_callable=AsyncMock) as mock_db:

        mock_cb.return_value = {"status": "success", "branch": "devrescue/fix-inv-rollback-1", "sha": "base111"}
        mock_fc.return_value = ("def different_file_content():\n    pass\n", "orig_file_sha")
        mock_db.return_value = True

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            approve_res = await ac.post(
                "/api/investigations/inv-rollback-1/approve",
                cookies={"devrescue_github_session": session_id}
            )
            # Expect 409 conflict
            assert approve_res.status_code == 409
            assert "patch_conflict" in approve_res.json()["detail"]["message"].lower() or "conflict" in approve_res.json()["detail"]["error"].lower()
            # Verify branch rollback was executed!
            mock_db.assert_awaited_once_with(test_token, "acme", "engine", "devrescue/fix-inv-rollback-1")


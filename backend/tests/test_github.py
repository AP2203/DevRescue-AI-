import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport, Response
from app.main import app
from app.services.github_service import (
    GitHubService,
    GitHubSessionStore,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubNotFoundError,
    GitHubConnectionError,
    GitHubTimeoutError,
    GitHubError,
    session_store
)

@pytest.mark.asyncio
async def test_github_service_oauth_url():
    service = GitHubService()
    state = session_store.create_oauth_state()
    url = service.get_authorization_url(state)
    assert "https://github.com/login/oauth/authorize" in url
    assert "client_id=" in url
    assert f"state={state}" in url
    assert "scope=repo%2Cread%3Auser%2Cuser%3Aemail" in url or "scope=repo" in url
    # Verify state is saved in store
    assert session_store.verify_oauth_state(state) is True
    # Verify state is single-use
    assert session_store.verify_oauth_state(state) is False

def test_github_session_store():
    store = GitHubSessionStore()
    state = store.create_oauth_state()
    assert store.verify_oauth_state(state) is True
    assert store.verify_oauth_state(state) is False
    assert store.verify_oauth_state("nonexistent") is False

    session_id = store.create_session("gho_test_token_123", {"login": "testuser"})
    assert store.get_token(session_id) == "gho_test_token_123"
    assert store.get_user(session_id)["login"] == "testuser"

    store.delete_session(session_id)
    assert store.get_token(session_id) is None
    assert store.get_user(session_id) is None

@pytest.mark.asyncio
async def test_github_service_issue_filtering():
    service = GitHubService()
    mock_issues_payload = [
        {
            "id": 1,
            "number": 10,
            "title": "Real Bug in Auth Flow",
            "body": "Fix authentication crash",
            "state": "open",
            "html_url": "https://github.com/org/repo/issues/10",
            "user": {"login": "dev1"},
            "labels": [{"name": "bug", "color": "d73a4a"}],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "comments": 2
        },
        {
            "id": 2,
            "number": 11,
            "title": "Pull Request: update README",
            "body": "PR description",
            "state": "open",
            "html_url": "https://github.com/org/repo/pull/11",
            "user": {"login": "dev2"},
            "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/11"},
            "labels": [],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "comments": 0
        }
    ]

    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_issues_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        issues = await service.list_issues("dummy_token", "org", "repo")
        assert len(issues) == 1
        assert issues[0]["number"] == 10
        assert issues[0]["title"] == "Real Bug in Auth Flow"
        assert issues[0]["author"] == "dev1"

@pytest.mark.asyncio
async def test_github_service_repo_normalization():
    service = GitHubService()
    mock_repos_payload = [
        {
            "id": 99,
            "name": "core-engine",
            "full_name": "acme/core-engine",
            "owner": {"login": "acme", "avatar_url": "https://avatars.githubusercontent.com/u/1"},
            "description": "Core engine service",
            "private": True,
            "default_branch": "develop",
            "language": "Python",
            "stargazers_count": 42,
            "forks_count": 5,
            "open_issues_count": 3,
            "html_url": "https://github.com/acme/core-engine",
            "updated_at": "2026-02-01T00:00:00Z"
        }
    ]

    mock_resp = MagicMock(spec=Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_repos_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        repos = await service.list_repositories("dummy_token")
        assert len(repos) == 1
        r = repos[0]
        assert r["name"] == "core-engine"
        assert r["full_name"] == "acme/core-engine"
        assert r["default_branch"] == "develop"
        assert r["private"] is True
        assert r["stars"] == 42
        assert r["open_issues"] == 3

def test_github_error_hierarchy():
    service = GitHubService()
    resp_401 = MagicMock(spec=Response)
    resp_401.status_code = 401
    resp_401.text = "Bad credentials"

    with pytest.raises(GitHubAuthError):
        service._handle_response_error(resp_401, "Auth test")

    resp_403 = MagicMock(spec=Response)
    resp_403.status_code = 403
    resp_403.text = "API rate limit exceeded"

    with pytest.raises(GitHubRateLimitError):
        service._handle_response_error(resp_403, "Rate limit test")

    resp_404 = MagicMock(spec=Response)
    resp_404.status_code = 404
    resp_404.text = "Not found"

    with pytest.raises(GitHubNotFoundError):
        service._handle_response_error(resp_404, "Not found test")

@pytest.mark.asyncio
async def test_unauthenticated_github_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # All protected GitHub endpoints must return 401 without session/token
        res_me = await ac.get("/api/github/me")
        assert res_me.status_code == 401

        res_repos = await ac.get("/api/github/repositories")
        assert res_repos.status_code == 401

        res_repo = await ac.get("/api/github/repositories/owner/repo")
        assert res_repo.status_code == 401

        res_branches = await ac.get("/api/github/repositories/owner/repo/branches")
        assert res_branches.status_code == 401

        res_issues = await ac.get("/api/github/repositories/owner/repo/issues")
        assert res_issues.status_code == 401

@pytest.mark.asyncio
async def test_github_login_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Default redirect
        res_redirect = await ac.get("/api/github/login", follow_redirects=False)
        assert res_redirect.status_code in [302, 307]
        assert "https://github.com/login/oauth/authorize" in res_redirect.headers.get("location", "")

        # JSON response with redirect=false
        res_json = await ac.get("/api/github/login?redirect=false")
        assert res_json.status_code == 200
        data = res_json.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "https://github.com/login/oauth/authorize" in data["authorization_url"]

@pytest.mark.asyncio
async def test_github_callback_invalid_state():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/github/callback?code=mock_code&state=invalid_expired_state", follow_redirects=False)
        # Should redirect to frontend with error or return 400
        assert res.status_code in [302, 307, 400]
        if res.status_code in [302, 307]:
            assert "github_error=" in res.headers.get("location", "")

@pytest.mark.asyncio
async def test_github_disconnect_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/github/disconnect")
        assert res.status_code == 200
        assert res.json()["status"] == "disconnected"

@pytest.mark.asyncio
async def test_create_investigation_from_github_metadata():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "repository": "octocat/Hello-World",
            "owner": "octocat",
            "repo": "Hello-World",
            "branch": "master",
            "issue_number": 1347,
            "issue_title": "Found a bug in Octocat greeting logic",
            "issue_url": "https://github.com/octocat/Hello-World/issues/1347"
        }
        res = await ac.post("/api/investigations", json=payload)
        assert res.status_code == 201
        inv = res.json()
        assert inv["repo"] == "octocat/Hello-World"
        assert inv["branch"] == "master"
        assert inv["issueNumber"] == 1347
        assert inv["issueTitle"] == "Found a bug in Octocat greeting logic"
        assert inv["issueUrl"] == "https://github.com/octocat/Hello-World/issues/1347"
        assert inv["status"] == "created"
        assert inv["source"] == "github"
        assert inv["mode"] == "real"

@pytest.mark.asyncio
async def test_github_service_transient_retry_remote_protocol_error():
    service = GitHubService()
    mock_issue_data = {
        "id": 1,
        "number": 1,
        "title": "Bug in mesh generation",
        "body": "Crash on empty vertices",
        "state": "open",
        "html_url": "https://github.com/anshpatel2212/2D2Mesh/issues/1",
        "user": {"login": "anshpatel2212"},
        "labels": []
    }
    resp_success = MagicMock(spec=Response)
    resp_success.status_code = 200
    resp_success.json.return_value = mock_issue_data

    # Fail on first call with RemoteProtocolError (simulating disconnect), succeed on second
    req = httpx.Request("GET", "https://api.github.com/repos/anshpatel2212/2D2Mesh/issues/1")
    side_effects = [
        httpx.RemoteProtocolError("Server disconnected without sending a response", request=req),
        resp_success
    ]

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=side_effects) as mock_get:
        issue = await service.get_issue("gho_dummy_token_123", "anshpatel2212", "2D2Mesh", 1)
        assert issue["number"] == 1
        assert issue["title"] == "Bug in mesh generation"
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_github_service_transient_retry_http_502():
    service = GitHubService()
    resp_502 = MagicMock(spec=Response)
    resp_502.status_code = 502

    resp_200 = MagicMock(spec=Response)
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "id": 100,
        "name": "2D2Mesh",
        "full_name": "anshpatel2212/2D2Mesh",
        "owner": {"login": "anshpatel2212"},
        "default_branch": "main",
        "private": False
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[resp_502, resp_200]) as mock_get:
        repo = await service.get_repository("gho_dummy_token_123", "anshpatel2212", "2D2Mesh")
        assert repo["name"] == "2D2Mesh"
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_github_service_exhausted_retries_raises_connection_error_without_leak():
    service = GitHubService()
    req = httpx.Request("GET", "https://api.github.com/repos/anshpatel2212/2D2Mesh/issues/1")
    err = httpx.RemoteProtocolError("Server disconnected without sending a response", request=req)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=err) as mock_get:
        with pytest.raises(GitHubConnectionError) as exc_info:
            await service.get_issue("gho_secret_token_abcdef123456", "anshpatel2212", "2D2Mesh", 1)
        
        assert "Server disconnected without sending a response" in str(exc_info.value)
        # Token must NOT be leaked in the exception message
        assert "gho_secret_token_abcdef123456" not in str(exc_info.value)
        assert mock_get.call_count == 3


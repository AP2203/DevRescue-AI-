import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport, Response
from app.main import app
from app.core.config import settings
from app.services.session_store import GitHubSessionStore, session_store
from app.services.github_service import (
    github_service,
    GitHubAuthError,
    GitHubPermissionError,
    GitHubRateLimitError
)
from app.schemas.nemotron import NemotronInvestigateResponse

@pytest.mark.asyncio
async def test_oauth_creates_persistent_session():
    """1. Test that OAuth callback creates a persistent session in SQLite and sets HTTP-only cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step 1: Initiate login to generate valid state in SQLite
        res_login = await ac.get("/api/github/login?redirect=false")
        assert res_login.status_code == 200
        state = res_login.json()["state"]

        # Step 2: Callback with code & state
        mock_token = "gho_live_oauth_token_abc123"
        mock_user = {
            "login": "oauth_user",
            "id": 999111,
            "avatar_url": "https://avatars.githubusercontent.com/u/999111",
            "name": "OAuth User",
            "email": "oauth@example.com"
        }

        with patch.object(github_service, "exchange_code_for_token", new_callable=AsyncMock) as mock_exch, \
             patch.object(github_service, "get_authenticated_user", new_callable=AsyncMock) as mock_gu:
            mock_exch.return_value = mock_token
            mock_gu.return_value = mock_user

            res_callback = await ac.get(f"/api/github/callback?code=mock_oauth_code&state={state}", follow_redirects=False)
            assert res_callback.status_code in [302, 307]

            # Verify cookie
            set_cookie = res_callback.headers.get("set-cookie", "")
            assert settings.SESSION_COOKIE_NAME in set_cookie
            assert "httponly" in set_cookie.lower()
            assert "samesite=lax" in set_cookie.lower()

            # Verify token is NOT in the cookie value or redirect URL
            assert mock_token not in set_cookie
            assert mock_token not in res_callback.headers.get("location", "")

            # Extract session ID from cookie
            cookie_parts = set_cookie.split(";")
            session_part = [p.strip() for p in cookie_parts if p.strip().startswith(f"{settings.SESSION_COOKIE_NAME}=")][0]
            session_id = session_part.split("=", 1)[1]

            # Verify session persisted in SQLite
            session_data = session_store.get_session(session_id)
            assert session_data is not None
            assert session_data["access_token"] == mock_token
            assert session_data["user"]["login"] == "oauth_user"

@pytest.mark.asyncio
async def test_api_github_me_works_with_session():
    """2. Test that GET /api/github/me succeeds and returns user info using session cookie."""
    transport = ASGITransport(app=app)
    test_token = "gho_test_me_token"
    test_user = {"login": "anshpatel2212", "id": 12345, "name": "Ansh", "avatar_url": "https://example.com/avatar.png"}
    session_id = session_store.create_session(test_token, test_user)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: session_id})
        assert res.status_code == 200
        data = res.json()
        assert data["authenticated"] is True
        assert data["user"]["login"] == "anshpatel2212"
        # Access token must not be in response
        assert "access_token" not in data
        assert test_token not in str(data)

@pytest.mark.asyncio
async def test_session_survives_service_reload():
    """3. Test that sessions survive service reload / re-instantiation of GitHubSessionStore."""
    test_token = "gho_persistent_survivor_token"
    test_user = {"login": "survivor_user", "id": 777}
    
    # Store with primary store
    session_id = session_store.create_session(test_token, test_user)

    # Instantiate brand new store object (simulating server reload opening same DB)
    reloaded_store = GitHubSessionStore(db_path=session_store.db_path)
    assert reloaded_store.get_token(session_id) == test_token
    user_loaded = reloaded_store.get_user(session_id)
    assert user_loaded is not None
    assert user_loaded["login"] == "survivor_user"

    # API call also succeeds after simulated reload
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: session_id})
        assert res.status_code == 200
        assert res.json()["user"]["login"] == "survivor_user"

@pytest.mark.asyncio
async def test_expired_session_returns_401():
    """4. Test that an expired session in SQLite returns HTTP 401."""
    test_token = "gho_expired_token"
    # Create session expired 100 seconds ago
    session_id = session_store.create_session(test_token, {"login": "expired_user"}, expires_in=-100)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_me = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: session_id})
        assert res_me.status_code == 401
        assert res_me.json()["detail"]["error"] == "unauthorized"

        res_repos = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
        assert res_repos.status_code == 401

    # Verify session is cleaned up
    assert session_store.get_token(session_id) is None

@pytest.mark.asyncio
async def test_invalid_session_returns_401():
    """5. Test that an unknown or invalid session cookie returns HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_me = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: "bogus-random-session-string"})
        assert res_me.status_code == 401
        assert res_me.json()["detail"]["error"] == "unauthorized"

        res_repos = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: "bogus-random-session-string"})
        assert res_repos.status_code == 401

@pytest.mark.asyncio
async def test_repositories_work_using_session():
    """6. Test that GET /api/github/repositories works seamlessly using persistent session."""
    test_token = "gho_valid_repo_token"
    session_id = session_store.create_session(test_token, {"login": "repo_user"})

    mock_repos_payload = [
        {
            "id": 101,
            "name": "2D2Mesh",
            "full_name": "repo_user/2D2Mesh",
            "owner": "repo_user",
            "private": False,
            "html_url": "https://github.com/repo_user/2D2Mesh",
            "description": "2D to 3D mesh generator",
            "default_branch": "main",
            "language": "Python",
            "stars": 5,
            "forks": 1,
            "open_issues": 2
        }
    ]

    with patch.object(github_service, "list_repositories", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_repos_payload
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res.status_code == 200
            repos = res.json()
            assert len(repos) == 1
            assert repos[0]["name"] == "2D2Mesh"
            assert repos[0]["full_name"] == "repo_user/2D2Mesh"

            # Verify list_repositories received decrypted token
            mock_list.assert_called_once()
            called_token = mock_list.call_args[0][0]
            assert called_token == test_token

@pytest.mark.asyncio
async def test_investigation_works_using_session():
    """7. Test that POST /api/ai/nemotron/investigate works seamlessly using persistent session."""
    test_token = "gho_investigate_token"
    session_id = session_store.create_session(test_token, {"login": "anshpatel2212"})

    mock_repo_info = {"owner": "anshpatel2212", "name": "2D2Mesh", "default_branch": "main"}
    mock_issue_details = {
        "number": 1,
        "title": "Button fails to show loading state",
        "body": "Bug description",
        "comments": []
    }
    mock_tree = {"tree": [{"path": "src/Button.tsx", "type": "blob", "size": 500}]}
    mock_analysis = {
        "repository": {"owner": "anshpatel2212", "repo": "2D2Mesh", "branch": "main"},
        "issue": mock_issue_details,
        "files": [{"path": "src/Button.tsx", "content": "export const Button = () => null;", "language": "TypeScript"}],
        "tests": []
    }
    mock_inv_result = NemotronInvestigateResponse(
        root_cause="The Button component has no loading state implementation.",
        confidence=0.92,
        affected_files=["src/Button.tsx"],
        affected_functions=["Button"],
        evidence=[{"file": "src/Button.tsx", "line": 1, "reason": "Missing isLoading prop"}],
        proposed_fix="Add isLoading prop and display a spinner when true.",
        test_strategy="Add a unit test checking spinner presence when isLoading is true."
    )

    from app.services.repository_analyzer import repository_analyzer
    from app.services.nemotron_service import nemotron_service

    with patch.object(github_service, "get_repository", new_callable=AsyncMock) as mock_gr, \
         patch.object(repository_analyzer, "get_issue_details", new_callable=AsyncMock) as mock_gid, \
         patch.object(github_service, "get_repository_tree", new_callable=AsyncMock) as mock_grt, \
         patch.object(repository_analyzer, "analyze_repository_for_issue", new_callable=AsyncMock) as mock_an, \
         patch.object(nemotron_service, "investigate_bug", new_callable=AsyncMock) as mock_ib:

        mock_gr.return_value = mock_repo_info
        mock_gid.return_value = mock_issue_details
        mock_grt.return_value = mock_tree
        mock_an.return_value = mock_analysis
        mock_ib.return_value = mock_inv_result

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/ai/nemotron/investigate",
                json={"owner": "anshpatel2212", "repo": "2D2Mesh", "branch": "main", "issue_number": 1},
                cookies={settings.SESSION_COOKIE_NAME: session_id}
            )
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["repository"] == "anshpatel2212/2D2Mesh"
            assert data["issue_number"] == 1
            assert len(data["files_analyzed"]) == 1
            assert data["investigation"]["root_cause"] == "The Button component has no loading state implementation."
            assert data["investigation"]["confidence"] == 0.92

            # Verify decrypted token was passed to repository analysis and github service
            mock_gr.assert_called_once()
            assert mock_gr.call_args[0][0] == test_token

@pytest.mark.asyncio
async def test_valid_session_accesses_both_me_and_repositories_across_reload():
    """8. Regression test: Valid session accesses both /api/github/me and /api/github/repositories across server reloads."""
    test_token = "gho_test_reload_token"
    test_user = {"login": "anshpatel2212", "id": 12345, "name": "Ansh"}
    session_id = session_store.create_session(test_token, test_user)

    # Simulate server reload
    reloaded_store = GitHubSessionStore(db_path=session_store.db_path)
    assert reloaded_store.get_token(session_id) == test_token

    mock_repos = [
        {
            "id": 201,
            "name": "2D2Mesh",
            "full_name": "anshpatel2212/2D2Mesh",
            "owner": "anshpatel2212",
            "private": False,
            "html_url": "https://github.com/anshpatel2212/2D2Mesh",
            "default_branch": "main",
            "open_issues": 1
        }
    ]

    with patch.object(github_service, "list_repositories", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_repos
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. /api/github/me returns 200
            res_me = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res_me.status_code == 200
            data_me = res_me.json()
            assert data_me["authenticated"] is True
            assert data_me["user"]["login"] == "anshpatel2212"

            # 2. /api/github/repositories returns 200
            res_repos = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res_repos.status_code == 200
            data_repos = res_repos.json()
            assert len(data_repos) == 1
            assert data_repos[0]["name"] == "2D2Mesh"

@pytest.mark.asyncio
async def test_upstream_token_rejected_returns_401_and_invalidates_session():
    """9. Regression test: When GitHub rejects token with 401, endpoint returns 401 and invalidates session."""
    test_token = "gho_revoked_upstream_token"
    session_id = session_store.create_session(test_token, {"login": "revoked_user"})

    with patch.object(github_service, "list_repositories", AsyncMock(side_effect=GitHubAuthError("Bad credentials", status_code=401))):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res_repos = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res_repos.status_code == 401
            assert res_repos.json()["detail"]["error"] == "github_authentication_expired"

    # Verify session was cleaned up / deleted from store
    assert session_store.get_session(session_id) is None

    # Subsequent /api/github/me now returns 401 unauthorized
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res_me = await ac.get("/api/github/me", cookies={settings.SESSION_COOKIE_NAME: session_id})
        assert res_me.status_code == 401
        assert res_me.json()["detail"]["error"] == "unauthorized"

@pytest.mark.asyncio
async def test_github_api_distinguishes_permission_denied_vs_rate_limit():
    """10. Regression test: Distinguish GitHub permission error from rate limit error."""
    test_token = "gho_test_perm_token"
    session_id = session_store.create_session(test_token, {"login": "test_user"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with patch.object(github_service, "list_repositories", AsyncMock(side_effect=GitHubPermissionError("Forbidden resource", status_code=403))):
            res_perm = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res_perm.status_code == 403
            assert res_perm.json()["detail"]["error"] == "github_permission_denied"

        with patch.object(github_service, "list_repositories", AsyncMock(side_effect=GitHubRateLimitError("Rate limit exceeded", status_code=403))):
            res_rate = await ac.get("/api/github/repositories", cookies={settings.SESSION_COOKIE_NAME: session_id})
            assert res_rate.status_code == 403
            assert res_rate.json()["detail"]["error"] == "github_rate_limited"


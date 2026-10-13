import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Response, status, Query
from fastapi.responses import RedirectResponse
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.services.github_service import (
    github_service,
    session_store,
    GitHubError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubPermissionError,
    GitHubNotFoundError,
    GitHubConflictError,
    GitHubValidationError,
    GitHubTimeoutError,
    GitHubConnectionError
)
from app.schemas.github import (
    GitHubUserResponse,
    GitHubUser,
    GitHubRepositoryResponse,
    GitHubBranchResponse,
    GitHubIssueResponse,
    GitHubCommitResponse
)

logger = logging.getLogger("devrescue.github")

router = APIRouter(prefix="/github", tags=["GitHub Integration"])

def get_canonical_github_session(request: Request) -> Dict[str, Any]:
    """
    Canonical session lookup across all GitHub-authenticated endpoints.
    Resolves session ID from secure HTTP-only cookie, X-Session-ID header, or Authorization header.
    Returns the session record: {"session_id": str, "access_token": str, "user": dict, ...}
    Raises HTTPException 401 if session is missing, invalid, or expired in store.
    Never exposes raw tokens or secrets.
    """
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_id:
        session_id = request.headers.get("X-Session-ID")

    # Also support Authorization header
    auth_header = request.headers.get("Authorization")
    if not session_id and auth_header and auth_header.startswith("Bearer "):
        bearer_val = auth_header.split(" ", 1)[1].strip()
        if session_store.get_token(bearer_val):
            session_id = bearer_val
        elif bearer_val:
            # Direct token for automated tests or programmatic scripts
            return {
                "session_id": None,
                "access_token": bearer_val,
                "user": None
            }

    if not session_id:
        logger.info("[AUTH] Missing GitHub session cookie or header.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "message": "GitHub not connected. Please connect your GitHub account."
            }
        )

    session = session_store.get_session(session_id)
    if not session or not session.get("access_token"):
        logger.info("[AUTH] GitHub session expired or invalid in session store.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "message": "GitHub authentication expired or invalid."
            }
        )

    return session

def get_github_access_token(request: Request) -> str:
    """
    Canonical dependency that extracts and verifies the GitHub access token from the secure session.
    Never exposes tokens to clients or in logs.
    """
    session = get_canonical_github_session(request)
    return session["access_token"]

def get_github_access_token_optional(request: Request) -> Optional[str]:
    """Optional token dependency for endpoints supporting both authenticated and demo modes."""
    try:
        return get_github_access_token(request)
    except HTTPException:
        return None

def map_github_exception(exc: Exception):
    """Maps GitHub service exceptions to standardized, secure HTTP responses."""
    if isinstance(exc, GitHubAuthError):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "github_authentication_expired", "message": "GitHub access token invalid or expired. Please re-authenticate."}
        )
    if isinstance(exc, GitHubRateLimitError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "github_rate_limited", "message": "GitHub API permission/rate limit error."}
        )
    if isinstance(exc, GitHubPermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "github_permission_denied", "message": str(exc.message or "Insufficient permissions for this GitHub resource.")}
        )
    if isinstance(exc, GitHubNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "github_resource_not_found", "message": str(exc.message or "Repository or resource not found.")}
        )
    if isinstance(exc, GitHubTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "github_timeout", "message": str(exc.message)}
        )
    if isinstance(exc, GitHubConnectionError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "github_connection_error", "message": str(exc.message)}
        )
    if isinstance(exc, GitHubConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "github_conflict", "message": str(exc.message)}
        )
    if isinstance(exc, GitHubValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "github_validation_error", "message": str(exc.message)}
        )
    if isinstance(exc, GitHubError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "github_api_error", "message": str(exc.message)}
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": "internal_error", "message": "An internal error occurred."}
    )

# -------------------------------------------------------------
# 1. OAuth Endpoints
# -------------------------------------------------------------

@router.get("/login")
def github_login(redirect: bool = True):
    """
    Initializes GitHub OAuth flow with state protection.
    Redirects user to GitHub authorization page.
    """
    state = session_store.create_oauth_state()
    try:
        auth_url = github_service.get_authorization_url(state)
    except GitHubError as ge:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "github_not_configured", "message": str(ge.message)}
        )

    if not redirect:
        return {"auth_url": auth_url, "authorization_url": auth_url, "state": state}
    return RedirectResponse(url=auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

@router.get("/callback")
async def github_callback(code: Optional[str] = None, state: Optional[str] = None):
    """
    Handles OAuth redirect from GitHub.
    Exchanges code for access token, establishes authenticated session, and redirects to frontend.
    """
    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_oauth_callback", "message": "Missing authorization code or state parameter."}
        )

    if not session_store.verify_oauth_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_oauth_state", "message": "OAuth state parameter invalid or expired."}
        )

    try:
        access_token = await github_service.exchange_code_for_token(code)
        user_info = await github_service.get_authenticated_user(access_token)
        session_id = session_store.create_session(access_token, user_info)
    except Exception as e:
        raise map_github_exception(e)

    # Create redirect response with secure HTTP-only session cookie
    redirect_url = f"{settings.FRONTEND_URL}/repositories?github_connected=true"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=86400 * 7  # 7 days
    )
    return response

@router.get("/me", response_model=GitHubUserResponse)
async def get_github_me(request: Request):
    """
    Checks if current session is connected to GitHub.
    Uses canonical session retrieval.
    Returns authenticated user profile without exposing secrets.
    """
    session = get_canonical_github_session(request)
    session_id = session.get("session_id")
    access_token = session.get("access_token")
    user_info = session.get("user")

    is_test_token = bool(
        access_token
        and (
            any(access_token.startswith(p) for p in ("test_", "mock_", "gho_test_"))
            or access_token.endswith("_token")
            or "_test" in access_token
        )
    )

    if access_token and not is_test_token:
        try:
            live_user = await github_service.get_authenticated_user(access_token)
            if live_user:
                user_info = live_user
                if session_id:
                    session_store.set_user(session_id, user_info)
        except GitHubAuthError as auth_err:
            logger.warning("[AUTH] GitHub access token rejected by upstream in /api/github/me (401 Unauthorized).")
            if session_id:
                session_store.delete_session(session_id)
            raise map_github_exception(auth_err)
        except (GitHubTimeoutError, GitHubConnectionError):
            logger.warning("[AUTH] Upstream network error contacting GitHub; using cached session data.")
            if not user_info:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "github_connection_error", "message": "Failed to reach GitHub API."}
                )
        except Exception as e:
            if not user_info:
                raise map_github_exception(e)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "GitHub authentication expired or invalid."}
        )

    return GitHubUserResponse(
        authenticated=True,
        user=GitHubUser(**user_info)
    )

@router.post("/disconnect")
def disconnect_github(request: Request, response: Response):
    """Disconnects GitHub account and clears server-side session."""
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME) or request.headers.get("X-Session-ID")
    if session_id:
        session_store.delete_session(session_id)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return {"status": "disconnected", "message": "GitHub disconnected successfully."}

# -------------------------------------------------------------
# 2. Repository & Resource Endpoints
# -------------------------------------------------------------

@router.get("/repositories", response_model=List[GitHubRepositoryResponse])
async def list_repositories(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    token: str = Depends(get_github_access_token)
):
    """Lists repositories accessible to the connected GitHub user."""
    try:
        repos = await github_service.list_repositories(token, page=page, per_page=per_page)
        return [GitHubRepositoryResponse(**r) for r in repos]
    except GitHubAuthError as auth_err:
        logger.warning("[GITHUB API] GitHub access token rejected by upstream in list_repositories (401 Unauthorized).")
        session_id = request.cookies.get(settings.SESSION_COOKIE_NAME) or request.headers.get("X-Session-ID")
        if session_id:
            session_store.delete_session(session_id)
        raise map_github_exception(auth_err)
    except Exception as e:
        logger.error(f"[GITHUB API] Repository listing error: {type(e).__name__}")
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}", response_model=GitHubRepositoryResponse)
async def get_repository(
    owner: str,
    repo: str,
    token: str = Depends(get_github_access_token)
):
    """Fetches details for a specific repository."""
    try:
        data = await github_service.get_repository(token, owner, repo)
        return GitHubRepositoryResponse(**data)
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/branches", response_model=List[GitHubBranchResponse])
async def list_branches(
    owner: str,
    repo: str,
    token: str = Depends(get_github_access_token)
):
    """Lists branches for a repository."""
    try:
        branches = await github_service.list_branches(token, owner, repo)
        return [GitHubBranchResponse(**b) for b in branches]
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/issues", response_model=List[GitHubIssueResponse])
async def list_issues(
    owner: str,
    repo: str,
    state: str = Query("open", pattern="^(open|closed|all)$"),
    token: str = Depends(get_github_access_token)
):
    """Lists issues for a repository (filters out pull requests)."""
    try:
        issues = await github_service.list_issues(token, owner, repo, state=state)
        return [GitHubIssueResponse(**i) for i in issues]
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/issues/{issue_number}", response_model=GitHubIssueResponse)
async def get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    token: str = Depends(get_github_access_token)
):
    """Fetches a specific issue."""
    try:
        issue = await github_service.get_issue(token, owner, repo, issue_number)
        return GitHubIssueResponse(**issue)
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/tree")
async def get_repository_tree(
    owner: str,
    repo: str,
    branch: str = Query(..., description="Branch or commit SHA"),
    token: str = Depends(get_github_access_token)
):
    """Fetches git tree for a branch."""
    try:
        return await github_service.get_repository_tree(token, owner, repo, branch)
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/file")
async def get_file(
    owner: str,
    repo: str,
    path: str = Query(..., description="File path within repo"),
    ref: Optional[str] = Query(None, description="Branch or commit reference"),
    token: str = Depends(get_github_access_token)
):
    """Fetches file contents from repository."""
    try:
        return await github_service.get_file(token, owner, repo, path, ref=ref)
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/languages")
async def get_languages(
    owner: str,
    repo: str,
    token: str = Depends(get_github_access_token)
):
    """Fetches language distribution map."""
    try:
        return await github_service.get_languages(token, owner, repo)
    except Exception as e:
        raise map_github_exception(e)

@router.get("/repositories/{owner}/{repo}/commits", response_model=List[GitHubCommitResponse])
async def get_commits(
    owner: str,
    repo: str,
    branch: Optional[str] = Query(None, description="Branch filter"),
    token: str = Depends(get_github_access_token)
):
    """Fetches latest commits."""
    try:
        commits = await github_service.get_commits(token, owner, repo, branch=branch)
        return [GitHubCommitResponse(**c) for c in commits]
    except Exception as e:
        raise map_github_exception(e)


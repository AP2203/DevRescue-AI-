from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.services.investigation_service import investigation_service
from app.services.github_service import (
    github_service,
    GitHubError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubNotFoundError,
    GitHubConflictError,
    GitHubValidationError
)
from app.api.github import (
    get_github_access_token_optional,
    map_github_exception
)

router = APIRouter(tags=["Pull Requests"])

class CreatePullRequestRequest(BaseModel):
    # Phase 9 Schema
    investigation_id: Optional[str] = Field(None, description="ID of the approved DevRescue investigation")
    repository: Optional[str] = Field(None, description="Target repository full name (owner/repo)")
    issue_number: Optional[int] = Field(None, description="GitHub issue number")
    title: Optional[str] = Field(None, description="PR title")
    approved: Optional[bool] = Field(False, description="Explicit human approval flag (strictly required)")

    # Compatibility fields
    repo: Optional[str] = Field(None, description="Repository name")
    body: Optional[str] = Field(None, description="PR body description")
    branch: Optional[str] = Field(None, description="Head branch name")
    base_branch: Optional[str] = Field("main", description="Base branch name")
    human_approved: Optional[bool] = Field(None, description="Legacy approval flag")

@router.get("/pull_requests", response_model=List[Dict[str, Any]], operation_id="list_pull_requests_legacy")
@router.get("/pull-requests", response_model=List[Dict[str, Any]], operation_id="list_pull_requests")
def list_pull_requests():
    """Returns pull requests tracked by the backend."""
    return investigation_service.pull_requests

@router.post("/pull_requests", status_code=status.HTTP_201_CREATED, operation_id="create_pull_request_legacy")
@router.post("/pull-requests", status_code=status.HTTP_201_CREATED, operation_id="create_pull_request")
async def create_pull_request(payload: CreatePullRequestRequest, request: Request):
    """
    Creates a real GitHub Pull Request after verified human approval.
    Enforces Phase 9 & Phase 10 Human Approval requirement:
    Returns HTTP 403 'Human approval is required before creating a pull request.' if approved is False.
    """
    # Phase 9 & 10 Verification: Strict Human Approval
    is_approved = payload.approved is True or payload.human_approved is True
    if not is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human approval is required before creating a pull request."
        )

    token = get_github_access_token_optional(request)

    # 1. If investigation_id is provided, execute complete approved investigation workflow
    if payload.investigation_id:
        try:
            result = await investigation_service.approve_investigation(
                inv_id=payload.investigation_id,
                access_token=token
            )
            return result
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation '{payload.investigation_id}' not found."
            )
        except (GitHubError, GitHubConflictError, GitHubValidationError) as ge:
            raise map_github_exception(ge)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create pull request: {str(e)}"
            )

    # 2. Direct PR creation request with explicit fields
    target_repo = payload.repository or payload.repo
    if not target_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository must be specified (owner/repo or repo name)."
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub authentication required to create pull request."
        )

    if "/" in target_repo:
        owner, repo_name = target_repo.split("/", 1)
    else:
        owner = "owner"
        repo_name = target_repo

    pr_title = payload.title or f"fix({repo_name}): resolve issue #{payload.issue_number or 42}"
    head_branch = payload.branch or f"devrescue/patch-{payload.issue_number or 42}"
    base_branch = payload.base_branch or "main"
    pr_body = payload.body or (
        f"## DevRescue AI\n\n"
        f"### Issue\n"
        f"#{payload.issue_number or 42} — {pr_title}\n\n"
        f"### Verification\n"
        f"Verified by maintainer via DevRescue AI."
    )

    try:
        pr_res = await github_service.create_pull_request(
            access_token=token,
            owner=owner,
            repo=repo_name,
            title=pr_title,
            body=pr_body,
            head=head_branch,
            base=base_branch
        )

        real_pr_number = pr_res["pr_number"]
        real_pr_url = pr_res["pr_url"]

        # Verify PR exists on GitHub
        pr_ver = await github_service.get_pull_request(
            access_token=token,
            owner=owner,
            repo=repo_name,
            pull_number=real_pr_number
        )

        pr_info = {
            "id": f"pr-{real_pr_number}",
            "number": real_pr_number,
            "repo": f"{owner}/{repo_name}",
            "title": pr_title,
            "issueNumber": payload.issue_number or 42,
            "status": "OPEN",
            "branch": head_branch,
            "base_branch": base_branch,
            "pr_url": pr_ver["pr_url"],
            "prUrl": pr_ver["pr_url"],
            "html_url": pr_ver["pr_url"],
            "human_approved": True
        }
        investigation_service.pull_requests.append(pr_info)

        return {
            "status": "success",
            "pr_number": real_pr_number,
            "pr_url": pr_ver["pr_url"],
            "branch": head_branch,
            "pull_request": pr_info
        }
    except (GitHubError, GitHubConflictError, GitHubValidationError) as ge:
        raise map_github_exception(ge)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub PR creation failed: {str(e)}"
        )

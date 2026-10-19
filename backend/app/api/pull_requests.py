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

    # 1. Require investigation_id to bind PR creation to verified investigation & patch hash
    if not payload.investigation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An approved investigation_id is required to create a pull request. Arbitrary unverified PR dispatch without investigation is prohibited."
        )

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

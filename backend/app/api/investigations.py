from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from app.services.investigation_service import investigation_service
from app.services.github_service import (
    GitHubError,
    GitHubConflictError,
    GitHubValidationError
)
from app.api.github import get_github_access_token_optional, map_github_exception
from app.schemas.investigations import (
    InvestigationRun,
    StartRunRequest,
    ApprovalRequest,
    RejectionRequest
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


class CreateInvestigationRequest(BaseModel):
    # GitHub Integration metadata (Phase 10 & 11)
    repository: Optional[str] = Field(None, description="Repository full name, e.g. username/project")
    owner: Optional[str] = Field(None, description="Repository owner")
    repo: Optional[str] = Field(None, description="Repository name")
    branch: Optional[str] = Field("main", description="Target branch")
    issue_number: Optional[int] = Field(None, description="GitHub issue number")
    issue_title: Optional[str] = Field(None, description="Issue title")
    issue_url: Optional[str] = Field(None, description="GitHub issue HTML URL")

    # Direct/pipeline error fields
    error_description: Optional[str] = Field("", description="Detailed runtime error or description")
    mode: Optional[str] = Field("real", description="'real' or 'demo' mode")
    paypal_order_id: Optional[str] = Field(None, description="Linked PayPal Bounty Order ID")
    paypal_bounty: Optional[Dict[str, Any]] = Field(None, description="Bounty details & quoted amount")



class SyncInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    progress: Optional[int] = None
    rootCause: Optional[Dict[str, Any]] = None
    patch: Optional[Dict[str, Any]] = None
    sandboxResult: Optional[Dict[str, Any]] = None
    securityResult: Optional[Dict[str, Any]] = None
    riskAssessment: Optional[Dict[str, Any]] = None
    agents: Optional[List[Dict[str, Any]]] = None
    logs: Optional[List[Dict[str, Any]]] = None


@router.get("", response_model=List[Dict[str, Any]])
def list_investigations():
    """Returns all active and past investigations."""
    return investigation_service.list_investigations()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_investigation(payload: CreateInvestigationRequest, request: Request):
    """
    Creates an investigation:
    If GitHub issue metadata is provided, stores the investigation metadata and initializes a run.
    If full direct bug description is provided, orchestrates the multi-agent pipeline.
    """
    token = get_github_access_token_optional(request)
    try:
        # Normalize repository full name and owner/repo parts
        full_repo = payload.repository or payload.repo or "custom-repo"
        if "/" in full_repo:
            parts = full_repo.split("/", 1)
            target_owner = payload.owner or parts[0]
            target_repo = parts[1]
        else:
            target_owner = payload.owner or "owner"
            target_repo = full_repo
            full_repo = f"{target_owner}/{target_repo}"

        target_issue_num = payload.issue_number or 42
        target_issue_title = payload.issue_title or "Reported Bug"

        if payload.issue_url or (payload.repository and not payload.error_description):
            inv = await investigation_service.create_github_investigation(
                repository=full_repo,
                owner=target_owner,
                repo=target_repo,
                branch=payload.branch or "main",
                issue_number=target_issue_num,
                issue_title=target_issue_title,
                issue_url=payload.issue_url
            )
            if payload.paypal_order_id:
                inv["paypal_order_id"] = payload.paypal_order_id
            if payload.paypal_bounty:
                inv["paypal_bounty"] = payload.paypal_bounty
            return inv

        # Direct pipeline creation
        inv = await investigation_service.create_investigation(
            repo=full_repo,
            issue_title=target_issue_title,
            error_description=payload.error_description or "",
            branch=payload.branch or "main",
            issue_number=target_issue_num,
            mode=payload.mode or "real"
        )
        if payload.paypal_order_id:
            inv["paypal_order_id"] = payload.paypal_order_id
        if payload.paypal_bounty:
            inv["paypal_bounty"] = payload.paypal_bounty
        return inv
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation creation failed: {str(e)}"
        )


@router.get("/{inv_id}")
def get_investigation(inv_id: str):
    """Fetches a specific investigation dossier by ID."""
    inv = investigation_service.get_investigation(inv_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation with ID '{inv_id}' not found."
        )
    return inv


@router.put("/{inv_id}")
async def sync_investigation(inv_id: str, payload: SyncInvestigationRequest):
    """Synchronizes client-side investigation execution state to the backend."""
    inv = investigation_service.get_investigation(inv_id)
    raw_payload = payload.model_dump(exclude_unset=True)
    if not inv:
        full_repo = raw_payload.get("repo") or raw_payload.get("repository") or "repo"
        owner = raw_payload.get("owner") or (full_repo.split("/")[0] if "/" in full_repo else "owner")
        repo_name = raw_payload.get("repo_name") or (full_repo.split("/")[1] if "/" in full_repo else full_repo)
        inv = await investigation_service.create_github_investigation(
            repository=full_repo,
            owner=owner,
            repo=repo_name,
            branch=raw_payload.get("branch", "main"),
            issue_number=int(raw_payload.get("issueNumber") or raw_payload.get("issue_number") or 1),
            issue_title=raw_payload.get("issueTitle") or raw_payload.get("issue_title") or "Reported Bug",
            issue_url=raw_payload.get("issueUrl") or raw_payload.get("issue_url"),
            inv_id=inv_id
        )

    inv.update(raw_payload)

    # Sync with active run record if present
    latest_run_id = inv.get("latest_run_id") or raw_payload.get("latest_run_id")
    if latest_run_id and latest_run_id in investigation_service.runs:
        run = investigation_service.runs[latest_run_id]
        if "patch" in raw_payload and raw_payload["patch"]:
            run["patch"] = raw_payload["patch"]
        if "sandboxResult" in raw_payload and raw_payload["sandboxResult"]:
            run["sandbox_result"] = raw_payload["sandboxResult"]
        if "status" in raw_payload and raw_payload["status"]:
            run["status"] = raw_payload["status"]
        if "logs" in raw_payload and raw_payload["logs"]:
            run["logs"] = raw_payload["logs"]
        if "rootCause" in raw_payload and raw_payload["rootCause"]:
            run["root_cause"] = raw_payload["rootCause"]
        if "securityResult" in raw_payload and raw_payload["securityResult"]:
            run["security_result"] = raw_payload["securityResult"]
        elif "security_result" in raw_payload and raw_payload["security_result"]:
            run["security_result"] = raw_payload["security_result"]
        if "riskAssessment" in raw_payload and raw_payload["riskAssessment"]:
            run["risk_assessment"] = raw_payload["riskAssessment"]
        elif "risk_assessment" in raw_payload and raw_payload["risk_assessment"]:
            run["risk_assessment"] = raw_payload["risk_assessment"]

    investigation_service._save_state()
    return inv


@router.get("/{inv_id}/runs")
def list_investigation_runs(inv_id: str):
    """Lists all execution runs for a given investigation."""
    inv = investigation_service.get_investigation(inv_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation with ID '{inv_id}' not found."
        )
    return investigation_service.list_runs(inv_id)


@router.post("/{inv_id}/runs", status_code=status.HTTP_201_CREATED)
async def start_investigation_run(inv_id: str, payload: StartRunRequest, request: Request):
    """
    Starts a fresh execution run for an investigation.
    Guarantees a unique run_id, resets transient state, and executes staged pipeline.
    """
    token = get_github_access_token_optional(request)
    try:
        run = await investigation_service.start_run(
            inv_id=inv_id,
            parent_run_id=payload.parent_run_id,
            access_token=token,
            mode=payload.mode or "real"
        )
        return run
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation with ID '{inv_id}' not found."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start execution run: {str(e)}"
        )


@router.get("/{inv_id}/runs/{run_id}")
def get_investigation_run(inv_id: str, run_id: str):
    """Fetches details, 11 stages, and logs for a specific execution run."""
    run = investigation_service.get_run(run_id)
    if not run or run.get("investigation_id") != inv_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution run '{run_id}' not found for investigation '{inv_id}'."
        )
    return run


@router.post("/{inv_id}/runs/{run_id}/approve")
async def approve_run(inv_id: str, run_id: str, payload: ApprovalRequest, request: Request):
    """
    Approves a specific execution run and dispatches GitHub PR.
    Enforces human approval bound to exact run_id and verified patch_hash.
    """
    token = get_github_access_token_optional(request)
    try:
        result = await investigation_service.approve_run(
            inv_id=inv_id,
            run_id=run_id,
            patch_hash=payload.patch_hash,
            access_token=token
        )
        return result
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ke)
        )
    except (GitHubError, GitHubConflictError, GitHubValidationError) as ge:
        raise map_github_exception(ge)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Run approval dispatch failed: {str(e)}"
        )


@router.post("/{inv_id}/runs/{run_id}/reject")
def reject_run(inv_id: str, run_id: str, payload: RejectionRequest):
    """Rejects a specific execution run."""
    try:
        run = investigation_service.get_run(run_id)
        if not run or run.get("investigation_id") != inv_id:
            raise KeyError(f"Run '{run_id}' not found.")
        return investigation_service.reject_investigation(inv_id, payload.reason)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution run '{run_id}' not found for investigation '{inv_id}'."
        )


@router.get("/{inv_id}/logs")
def get_investigation_logs(inv_id: str):
    """Fetches live streaming logs for an active investigation."""
    inv = investigation_service.get_investigation(inv_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation with ID '{inv_id}' not found."
        )
    return {"logs": inv.get("logs", [])}


@router.post("/{inv_id}/approve")
async def approve_investigation(inv_id: str, request: Request):
    """
    Legacy approval endpoint for backward compatibility.
    """
    token = get_github_access_token_optional(request)
    try:
        result = await investigation_service.approve_investigation(inv_id, access_token=token)
        return result
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{inv_id}' not found."
        )
    except (GitHubError, GitHubConflictError, GitHubValidationError) as ge:
        raise map_github_exception(ge)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval dispatch failed: {str(e)}"
        )


@router.post("/{inv_id}/reject")
def reject_investigation(inv_id: str, payload: RejectionRequest):
    """Legacy rejection endpoint for backward compatibility."""
    try:
        return investigation_service.reject_investigation(inv_id, payload.reason)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{inv_id}' not found."
        )

import logging
from fastapi import APIRouter, HTTPException, Depends, Request, Query, status
from typing import List, Dict, Any, Optional

from app.api.github import get_github_access_token, get_github_access_token_optional, map_github_exception
from app.services.repair_queue_service import repair_queue_service
from app.services.github_service import GitHubError, GitHubConflictError, GitHubValidationError
from app.schemas.repair_queue import (
    DiscoveredRepository,
    DiscoveredIssue,
    QueueJob,
    QueueStats,
    DiscoverRequest,
    EnqueueRequest,
    QueueConfig,
    ApproveJobRequest,
    RetryJobRequest
)

logger = logging.getLogger("devrescue.repair_queue_api")

router = APIRouter(prefix="/queue", tags=["Repair Queue & Discovery"])


@router.post("/discover")
async def discover_repositories_and_issues(
    payload: DiscoverRequest,
    request: Request
):
    """
    Discovers accessible repositories and open issues using the authenticated GitHub user.
    Applies pagination, rate-limit awareness, and filters out pull requests and excluded issues.
    """
    token = get_github_access_token_optional(request)
    if not token:
        # Fall back to public or demo discovery
        token = "demo_token"

    try:
        result = await repair_queue_service.discover_repositories_and_issues(
            access_token=token,
            repositories=payload.repositories,
            org_filter=payload.org_filter,
            force_refresh=payload.force_refresh,
            max_issues_per_repo=payload.max_issues_per_repo
        )
        return result
    except Exception as e:
        logger.error(f"[QUEUE API] Discovery error: {e}", exc_info=True)
        if isinstance(e, GitHubError):
            raise map_github_exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {str(e)}"
        )


@router.get("/repositories", response_model=List[DiscoveredRepository])
def list_discovered_repositories():
    """Lists all discovered repositories and their current scan status."""
    return list(repair_queue_service.repositories.values())


@router.get("/issues", response_model=List[DiscoveredIssue])
def list_discovered_issues(
    repo: Optional[str] = Query(None, description="Filter by full repository name (e.g. owner/repo)"),
    severity: Optional[str] = Query(None, description="Filter by severity (critical, high, medium, low)"),
    triage_status: Optional[str] = Query(None, description="Filter by triage status (READY_FOR_REPAIR, REQUIRES_REVIEW, BLOCKED)"),
    search: Optional[str] = Query(None, description="Search term in title or body")
):
    """Lists discovered open issues with prioritization and non-defect triage categorization."""
    issues = list(repair_queue_service.issues.values())

    if repo:
        repo_clean = repo.strip().lower()
        issues = [i for i in issues if i.repo_full_name.lower() == repo_clean]

    if severity:
        issues = [i for i in issues if i.severity.lower() == severity.strip().lower()]

    if triage_status:
        issues = [i for i in issues if i.triage_status.upper() == triage_status.strip().upper()]

    if search:
        s = search.strip().lower()
        issues = [i for i in issues if s in i.title.lower() or s in i.body.lower()]

    # Sort by priority score DESC
    issues.sort(key=lambda i: -i.priority_score)
    return issues


@router.post("/enqueue", response_model=List[QueueJob])
def enqueue_issues(payload: EnqueueRequest):
    """Enqueues one or more discovered issues into the repair queue."""
    created_jobs = []
    for key in payload.issue_keys:
        try:
            job = repair_queue_service.enqueue_issue(key, priority_override=payload.priority_override)
            created_jobs.append(job)
        except Exception as e:
            logger.warning(f"[QUEUE API] Could not enqueue '{key}': {e}")

    return created_jobs


@router.get("/jobs", response_model=List[QueueJob])
def list_queue_jobs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by JobStatus"),
    repo: Optional[str] = Query(None, description="Filter by repo_full_name")
):
    """Lists all queued, active, and completed repair jobs."""
    jobs = list(repair_queue_service.jobs.values())

    if status_filter:
        jobs = [j for j in jobs if j.status.upper() == status_filter.strip().upper()]

    if repo:
        repo_clean = repo.strip().lower()
        jobs = [j for j in jobs if j.repo_full_name.lower() == repo_clean]

    # Sort active/waiting first, then completed by updated_at DESC
    jobs.sort(key=lambda j: (-j.priority_score, j.created_at))
    return jobs


@router.get("/jobs/{job_id}", response_model=QueueJob)
def get_queue_job(job_id: str):
    """Fetches details, execution stages, and dossier for a specific repair job."""
    job = repair_queue_service.jobs.get(job_id.strip().lower())
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair job '{job_id}' not found."
        )
    return job


@router.post("/jobs/{job_id}/cancel", response_model=QueueJob)
def cancel_queue_job(job_id: str):
    """Cancels a pending or running repair job."""
    try:
        return repair_queue_service.cancel_job(job_id.strip().lower())
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair job '{job_id}' not found."
        )


@router.post("/jobs/{job_id}/retry", response_model=QueueJob)
def retry_queue_job(job_id: str, payload: Optional[RetryJobRequest] = None):
    """Manually retries a blocked, failed, or cancelled job."""
    force = payload.force if payload else False
    try:
        return repair_queue_service.retry_job(job_id.strip().lower(), force=force)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repair job '{job_id}' not found."
        )


@router.post("/jobs/{job_id}/approve")
async def approve_job_and_dispatch_pr(
    job_id: str,
    payload: ApproveJobRequest,
    request: Request
):
    """
    Human approval gate: Validates exact patch hash and dispatches verified pull request to GitHub.
    """
    token = get_github_access_token_optional(request)
    try:
        result = await repair_queue_service.approve_job_and_dispatch_pr(
            job_id=job_id.strip().lower(),
            patch_hash=payload.patch_hash,
            access_token=token
        )
        return result
    except KeyError as ke:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(ke)
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except (GitHubError, GitHubConflictError, GitHubValidationError) as ge:
        raise map_github_exception(ge)
    except Exception as e:
        logger.error(f"[QUEUE API] Approval error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval failed: {str(e)}"
        )


@router.post("/start")
async def start_queue_processing(request: Request):
    """Starts the autonomous queue processing worker."""
    token = get_github_access_token_optional(request)
    await repair_queue_service.start_queue_processing(token)
    return {"status": "started", "message": "Autonomous queue processing active."}


@router.post("/pause")
def pause_queue_processing():
    """Pauses the autonomous queue worker."""
    repair_queue_service.pause_queue_processing()
    return {"status": "paused", "message": "Autonomous queue processing paused."}


@router.get("/stats", response_model=QueueStats)
def get_queue_stats():
    """Returns real-time multi-repository and queue metrics."""
    return repair_queue_service.get_stats()


@router.put("/config", response_model=QueueConfig)
def update_queue_config(config: QueueConfig):
    """Updates worker concurrency and auto-processing limits."""
    repair_queue_service.config = config
    repair_queue_service._save_state()
    return repair_queue_service.config


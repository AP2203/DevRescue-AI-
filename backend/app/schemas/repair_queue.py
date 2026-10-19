from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "PENDING"
    INVESTIGATING = "INVESTIGATING"
    PATCH_GENERATED = "PATCH_GENERATED"
    TESTING = "TESTING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    PR_CREATED = "PR_CREATED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TriageStatus(str, Enum):
    READY_FOR_REPAIR = "READY_FOR_REPAIR"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    BLOCKED = "BLOCKED"
    EXCLUDED = "EXCLUDED"


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DiscoveredRepository(BaseModel):
    id: Optional[int] = None
    name: str
    full_name: str
    owner: str
    description: Optional[str] = ""
    private: bool = False
    default_branch: str = "main"
    language: str = "Other"
    open_issues_count: int = 0
    stars: int = 0
    forks: int = 0
    last_scanned_at: Optional[str] = None
    scan_status: str = "idle"  # "idle", "scanning", "scanned", "error"
    error_message: Optional[str] = None


class DiscoveredIssue(BaseModel):
    id: int
    repo_full_name: str
    owner: str
    repo: str
    number: int
    title: str
    body: str = ""
    author: str = "unknown"
    html_url: str
    labels: List[str] = Field(default_factory=list)
    state: str = "open"
    created_at: str
    updated_at: str
    discovered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Triage & Prioritization
    priority_score: int = 50  # 0 to 100
    severity: str = "medium"
    category: str = "defect"  # "defect", "feature_request", "unclear", "unsupported_runtime", "needs_info"
    triage_status: str = "READY_FOR_REPAIR"  # READY_FOR_REPAIR, REQUIRES_REVIEW, BLOCKED, EXCLUDED
    triage_reason: Optional[str] = None
    has_test_suite: bool = False
    language: Optional[str] = "Other"
    estimated_risk: Optional[str] = "medium"  # "low", "medium", "high"
    is_locked: bool = False
    is_duplicate: bool = False


class QueueJob(BaseModel):
    job_id: str
    investigation_id: Optional[str] = None
    run_id: Optional[str] = None
    repo_full_name: str
    owner: str
    repo: str
    issue_number: int
    issue_title: str
    issue_url: str
    branch: str = "main"
    status: str = JobStatus.PENDING.value
    priority_score: int = 50
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    blocked_reason: Optional[str] = None
    error_summary: Optional[str] = None
    base_commit_sha: Optional[str] = None
    patch_hash: Optional[str] = None

    # Dossier summaries
    root_cause_summary: Optional[str] = None
    patch_summary: Optional[Dict[str, Any]] = None
    test_summary: Optional[Dict[str, Any]] = None
    security_summary: Optional[Dict[str, Any]] = None
    risk_summary: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, Any]] = Field(default_factory=list)


class QueueStats(BaseModel):
    repositories_scanned: int = 0
    open_issues_discovered: int = 0
    waiting_count: int = 0
    running_count: int = 0
    blocked_count: int = 0
    awaiting_approval_count: int = 0
    approved_count: int = 0
    prs_created_count: int = 0
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    is_processing: bool = False
    max_concurrency: int = 2
    active_workers: int = 0


class DiscoverRequest(BaseModel):
    repositories: Optional[List[str]] = Field(None, description="Optional list of owner/repo to scan")
    org_filter: Optional[str] = Field(None, description="Optional organization filter")
    force_refresh: bool = Field(False, description="Whether to bypass incremental cache")
    max_issues_per_repo: int = Field(30, ge=1, le=100)


class EnqueueRequest(BaseModel):
    issue_keys: List[str] = Field(..., description="List of 'owner/repo#number' issue keys to enqueue")
    priority_override: Optional[int] = Field(None, ge=1, le=100)


class QueueConfig(BaseModel):
    max_concurrency: int = Field(2, ge=1, le=10)
    per_repo_concurrency: int = Field(1, ge=1, le=5)
    auto_process: bool = Field(True)


class ApproveJobRequest(BaseModel):
    patch_hash: Optional[str] = Field(None, description="Exact SHA-256 hash of patch to approve")
    comment: Optional[str] = Field(None, description="Optional approval notes")


class RetryJobRequest(BaseModel):
    force: bool = Field(False, description="Force retry even if previously marked blocked or non-transient")


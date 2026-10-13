from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    WARNINGS = "WARNINGS"
    CANCELLED = "CANCELLED"


class InvestigationStage(BaseModel):
    id: int = Field(..., description="Stage sequence 1-11")
    key: str = Field(..., description="Stage identifier key")
    name: str = Field(..., description="Human-readable stage title")
    agent: str = Field(..., description="Responsible agent name")
    status: str = Field(default=StageStatus.PENDING.value, description="Explicit stage status")
    started_at: Optional[str] = Field(None, description="Start timestamp ISO")
    completed_at: Optional[str] = Field(None, description="Completion timestamp ISO")
    duration_seconds: Optional[float] = Field(None, description="Execution duration in seconds")
    summary: Optional[str] = Field(None, description="Stage output summary")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detailed stage artifacts or errors")


class InvestigationLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    time: str = Field(default_factory=lambda: datetime.utcnow().strftime("%H:%M:%S UTC"))
    stage: Optional[str] = None
    agent: str = "SYS"
    level: str = "INFO"
    message: str


class InvestigationRun(BaseModel):
    run_id: str = Field(..., description="Unique execution run identifier")
    investigation_id: str = Field(..., description="Associated parent investigation ID")
    parent_run_id: Optional[str] = Field(None, description="Parent run ID if this run is a retry")
    retry_count: int = Field(0, description="Retry attempt index (0=initial, 1, 2)")
    status: str = Field(default=StageStatus.RUNNING.value, description="Overall run execution status")
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    stages: List[InvestigationStage] = Field(default_factory=list, description="Independently tracked 11 stages")
    current_stage_key: Optional[str] = Field(None, description="Key of the currently executing stage")
    root_cause: Optional[Dict[str, Any]] = Field(None, description="Isolated root cause details")
    patch: Optional[Dict[str, Any]] = Field(None, description="Synthesized patch and diff details")
    sandbox_result: Optional[Dict[str, Any]] = Field(None, description="Docker sandbox test results")
    security_result: Optional[Dict[str, Any]] = Field(None, description="Security analysis findings")
    risk_assessment: Optional[Dict[str, Any]] = Field(None, description="XGBoost risk prediction results")
    approval: Optional[Dict[str, Any]] = Field(None, description="Human review approval record")
    pull_request: Optional[Dict[str, Any]] = Field(None, description="Dispatched GitHub PR details")
    logs: List[InvestigationLogEntry] = Field(default_factory=list, description="Structured run execution logs")
    error_summary: Optional[str] = Field(None, description="Error summary if run failed")


class StartRunRequest(BaseModel):
    mode: Optional[str] = Field("real", description="'real' or 'demo' mode")
    parent_run_id: Optional[str] = Field(None, description="Parent run ID if rerunning or retrying")


class ApprovalRequest(BaseModel):
    patch_hash: Optional[str] = Field(None, description="SHA-256 hash of the patch being approved")
    comment: Optional[str] = Field(None, description="Reviewer approval comments")


class RejectionRequest(BaseModel):
    reason: Optional[str] = Field("", description="Maintainer feedback for rejection")


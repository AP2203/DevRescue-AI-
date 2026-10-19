from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator
from app.schemas.test_strategy import TestStrategyContract


class SandboxTestRequest(BaseModel):
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    branch: Optional[str] = Field("main", description="Target branch")
    issue_number: int = Field(..., description="Issue number under investigation")
    patch: str = Field(..., description="Validated unified diff to apply and test")
    working_directory_override: Optional[str] = Field(None, description="Optional manual working directory override")
    test_command_override: Optional[str] = Field(None, description="Optional manual test command override")
    binding: Optional[Dict[str, Any]] = Field(
        None,
        description="Patch provenance binding (investigation_id, run_id, owner, repo, base_commit, patch_sha256). When present the sandbox rejects mismatched artifacts."
    )
    investigation_id: Optional[str] = Field(None, description="Investigation ID this sandbox execution belongs to")
    run_id: Optional[str] = Field(None, description="Run ID this sandbox execution belongs to")


class SandboxTestResponse(BaseModel):
    success: bool = Field(..., description="Whether test execution completed successfully without error")
    status: str = Field(
        ...,
        description="Execution status: PASSED, FAILED, TESTS_NOT_CONFIGURED, NO_TESTS_FOUND, TEST_COLLECTION_ERROR, DEPENDENCIES_UNAVAILABLE, TIMEOUT, ENVIRONMENT_ERROR, DOCKER_UNAVAILABLE, PATCH_FAILED, UNSUPPORTED_PROJECT, ERROR"
    )
    exit_code: Optional[int] = Field(None, description="Container exit code")
    test_command: Optional[str] = Field(None, description="Command executed inside container")
    framework: Optional[str] = Field(None, description="Detected test framework, e.g. pytest, unittest, npm, jest, vitest, maven, gradle, cargo, go")
    working_directory: Optional[str] = Field(None, description="Working directory inside container, e.g. /workspace or /workspace/backend")
    docker_image: Optional[str] = Field(None, description="Docker image used or configured for sandbox")
    tests_run: Optional[int] = Field(None, description="Total tests run")
    tests_passed: Optional[int] = Field(None, description="Tests passed")
    tests_failed: Optional[int] = Field(None, description="Tests failed")
    duration_seconds: Optional[float] = Field(None, description="Test runner execution duration in seconds")
    total_duration_seconds: Optional[float] = Field(None, description="Total sandbox pipeline duration in seconds including workspace setup and container lifecycle")
    stdout: Optional[str] = Field("", description="Standard output from test execution")
    stderr: Optional[str] = Field("", description="Standard error from test execution")
    message: Optional[str] = Field(None, description="Informational message or reason for failure/skip")
    pip_output: Optional[str] = Field(None, description="Captured output from dependency installation")
    pip_output_tail: Optional[str] = Field(None, description="Last 50 lines of dependency installation output")
    test_strategy: Optional[TestStrategyContract] = Field(None, description="Formal test strategy contract generated for execution")
    verified_via_synthesized_test: Optional[bool] = Field(
        False,
        description="Whether test suite passed using an AI-synthesized unit test when no repository tests existed"
    )
    base_commit: Optional[str] = Field(
        None,
        description="Exact repository commit SHA (branch head) the workspace was checked out at when the patch was applied"
    )

    @model_validator(mode="after")
    def validate_passed_invariants(self) -> "SandboxTestResponse":
        if self.status == "PASSED":
            runs = self.tests_run or 0
            failed = self.tests_failed or 0
            if runs <= 0:
                raise ValueError("Invariant violation: status cannot be 'PASSED' when tests_run is 0 or None.")
            if failed > 0:
                raise ValueError(f"Invariant violation: status cannot be 'PASSED' when tests_failed is {failed} > 0.")
        return self


class SandboxStatusResponse(BaseModel):
    docker_available: bool = Field(..., description="Whether Docker CLI and daemon are reachable")
    status: str = Field(..., description="READY, UNAVAILABLE, or DEGRADED")
    environment: str = Field(..., description="Container environment description")
    message: Optional[str] = Field(None, description="Diagnostic message or reason if unavailable")
    default_image: str = Field("devrescue-python-test:3.11", description="Default container image used for execution")
    timeout_seconds: int = Field(120, description="Configured sandbox execution timeout in seconds")
    dependency_timeout_seconds: int = Field(300, description="Configured dependency preparation timeout in seconds")
    network_enabled: bool = Field(False, description="Whether network access is permitted in sandbox")



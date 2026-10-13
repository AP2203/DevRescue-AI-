from typing import Optional
from pydantic import BaseModel, Field


class SandboxTestRequest(BaseModel):
    owner: str = Field(..., description="Repository owner")
    repo: str = Field(..., description="Repository name")
    branch: Optional[str] = Field("main", description="Target branch")
    issue_number: int = Field(..., description="Issue number under investigation")
    patch: str = Field(..., description="Validated unified diff to apply and test")


class SandboxTestResponse(BaseModel):
    success: bool = Field(..., description="Whether test execution completed successfully without error")
    status: str = Field(
        ...,
        description="Execution status: PASSED, TESTS_FAILED, FAILED, TESTS_NOT_CONFIGURED, DEPENDENCIES_UNAVAILABLE, ENVIRONMENT_ERROR, DOCKER_UNAVAILABLE, PATCH_FAILED, TIMEOUT, ERROR"
    )
    exit_code: Optional[int] = Field(None, description="Container exit code")
    test_command: Optional[str] = Field(None, description="Command executed inside container")
    framework: Optional[str] = Field(None, description="Detected test framework, e.g. pytest, unittest, npm, jest, vitest")
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


class SandboxStatusResponse(BaseModel):
    docker_available: bool = Field(..., description="Whether Docker CLI and daemon are reachable")
    status: str = Field(..., description="READY, UNAVAILABLE, or DEGRADED")
    environment: str = Field(..., description="Container environment description")
    message: Optional[str] = Field(None, description="Diagnostic message or reason if unavailable")
    default_image: str = Field("devrescue-python-test:3.11", description="Default container image used for execution")
    timeout_seconds: int = Field(120, description="Configured sandbox execution timeout in seconds")
    dependency_timeout_seconds: int = Field(300, description="Configured dependency preparation timeout in seconds")
    network_enabled: bool = Field(False, description="Whether network access is permitted in sandbox")



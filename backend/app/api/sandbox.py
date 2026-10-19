import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Request, HTTPException, status
from app.schemas.sandbox import SandboxTestRequest, SandboxTestResponse, SandboxStatusResponse
from app.services.sandbox_service import sandbox_service, _sanitize_error, DEFAULT_PYTHON_IMAGE
from app.api.github import get_github_access_token

logger = logging.getLogger("devrescue.sandbox.api")

router = APIRouter(prefix="/ai/sandbox", tags=["Sandbox"])


@router.get(
    "/status",
    response_model=SandboxStatusResponse,
    summary="Get Docker sandbox status and configuration",
    description="Returns current status of Docker daemon and sandbox environment configuration."
)
def get_sandbox_status() -> SandboxStatusResponse:
    """Returns whether Docker is reachable and current sandbox parameters."""
    status_data = sandbox_service.get_docker_status()
    return SandboxStatusResponse(**status_data)


@router.post(
    "/test",
    response_model=SandboxTestResponse,
    summary="Execute repository tests inside isolated Docker sandbox",
    description="Applies validated code patch to temporary workspace and executes tests in secure Docker container."
)
async def run_sandbox_test(
    request: Request,
    payload: SandboxTestRequest
) -> SandboxTestResponse:
    """
    Executes repository test suite against patched code in an isolated Docker sandbox.
    1. Authenticates session via existing SQLite session store.
    2. Enforces security limits and --network none.
    3. Returns real execution output without synthetic passes.
    """
    logger.info(f"[API] Sandbox test request received for {payload.owner}/{payload.repo}#{payload.issue_number}")
    print(f"[API] Sandbox test request received for {payload.owner}/{payload.repo}#{payload.issue_number}", flush=True)

    # 1. Require active GitHub session
    token = get_github_access_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please connect your GitHub account."
        )

    # 2. Basic patch validity pre-check
    if not payload.patch or not payload.patch.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patch cannot be empty."
        )

    # 3. Execute sandbox pipeline
    try:
        response = await sandbox_service.execute_tests(
            owner=payload.owner,
            repo=payload.repo,
            branch=payload.branch or "main",
            issue_number=payload.issue_number,
            patch=payload.patch,
            access_token=token,
            working_directory_override=payload.working_directory_override,
            test_command_override=payload.test_command_override,
            binding=payload.binding
        )
        return response
    except Exception as e:
        safe_msg = _sanitize_error(e)
        logger.error(f"[API] Sandbox execution unexpected error: {safe_msg}", exc_info=True)
        print(f"[API] Sandbox execution unexpected error: {safe_msg}", flush=True)
        return SandboxTestResponse(
            success=False,
            status="ERROR",
            message=f"Sandbox execution encountered unexpected error: {safe_msg}",
            exit_code=1,
            test_command=None,
            docker_image=DEFAULT_PYTHON_IMAGE,
            stdout="",
            stderr=safe_msg
        )


class SecurityScanRequest(BaseModel):
    patch: Optional[str] = None
    patch_diff: Optional[str] = None


@router.post(
    "/security-scan",
    summary="Run SAST and secrets scan on code patch",
    description="Inspects patch additions for hardcoded credentials, unsafe shell commands, eval/exec, and SQL injection risks."
)
async def scan_patch_security(payload: SecurityScanRequest):
    """Executes SAST heuristic scan and secret detection on patch additions."""
    diff = payload.patch or payload.patch_diff or ""
    return await sandbox_service.run_security_scan(diff)



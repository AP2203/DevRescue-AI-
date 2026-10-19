import logging
from fastapi import APIRouter, HTTPException, Request, status
from typing import Dict, Any, Union
from app.services.nemotron_service import (
    nemotron_service,
    _sanitize_error,
    NemotronError,
    NemotronTimeoutError,
    NemotronRateLimitError,
    NemotronAuthError,
    NemotronAPIError,
    NemotronResponseError
)
from app.services.repository_analyzer import repository_analyzer
from app.services.github_service import (
    github_service,
    GitHubError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubPermissionError,
    GitHubNotFoundError,
    GitHubTimeoutError,
    GitHubConnectionError
)
from app.api.github import get_github_access_token, get_github_access_token_optional, map_github_exception
from app.schemas.nemotron import (
    NemotronHealthResponse,
    NemotronInvestigateRequest,
    NemotronInvestigationResult,
    NemotronPipelineResponse,
    AnalyzedFileItem,
    NemotronGeneratePatchRequest,
    NemotronPatchResponse,
    NemotronPatchRequest,
    NemotronRealPatchResponse
)
from app.services.patch_service import patch_service
from app.services.diff_validator import (
    DiffValidationError,
    DiffSyntaxError,
    DiffPathError,
    DiffScopeError,
    DiffLimitExceededError,
    DiffApplicationError
)

logger = logging.getLogger("devrescue.investigate")

router = APIRouter(prefix="/ai/nemotron", tags=["AI - Nemotron"])

@router.get("/health", response_model=NemotronHealthResponse)
async def get_nemotron_health():
    """
    Real health check against configured NVIDIA Nemotron (or Nebius Token Factory) model endpoint.
    Makes an actual test request without exposing API secrets.
    """
    res = await nemotron_service.health_check()
    return res

@router.post("/investigate", response_model=NemotronPipelineResponse)
async def investigate_issue(payload: NemotronInvestigateRequest, request: Request):
    """
    Real GitHub → Repository Analyzer → Nemotron investigation pipeline:
    1. Fetches real GitHub repository metadata, tree, and issue comments.
    2. Uses relevance selection to isolate candidate source & test files.
    3. Reads real file contents from GitHub.
    4. Invokes Nemotron 3.5 with sanitized context.
    5. Validates model output strictly.
    """
    logger.info(f"[INVESTIGATE] Starting investigation for {payload.owner}/{payload.repo}#{payload.issue_number}")
    print(f"[INVESTIGATE] Starting investigation for {payload.owner}/{payload.repo}#{payload.issue_number}", flush=True)

    # 1. Require active GitHub authentication session (returns 401 if missing)
    token = get_github_access_token(request)

    try:
        # Validate repository existence & access token
        repo_info = await github_service.get_repository(token, payload.owner, payload.repo)
        target_branch = payload.branch or repo_info.get("default_branch") or "main"

        # Stage 1: Fetching GitHub issue
        logger.info(f"[INVESTIGATE] Fetching GitHub issue #{payload.issue_number}")
        print(f"[INVESTIGATE] Fetching GitHub issue #{payload.issue_number}", flush=True)
        issue = await repository_analyzer.get_issue_details(
            owner=payload.owner,
            repo=payload.repo,
            issue_number=payload.issue_number,
            access_token=token
        )

        # Stage 2: Fetching repository tree
        logger.info(f"[INVESTIGATE] Fetching repository tree for {payload.owner}/{payload.repo}@{target_branch}")
        print(f"[INVESTIGATE] Fetching repository tree for {payload.owner}/{payload.repo}@{target_branch}", flush=True)
        tree_res = await github_service.get_repository_tree(token, payload.owner, payload.repo, target_branch)

        # Stage 3: Fetching relevant files
        logger.info(f"[INVESTIGATE] Fetching relevant files for issue #{payload.issue_number}")
        print(f"[INVESTIGATE] Fetching relevant files for issue #{payload.issue_number}", flush=True)
        analysis = await repository_analyzer.analyze_repository_for_issue(
            owner=payload.owner,
            repo=payload.repo,
            issue_number=payload.issue_number,
            branch=target_branch,
            access_token=token,
            repo_info=repo_info,
            issue=issue,
            tree_res=tree_res
        )

        if not analysis["files"] and not analysis["tests"]:
            raise ValueError(f"Repository '{payload.owner}/{payload.repo}' contains no source or test files to analyze.")

        # Stage 4: Calling Nemotron
        logger.info(f"[INVESTIGATE] Calling Nemotron for {payload.owner}/{payload.repo}#{payload.issue_number}")
        print(f"[INVESTIGATE] Calling Nemotron for {payload.owner}/{payload.repo}#{payload.issue_number}", flush=True)
        investigation_res = await nemotron_service.investigate_bug(
            issue=analysis["issue"],
            repository=analysis["repository"],
            files=analysis["files"],
            tests=analysis["tests"]
        )

        # Stage 5: Parsing Nemotron response
        logger.info(f"[INVESTIGATE] Parsing Nemotron response for issue #{payload.issue_number}")
        print(f"[INVESTIGATE] Parsing Nemotron response for issue #{payload.issue_number}", flush=True)

        all_analyzed = analysis["files"] + analysis["tests"]
        response_data = NemotronPipelineResponse(
            success=True,
            repository=f"{payload.owner}/{payload.repo}",
            issue_number=payload.issue_number,
            files_analyzed=[
                AnalyzedFileItem(path=f["path"], language=f.get("language", "unknown"))
                for f in all_analyzed
            ],
            investigation=investigation_res
        )

        # Stage 6: Completed
        logger.info(f"[INVESTIGATE] Completed investigation for {payload.owner}/{payload.repo}#{payload.issue_number}")
        print(f"[INVESTIGATE] Completed investigation for {payload.owner}/{payload.repo}#{payload.issue_number}", flush=True)

        return response_data

    except GitHubTimeoutError as gte:
        logger.error(f"[INVESTIGATE] GitHub API timeout: {gte}")
        print(f"[INVESTIGATE] GitHub API timeout: {gte}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "gateway_timeout", "error_code": "GITHUB_TIMEOUT", "message": _sanitize_error(gte)}
        )
    except GitHubConnectionError as gce:
        logger.error(f"[INVESTIGATE] GitHub API connection error: {gce}")
        print(f"[INVESTIGATE] GitHub API connection error: {gce}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "github_connection_error", "error_code": "GITHUB_CONNECTION_ERROR", "message": _sanitize_error(gce)}
        )
    except (GitHubAuthError, GitHubRateLimitError, GitHubPermissionError, GitHubNotFoundError, GitHubError) as ge:
        logger.error(f"[INVESTIGATE] GitHub error: {ge}")
        print(f"[INVESTIGATE] GitHub error: {ge}", flush=True)
        raise map_github_exception(ge)
    except NemotronTimeoutError as te:
        logger.error(f"[INVESTIGATE] Nemotron timeout error: {te}")
        print(f"[INVESTIGATE] Nemotron timeout error: {te}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "gateway_timeout", "error_code": "NEMOTRON_TIMEOUT", "message": _sanitize_error(te)}
        )
    except NemotronRateLimitError as rle:
        logger.error(f"[INVESTIGATE] Nemotron rate limit error: {rle}")
        print(f"[INVESTIGATE] Nemotron rate limit error: {rle}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limited", "error_code": "NEMOTRON_RATE_LIMITED", "message": _sanitize_error(rle)}
        )
    except NemotronAuthError as nae:
        logger.error(f"[INVESTIGATE] Nemotron auth error: {nae}")
        print(f"[INVESTIGATE] Nemotron auth error: {nae}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "error_code": "NEMOTRON_AUTH_ERROR", "message": _sanitize_error(nae)}
        )
    except NemotronResponseError as nre:
        logger.error(f"[INVESTIGATE] Nemotron invalid response error: {nre}")
        print(f"[INVESTIGATE] Nemotron invalid response error: {nre}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "bad_gateway", "error_code": "NEMOTRON_INVALID_RESPONSE", "message": _sanitize_error(nre)}
        )
    except NemotronAPIError as be:
        logger.error(f"[INVESTIGATE] Nemotron API error: {be}")
        print(f"[INVESTIGATE] Nemotron API error: {be}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "bad_gateway", "error_code": "NEMOTRON_API_ERROR", "message": _sanitize_error(be)}
        )
    except ValueError as ve:
        logger.error(f"[INVESTIGATE] Bad request error: {ve}")
        print(f"[INVESTIGATE] Bad request error: {ve}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_sanitize_error(ve)
        )
    except Exception as e:
        safe_msg = _sanitize_error(e)
        logger.error(f"[INVESTIGATE] Unexpected error: {safe_msg}")
        print(f"[INVESTIGATE] Unexpected error: {safe_msg}", flush=True)
        if "github" in safe_msg.lower():
            if "timeout" in safe_msg.lower():
                status_code = status.HTTP_504_GATEWAY_TIMEOUT
                error_code = "GITHUB_TIMEOUT"
                error_type = "github_timeout"
            else:
                status_code = status.HTTP_502_BAD_GATEWAY
                error_code = "GITHUB_CONNECTION_ERROR"
                error_type = "github_connection_error"
        elif "timeout" in safe_msg.lower():
            status_code = status.HTTP_504_GATEWAY_TIMEOUT
            error_code = "NEMOTRON_TIMEOUT"
            error_type = "gateway_timeout"
        elif "connection" in safe_msg.lower() or "502" in safe_msg.lower() or "gateway" in safe_msg.lower():
            status_code = status.HTTP_502_BAD_GATEWAY
            error_code = "NEMOTRON_API_ERROR"
            error_type = "bad_gateway"
        elif "rate limit" in safe_msg.lower():
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            error_code = "NEMOTRON_RATE_LIMITED"
            error_type = "rate_limited"
        elif any(term in safe_msg.lower() for term in ["unauthorized", "authentication", "forbidden"]):
            status_code = status.HTTP_401_UNAUTHORIZED
            error_code = "NEMOTRON_AUTH_ERROR"
            error_type = "unauthorized"
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_code = "NEMOTRON_API_ERROR"
            error_type = "internal_error"
        raise HTTPException(
            status_code=status_code,
            detail={"error": error_type, "error_code": error_code, "message": f"Nemotron investigation failed: {safe_msg}"}
        )

@router.post("/generate-patch", response_model=NemotronPatchResponse)
async def generate_patch(payload: NemotronGeneratePatchRequest):
    """
    Generates a minimal unified diff patch for an investigated issue.
    Ensures patch only references files that exist in the repository context.
    """
    try:
        result = await nemotron_service.generate_patch(
            issue=payload.issue.model_dump(),
            investigation=payload.investigation.model_dump(),
            files=[f.model_dump() for f in payload.files],
            tests=[t.model_dump() for t in payload.tests]
        )
        return result
    except ValueError as ve:
        # Includes NemotronResponseError (malformed/invalid model output) -> client-side 400.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_sanitize_error(ve)
        )
    except NemotronTimeoutError as te:
        logger.error(f"[GENERATE_PATCH] Nemotron timeout: {te}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "gateway_timeout",
                "error_code": "NEMOTRON_TIMEOUT",
                "message": _sanitize_error(te),
                "correlation_id": getattr(te, "correlation_id", None)
            }
        )
    except NemotronRateLimitError as rle:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "error_code": "NEMOTRON_RATE_LIMITED",
                "message": _sanitize_error(rle),
                "correlation_id": getattr(rle, "correlation_id", None)
            }
        )
    except NemotronAuthError as nae:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "error_code": "NEMOTRON_AUTH_ERROR",
                "message": _sanitize_error(nae),
                "correlation_id": getattr(nae, "correlation_id", None)
            }
        )
    except NemotronAPIError as be:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "bad_gateway",
                "error_code": "NEMOTRON_API_ERROR",
                "message": _sanitize_error(be),
                "correlation_id": getattr(be, "correlation_id", None)
            }
        )
    except Exception as e:
        safe_msg = _sanitize_error(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patch generation failed: {safe_msg}"
        )

@router.post("/patch", response_model=NemotronRealPatchResponse)
async def generate_real_patch(payload: NemotronPatchRequest, request: Request):
    """
    Real unified patch generation and diff validation pipeline:
    1. Authenticates using persistent SQLite GitHub session cookie.
    2. Retrieves real current file contents for affected files.
    3. Calls Nemotron to synthesize a unified diff.
    4. Validates syntax, scope, safety limits, and clean application.
    5. Returns validated unified diff patch.
    """
    token = get_github_access_token(request)
    try:
        result = await patch_service.generate_and_validate_patch(
            owner=payload.owner,
            repo=payload.repo,
            branch=payload.branch or "main",
            issue_number=payload.issue_number,
            investigation=payload.investigation.model_dump(),
            access_token=token
        )
        return result
    except DiffApplicationError as dae:
        logger.error(f"[PATCH] Diff application error: {dae.message}")
        print(f"[PATCH] Diff application error: {dae.message}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "patch_application_failed",
                "status": "PATCH_APPLICATION_FAILED",
                "message": dae.message,
                "file": getattr(dae, "file", None),
                "hunk": getattr(dae, "hunk", None),
                "retry_available": getattr(dae, "retry_available", False),
                "attempts": getattr(dae, "attempts", 1)
            }
        )
    except (DiffValidationError, DiffSyntaxError, DiffPathError, DiffScopeError, DiffLimitExceededError) as dve:
        logger.error(f"[PATCH] Diff validation error: {dve.message}")
        print(f"[PATCH] Diff validation error: {dve.message}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_patch",
                "status": "INVALID_PATCH",
                "message": dve.message,
                "file": getattr(dve, "file", None),
                "hunk": getattr(dve, "hunk", None),
                "retry_available": False,
            }
        )
    except (GitHubTimeoutError, NemotronTimeoutError) as te:
        logger.error(f"[PATCH] Timeout error: {te}")
        print(f"[PATCH] Timeout error: {te}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "error": "gateway_timeout",
                "error_code": "GITHUB_TIMEOUT" if isinstance(te, GitHubTimeoutError) else "NEMOTRON_TIMEOUT",
                "message": _sanitize_error(te),
                "retry_available": True,
                "correlation_id": getattr(te, "correlation_id", None)
            }
        )
    except (GitHubConnectionError, NemotronAPIError, NemotronResponseError) as be:
        logger.error(f"[PATCH] Upstream error: {be}")
        print(f"[PATCH] Upstream error: {be}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "bad_gateway",
                "error_code": "GITHUB_CONNECTION_ERROR" if isinstance(be, GitHubConnectionError) else "NEMOTRON_API_ERROR",
                "message": _sanitize_error(be),
                "correlation_id": getattr(be, "correlation_id", None)
            }
        )
    except (GitHubAuthError, GitHubRateLimitError, GitHubNotFoundError, GitHubError) as ge:
        logger.error(f"[PATCH] GitHub error: {ge}")
        print(f"[PATCH] GitHub error: {ge}", flush=True)
        raise map_github_exception(ge)
    except Exception as e:
        safe_msg = _sanitize_error(e)
        logger.error(f"[PATCH] Unexpected patch error: {safe_msg}")
        print(f"[PATCH] Unexpected patch error: {safe_msg}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Patch generation failed: {safe_msg}"
        )


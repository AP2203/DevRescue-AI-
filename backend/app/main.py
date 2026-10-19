import sys
import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import ResponseValidationError, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
from app.api.health import router as health_router
from app.api.risk import router as risk_router
from app.api.investigations import router as investigations_router
from app.api.repositories import router as repositories_router
from app.api.pull_requests import router as pull_requests_router
from app.api.github import router as github_router
from app.api.nemotron import router as nemotron_router
from app.api.sandbox import router as sandbox_router
from app.api.repair_queue import router as repair_queue_router
from app.services.risk_prediction_service import risk_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation: verify ML model and dependencies
    try:
        health_info = risk_service.get_health_status()
        if health_info["status"] == "healthy":
            print(f"[STARTUP SUCCESS] ML Model loaded: {health_info['model_type']} with {health_info['expected_features_count']} features.")
        else:
            print(f"[STARTUP FAILED] ML Model failed to load: {health_info.get('error')}")
    except Exception as e:
        print(f"[STARTUP EXCEPTION] Critical error initializing ML model: {e}")
    yield
    print("[SHUTDOWN] DevRescue AI API shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="DevRescue AI - Autonomous Software Engineering API with Real GitHub API Integration",
    lifespan=lifespan
)

# CORS Middleware with credentials enabled for secure session cookies.
# Must be registered BEFORE exception handlers so that error responses also
# carry CORS headers (a missing CORS header makes the browser report the raw
# "Failed to fetch" TypeError instead of the real HTTP error).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

logger = logging.getLogger("devrescue.main")


@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    """
    A response-model validation failure used to surface as an unhandled 500
    (often without CORS headers), which the browser reports as "Failed to fetch".
    Return a structured JSON 500 instead so the frontend can show the real stage.
    """
    logger.error(f"[RESPONSE VALIDATION ERROR] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": "response_validation_error",
                "error_code": "RESPONSE_VALIDATION_ERROR",
                "message": "The server produced a response that failed internal validation. This is a backend defect, not a successful result.",
                "path": request.url.path,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error": "request_validation_error",
                "error_code": "REQUEST_VALIDATION_ERROR",
                "message": "The request payload was invalid.",
                "path": request.url.path,
                "errors": exc.errors() if hasattr(exc, "errors") else [],
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all so unexpected backend errors return a structured JSON body (with
    CORS headers) rather than dropping the connection, which the browser would
    report only as "Failed to fetch".
    """
    logger.error(f"[UNHANDLED EXCEPTION] {request.method} {request.url.path}: {exc}\n{traceback.format_exc()}")
    response = JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": "internal_error",
                "error_code": "INTERNAL_ERROR",
                "message": f"Internal server error: {type(exc).__name__}",
                "path": request.url.path,
            }
        },
    )
    # The generic Exception handler runs in ServerErrorMiddleware (outside the
    # CORS middleware), so attach CORS headers manually; otherwise the browser
    # hides this structured error behind "Failed to fetch".
    origin = request.headers.get("origin")
    if origin and origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# Register API Routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(risk_router, prefix=settings.API_V1_PREFIX)
app.include_router(investigations_router, prefix=settings.API_V1_PREFIX)
app.include_router(repositories_router, prefix=settings.API_V1_PREFIX)
app.include_router(pull_requests_router, prefix=settings.API_V1_PREFIX)
app.include_router(github_router, prefix=settings.API_V1_PREFIX)
app.include_router(nemotron_router, prefix=settings.API_V1_PREFIX)
app.include_router(sandbox_router, prefix=settings.API_V1_PREFIX)
app.include_router(repair_queue_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "message": "DevRescue AI API is running.",
        "documentation": "/docs",
        "endpoints": {
            "health": f"{settings.API_V1_PREFIX}/health",
            "risk_health": f"{settings.API_V1_PREFIX}/risk/health",
            "risk_predict": f"{settings.API_V1_PREFIX}/risk/predict",
            "investigations": f"{settings.API_V1_PREFIX}/investigations",
            "repositories": f"{settings.API_V1_PREFIX}/repositories",
            "pull_requests": f"{settings.API_V1_PREFIX}/pull_requests",
            "github_me": f"{settings.API_V1_PREFIX}/github/me",
            "github_login": f"{settings.API_V1_PREFIX}/github/login",
            "github_repositories": f"{settings.API_V1_PREFIX}/github/repositories",
            "nemotron_health": f"{settings.API_V1_PREFIX}/ai/nemotron/health",
            "nemotron_investigate": f"{settings.API_V1_PREFIX}/ai/nemotron/investigate",
            "nemotron_generate_patch": f"{settings.API_V1_PREFIX}/ai/nemotron/generate-patch",
            "nemotron_patch": f"{settings.API_V1_PREFIX}/ai/nemotron/patch",
            "sandbox_status": f"{settings.API_V1_PREFIX}/ai/sandbox/status",
            "sandbox_test": f"{settings.API_V1_PREFIX}/ai/sandbox/test"
        }
    }



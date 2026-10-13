"""Vision3D AI - FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded as SlowRateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import __version__
from app.config import get_settings
from app.db.mongodb import connect, disconnect
from app.exceptions import AppError
from app.logging_config import clear_request_context, configure_logging, set_request_context
from app.services import build_services
from app.services.storage_service import get_storage
from app.workers.processor import JobProcessor

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=[])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    settings = get_settings()
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, __version__, settings.ENVIRONMENT)

    db = await connect()
    app.state.db = db
    app.state.services = build_services(db)
    app.state.storage_provider = get_storage().provider

    worker: JobProcessor | None = None
    if settings.JOB_WORKER_ENABLED:
        worker = JobProcessor(
            db,
            get_storage(),
            poll_interval=settings.JOB_POLL_INTERVAL_SECONDS,
            stale_minutes=settings.JOB_STALE_TIMEOUT_MINUTES,
            max_retries=settings.JOB_MAX_RETRIES,
        )
        app.state.job_processor = worker
        app.state.worker_task = asyncio.create_task(worker.run())
        logger.info("Job worker enabled with %ss polling", settings.JOB_POLL_INTERVAL_SECONDS)

    yield

    if worker is not None:
        await worker.stop()
    await disconnect()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Vision3D AI API",
        version=__version__,
        description=(
            "REST API for converting 2D images into downloadable 3D models. "
            "Supports JWT auth, project management, background AI generation "
            "jobs, and model download."
        ),
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # -- CORS -----------------------------------------------------------------
    # A wildcard origin with credentials is invalid per the CORS spec, so fall
    # back to a permissive explicit list when no origins are configured.
    cors_origins = settings.CORS_ORIGINS or ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    app.add_middleware(SlowAPIMiddleware)

    # -- Rate limiting --------------------------------------------------------
    app.state.limiter = limiter

    async def rate_limit_handler(_request: Request, exc: SlowRateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "Too many requests. Please slow down and try again.",
                }
            },
        )

    app.add_exception_handler(SlowRateLimitExceeded, rate_limit_handler)

    # -- Error handlers -------------------------------------------------------
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        # Malformed ObjectIds and other value errors are client mistakes, not 500s.
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_value", "message": str(exc) or "Invalid value"}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            details[loc or "body"] = err.get("msg", "invalid value")
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Request validation failed", "details": details}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred"}},
        )

    # -- Request logging middleware -------------------------------------------
    @app.middleware("http")
    async def request_logger(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            set_request_context(
                request_id=request_id,
                path=request.url.path,
                method=request.method,
                duration_ms=round(duration_ms, 2),
            )
            clear_request_context()
        response.headers["X-Request-ID"] = request_id
        if not request.url.path.startswith("/api/v1/files"):
            logger.info(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={"extra_fields": {"request_id": request_id}},
            )
        return response

    # -- Routes ---------------------------------------------------------------
    from app.api.routes import admin, auth, edit, files, health, jobs, models, optimize, projects, quality, repair, uploads, users

    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(users.router, prefix=settings.API_V1_PREFIX)
    app.include_router(uploads.router, prefix=settings.API_V1_PREFIX)
    app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
    app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
    app.include_router(models.router, prefix=settings.API_V1_PREFIX)
    app.include_router(files.files_router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
    app.include_router(health.router, prefix=settings.API_V1_PREFIX)
    # New advanced feature routes
    app.include_router(quality.router, prefix=settings.API_V1_PREFIX)
    app.include_router(repair.router, prefix=settings.API_V1_PREFIX)
    app.include_router(edit.router, prefix=settings.API_V1_PREFIX)
    app.include_router(optimize.router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.APP_NAME,
            "docs": f"{settings.API_V1_PREFIX}/docs" if settings.ENVIRONMENT != "production" else None,
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


app = create_app()

import sys
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
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

# CORS Middleware with credentials enabled for secure session cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(risk_router, prefix=settings.API_V1_PREFIX)
app.include_router(investigations_router, prefix=settings.API_V1_PREFIX)
app.include_router(repositories_router, prefix=settings.API_V1_PREFIX)
app.include_router(pull_requests_router, prefix=settings.API_V1_PREFIX)
app.include_router(github_router, prefix=settings.API_V1_PREFIX)
app.include_router(nemotron_router, prefix=settings.API_V1_PREFIX)
app.include_router(sandbox_router, prefix=settings.API_V1_PREFIX)

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



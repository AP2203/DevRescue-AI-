"""Health and metadata route."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app import __version__
from app.ai.factory import get_registered_models
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    settings = get_settings()
    db_state = "ok"
    try:
        from app.db.mongodb import client

        if client is not None:
            await client.admin.command("ping")
        else:
            db_state = "not_initialized"
    except Exception as exc:  # pragma: no cover
        db_state = f"error: {type(exc).__name__}"

    return {
        "status": "ok" if db_state == "ok" else "degraded",
        "service": settings.APP_NAME,
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "ai_model": settings.AI_MODEL,
        "ai_models_available": get_registered_models(),
        "storage": getattr(request.app.state, "storage_provider", settings.STORAGE_BACKEND),
        "database": db_state,
        "time": datetime.now(UTC).isoformat(),
    }


@router.get("/models")
async def available_models() -> dict:
    from app.ai.factory import create_ai_model

    models = {}
    for name in get_registered_models():
        try:
            instance = create_ai_model(name)
            models[name] = instance.describe()
        except Exception as exc:  # pragma: no cover
            models[name] = {"name": name, "error": str(exc)}
    return {"default": get_settings().AI_MODEL, "models": models}

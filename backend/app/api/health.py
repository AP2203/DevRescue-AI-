from fastapi import APIRouter
from app.core.config import settings
from app.services.risk_prediction_service import risk_service

router = APIRouter(tags=["Health"])

@router.get("/health")
def get_health():
    """
    Core system health endpoint distinguishing healthy, degraded, or failed states.
    """
    ml_health = risk_service.get_health_status()
    overall_status = "healthy" if ml_health["status"] == "healthy" else "degraded"

    return {
        "status": overall_status,
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "components": {
            "ml_risk_model": ml_health["status"],
            "fastapi_server": "healthy"
        },
        "ml_details": {
            "model_loaded": ml_health["model_loaded"],
            "model_type": ml_health.get("model_type"),
            "expected_features_count": ml_health.get("expected_features_count", 0),
            "error": ml_health.get("error")
        }
    }

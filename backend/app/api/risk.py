from fastapi import APIRouter, HTTPException, status
from app.schemas.risk import RiskFeatureInput, RiskPredictionResponse
from app.services.risk_prediction_service import risk_service

router = APIRouter(prefix="/risk", tags=["Risk Analysis"])

@router.get("/health")
def get_risk_health():
    """Health check endpoint specific to the ML risk prediction model."""
    try:
        return risk_service.get_health_status()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk service health check failed: {str(e)}"
        )

@router.post("/predict", response_model=RiskPredictionResponse)
def predict_risk(features: RiskFeatureInput):
    """
    Predict patch regression risk using the trained 13-feature XGBoost model.
    Returns predicted risk level (LOW, MEDIUM, HIGH) with probabilities.
    """
    try:
        return risk_service.predict(features)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Feature validation error: {str(ve)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failure: {str(e)}"
        )

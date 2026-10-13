import json
import os
import joblib
import pandas as pd
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.schemas.risk import RiskFeatureInput, RiskPredictionResponse

class RiskPredictionService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RiskPredictionService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.model_path = settings.MODEL_PATH
        self.features_path = settings.FEATURES_PATH
        self.label_mapping_path = settings.LABEL_MAPPING_PATH
        
        self.model = None
        self.expected_features: List[str] = []
        self.label_mapping: Dict[str, int] = {}
        self.reverse_label_mapping: Dict[int, str] = {}
        self.status: str = "uninitialized"
        self.error: Optional[str] = None
        
        try:
            self.load_model()
            self.status = "healthy"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            print(f"[FATAL ML STARTUP ERROR] XGBoost model failed to load: {e}")

        self._initialized = True

    def load_model(self):
        """Loads and verifies the XGBoost model, feature list, and label mapping."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at: {self.model_path}")
        if not os.path.exists(self.features_path):
            raise FileNotFoundError(f"Features file not found at: {self.features_path}")
        if not os.path.exists(self.label_mapping_path):
            raise FileNotFoundError(f"Label mapping file not found at: {self.label_mapping_path}")

        # 1. Load feature names
        with open(self.features_path, "r", encoding="utf-8") as f:
            self.expected_features = json.load(f)

        if len(self.expected_features) != 13:
            raise ValueError(f"Expected exactly 13 features, but found {len(self.expected_features)} in {self.features_path}")

        # 2. Load label mapping
        with open(self.label_mapping_path, "r", encoding="utf-8") as f:
            self.label_mapping = json.load(f)
        
        self.reverse_label_mapping = {int(v): str(k) for k, v in self.label_mapping.items()}

        # 3. Load ML model
        self.model = joblib.load(self.model_path)
        
        # 4. Verify model attributes
        model_features_in = getattr(self.model, "n_features_in_", None)
        if model_features_in is not None and model_features_in != len(self.expected_features):
            raise ValueError(
                f"Model expects {model_features_in} features, but feature definition list has {len(self.expected_features)}"
            )

    def predict(self, feature_input: RiskFeatureInput) -> RiskPredictionResponse:
        """Runs inference on the provided 13 features using the loaded XGBoost model."""
        if self.status != "healthy" or self.model is None:
            raise RuntimeError(f"ML Model is unavailable (status: {self.status}). Error: {self.error}")

        # Extract features dictionary
        input_dict = feature_input.model_dump()
        
        # Build DataFrame with exact ordered columns
        df_row = pd.DataFrame([{col: input_dict[col] for col in self.expected_features}])

        # Predict class index
        raw_pred = self.model.predict(df_row)
        predicted_class_idx = int(raw_pred[0])
        predicted_label = self.reverse_label_mapping.get(predicted_class_idx, "UNKNOWN")

        # Predict class probabilities
        probs_dict: Dict[str, float] = {}
        if hasattr(self.model, "predict_proba"):
            raw_probs = self.model.predict_proba(df_row)[0]
            for idx, prob in enumerate(raw_probs):
                label_name = self.reverse_label_mapping.get(idx, f"CLASS_{idx}")
                probs_dict[label_name] = round(float(prob), 4)
            confidence = round(float(raw_probs[predicted_class_idx]), 4)
        else:
            confidence = 1.0
            probs_dict[predicted_label] = 1.0

        # Build recommendation based on predicted label
        if predicted_label == "LOW":
            recommendation = "Low regression risk detected. Safe for automated CI test suite and fast-track PR creation."
        elif predicted_label == "MEDIUM":
            recommendation = "Moderate risk detected. Requires standard automated testing and human reviewer sign-off."
        else:
            recommendation = "High regression risk detected. Deep test coverage and thorough security audit required before merge."

        return RiskPredictionResponse(
            risk_level=predicted_label,
            risk_score=confidence,
            predicted_class=predicted_class_idx,
            probabilities=probs_dict,
            features_received=input_dict,
            model_name=type(self.model).__name__,
            status="success",
            recommendation=recommendation
        )

    def get_health_status(self) -> Dict[str, Any]:
        """Returns health metadata distinguishing healthy, degraded, or failed."""
        return {
            "status": self.status,
            "model_loaded": self.model is not None,
            "error": self.error,
            "model_type": type(self.model).__name__ if self.model else None,
            "expected_features_count": len(self.expected_features),
            "expected_features": self.expected_features,
            "label_mapping": self.label_mapping
        }

risk_service = RiskPredictionService()

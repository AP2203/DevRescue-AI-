import os
import sys
import json
import fastapi
import uvicorn
import pydantic
import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import pytest
import httpx

def main():
    print("=== STEP 1: ENVIRONMENT VERIFICATION ===")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"FastAPI version: {fastapi.__version__}")
    print(f"XGBoost version: {xgb.__version__}")
    print(f"Scikit-learn version: {sklearn.__version__}")
    print(f"Joblib version: {joblib.__version__}")
    print(f"NumPy version: {np.__version__}")
    print(f"Pandas version: {pd.__version__}")
    print(f"Pydantic version: {pydantic.__version__}")
    print(f"Pytest version: {pytest.__version__}")
    print(f"HTTPX version: {httpx.__version__}")

    print("\n=== STEP 2: ML MODEL VERIFICATION ===")
    base_ml_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "ml")
    model_path = os.path.join(base_ml_dir, "devrescue_risk_model.pkl")
    features_path = os.path.join(base_ml_dir, "devrescue_features.json")
    labels_path = os.path.join(base_ml_dir, "risk_label_mapping.json")

    # Load model
    model = joblib.load(model_path)
    model_type = type(model).__name__
    print(f"Model type: {model_type}")
    assert "XGB" in model_type, f"Unexpected model type: {model_type}"

    # Features in model
    n_features = getattr(model, "n_features_in_", None)
    print(f"model.n_features_in_: {n_features}")
    assert n_features == 13, f"Expected 13 features, got {n_features}"

    # Load feature names
    with open(features_path, "r", encoding="utf-8") as f:
        features = json.load(f)
    print(f"devrescue_features count: {len(features)}")
    print(f"devrescue_features: {features}")
    assert len(features) == n_features == 13, "Feature count mismatch!"

    # Load label mapping
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    print(f"risk_label_mapping: {labels}")
    assert "LOW" in labels and "MEDIUM" in labels and "HIGH" in labels, "Labels missing LOW/MEDIUM/HIGH!"

    # Test an inference sample
    sample_df = pd.DataFrame([{col: 1 for col in features}])
    pred = model.predict(sample_df)
    probs = model.predict_proba(sample_df)
    print(f"Sample prediction: {pred[0]} with probabilities: {probs[0]}")

    print("\nALL ENVIRONMENT AND ML MODEL CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()

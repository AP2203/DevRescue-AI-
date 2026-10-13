import math
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

class RiskFeatureInput(BaseModel):
    files_changed: int = Field(..., ge=0, description="Number of files changed in patch")
    lines_added: int = Field(..., ge=0, description="Number of lines added")
    lines_removed: int = Field(..., ge=0, description="Number of lines removed")
    total_changed_lines: int = Field(..., ge=0, description="Total changed lines (added + removed)")
    patch_size: int = Field(..., ge=0, description="Patch size in bytes or diff line count")
    functions_changed: int = Field(..., ge=0, description="Number of functions modified")
    classes_changed: int = Field(..., ge=0, description="Number of classes modified")
    cyclomatic_complexity: float = Field(..., ge=0.0, description="Cyclomatic complexity score")
    code_size: int = Field(..., ge=0, description="Total code size or touched file size")
    dependency_changes: int = Field(..., ge=0, description="Number of dependency / manifest changes")
    test_count: int = Field(..., ge=0, description="Total test count executed")
    tests_passed: int = Field(..., ge=0, description="Tests passed")
    tests_failed: int = Field(..., ge=0, description="Tests failed")

    @field_validator("*", mode="before")
    @classmethod
    def check_finite_and_valid(cls, v):
        if v is None:
            raise ValueError("Feature value cannot be None")
        if isinstance(v, float):
            if math.isnan(v):
                raise ValueError("Feature value cannot be NaN")
            if math.isinf(v):
                raise ValueError("Feature value cannot be Infinite")
        return v

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "files_changed": 2,
                "lines_added": 15,
                "lines_removed": 3,
                "total_changed_lines": 18,
                "patch_size": 450,
                "functions_changed": 1,
                "classes_changed": 0,
                "cyclomatic_complexity": 2.5,
                "code_size": 1200,
                "dependency_changes": 0,
                "test_count": 8,
                "tests_passed": 8,
                "tests_failed": 0
            }
        }
    }


class RiskPredictionResponse(BaseModel):
    risk_level: str = Field(..., description="Predicted risk level: LOW, MEDIUM, or HIGH")
    risk_score: float = Field(..., description="Calculated confidence or risk probability score (0.0 to 1.0)")
    predicted_class: int = Field(..., description="Model class index (0, 1, or 2)")
    probabilities: Dict[str, float] = Field(..., description="Class probability distribution")
    features_received: Dict[str, Any] = Field(..., description="The 13 input features used for inference")
    model_name: str = Field(default="XGBClassifier", description="Name of the machine learning model")
    status: str = Field(default="success", description="Inference status")
    recommendation: Optional[str] = Field(None, description="Actionable recommendation based on predicted risk")

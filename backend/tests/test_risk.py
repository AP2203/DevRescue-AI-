import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

VALID_FEATURES = {
    "files_changed": 3,
    "lines_added": 25,
    "lines_removed": 10,
    "total_changed_lines": 35,
    "patch_size": 1024,
    "functions_changed": 2,
    "classes_changed": 1,
    "cyclomatic_complexity": 3.2,
    "code_size": 2500,
    "dependency_changes": 0,
    "test_count": 12,
    "tests_passed": 12,
    "tests_failed": 0
}

@pytest.mark.asyncio
async def test_risk_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/risk/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert data["expected_features_count"] == 13

@pytest.mark.asyncio
async def test_predict_risk_valid():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=VALID_FEATURES)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert 0.0 <= data["risk_score"] <= 1.0
    assert "probabilities" in data
    assert "LOW" in data["probabilities"]
    assert "MEDIUM" in data["probabilities"]
    assert "HIGH" in data["probabilities"]
    prob_sum = sum(data["probabilities"].values())
    assert 0.99 <= prob_sum <= 1.01

@pytest.mark.asyncio
async def test_predict_risk_missing_feature():
    incomplete_features = VALID_FEATURES.copy()
    del incomplete_features["cyclomatic_complexity"]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=incomplete_features)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_predict_risk_negative_value():
    invalid_features = VALID_FEATURES.copy()
    invalid_features["lines_added"] = -5
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=invalid_features)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_predict_risk_invalid_type():
    invalid_features = VALID_FEATURES.copy()
    invalid_features["patch_size"] = "large"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=invalid_features)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_predict_risk_extra_feature():
    invalid_features = VALID_FEATURES.copy()
    invalid_features["unexpected_column"] = 999
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=invalid_features)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_predict_risk_zero_boundary():
    zero_features = {k: (0.0 if k == "cyclomatic_complexity" else 0) for k in VALID_FEATURES}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/risk/predict", json=zero_features)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert data["status"] == "success"

def test_schema_nan_and_inf_validation():
    from app.schemas.risk import RiskFeatureInput
    import pytest as pt
    features_copy = VALID_FEATURES.copy()
    features_copy["cyclomatic_complexity"] = float("nan")
    with pt.raises(Exception):
        RiskFeatureInput(**features_copy)

    features_copy["cyclomatic_complexity"] = float("inf")
    with pt.raises(Exception):
        RiskFeatureInput(**features_copy)


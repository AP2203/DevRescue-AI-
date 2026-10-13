import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_investigation_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create investigation
        payload = {
            "repo": "acme-corp/payment-gateway",
            "issue_title": "Race condition in idempotency ledger",
            "error_description": "Concurrent webhook events capture duplicate settlements.",
            "branch": "main",
            "issue_number": 109,
            "mode": "demo"
        }
        create_res = await ac.post("/api/investigations", json=payload)
        assert create_res.status_code == 201
        inv = create_res.json()
        inv_id = inv["id"]
        assert inv["repo"] == "acme-corp/payment-gateway"
        assert inv["status"] == "READY_FOR_REVIEW"
        assert "risk_assessment" in inv
        assert inv["risk_assessment"]["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
        # Verify testing agent status is NOT_IMPLEMENTED (never fake passed)
        testing_agent = next(a for a in inv["agents"] if a["name"] == "Testing Agent")
        assert testing_agent["status"] == "NOT_IMPLEMENTED"

        # 2. Get investigation by ID
        get_res = await ac.get(f"/api/investigations/{inv_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == inv_id

        # 3. Get investigation logs
        logs_res = await ac.get(f"/api/investigations/{inv_id}/logs")
        assert logs_res.status_code == 200
        assert len(logs_res.json()["logs"]) > 0

        # 4. Approve investigation (Human Approval)
        approve_res = await ac.post(f"/api/investigations/{inv_id}/approve")
        assert approve_res.status_code == 200
        app_data = approve_res.json()
        assert app_data["investigation"]["human_approved"] is True
        assert app_data["pull_request"]["human_approved"] is True

@pytest.mark.asyncio
async def test_pull_request_without_human_approval():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "repo": "acme-corp/payment-gateway",
            "title": "fix: race condition",
            "body": "patch body",
            "branch": "devrescue/patch",
            "human_approved": False
        }
        res = await ac.post("/api/pull_requests", json=payload)
        assert res.status_code in [400, 403]
        assert "human" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_repositories_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/repositories")
        assert res.status_code == 200
        assert len(res.json()) >= 1

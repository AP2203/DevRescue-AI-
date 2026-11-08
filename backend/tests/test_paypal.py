import pytest
from app.services.pricing_service import pricing_service
from app.services.paypal_service import paypal_service
from app.services.session_store import session_store
from app.api.paypal import get_paypal_public_config

def test_paypal_public_config():
    config = get_paypal_public_config()
    assert "client_id" in config
    assert "mode" in config
    assert config["currency"] == "USD"

def test_dynamic_pricing_service_low_risk():
    quote = pricing_service.quote_bounty(
        repository="facebook/react",
        issue_number=101,
        issue_title="Fix typo in documentation comment",
        error_description="Minor syntax warning",
        cyclomatic_complexity=1.0,
        files_expected=1,
        test_count=3
    )
    assert quote["bounty_amount"] >= 10.0
    assert quote["currency"] == "USD"
    assert quote["risk_tier"] in ("LOW", "MEDIUM")
    assert "breakdown" in quote
    assert "recommendation" in quote

def test_dynamic_pricing_service_high_severity():
    quote = pricing_service.quote_bounty(
        repository="apache/kafka",
        issue_number=909,
        issue_title="Deadlock and race condition during consumer partition rebalance",
        error_description="Fatal deadlock leading to memory leak and crash under concurrency stress",
        cyclomatic_complexity=8.5,
        files_expected=4,
        test_count=25
    )
    assert quote["bounty_amount"] > 35.0
    assert "breakdown" in quote
    breakdown = quote["breakdown"]
    assert len(breakdown["detected_critical_factors"]) >= 2
    assert any(k in breakdown["detected_critical_factors"] for k in ("deadlock", "race condition", "memory leak"))

@pytest.mark.asyncio
async def test_paypal_order_lifecycle():
    # 1. Create Order
    order = await paypal_service.create_order(
        amount=50.0,
        currency="USD",
        investigation_id="inv-test-unit-01",
        repository="demo/payment-gateway",
        issue_number=42,
        issue_title="Idempotency lock fix"
    )
    assert "order_id" in order
    assert order["amount"] == 50.0
    assert order["status"] in ("CREATED", "APPROVED")

    order_id = order["order_id"]

    # 2. Capture Order on 100% green tests
    capture = await paypal_service.capture_order(order_id=order_id, investigation_id="inv-test-unit-01")
    assert capture["status"] == "COMPLETED"
    assert capture["verified_green_tests"] is True

    # 3. Check SQLite persistence
    txns = session_store.list_paypal_transactions(10)
    matching = [t for t in txns if t["order_id"] == order_id]
    assert len(matching) == 1
    assert matching[0]["amount"] == 50.0
    assert matching[0]["status"] == "COMPLETED"

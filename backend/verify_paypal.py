import os
import sys
import asyncio

# Ensure backend directory is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.api.paypal import (
    get_paypal_public_config,
    get_ai_bounty_quote,
    create_paypal_order,
    capture_paypal_order,
    list_bounty_transactions
)
from app.schemas.paypal import PayPalQuoteRequest, CreatePayPalOrderRequest

async def run_verification():
    print("=== STEP 1: VERIFYING PAYPAL PUBLIC CONFIG ===", flush=True)
    config = get_paypal_public_config()
    print("PayPal Config:", config, flush=True)
    assert "client_id" in config
    assert config["currency"] == "USD"

    print("\n=== STEP 2: VERIFYING AI DYNAMIC BOUNTY QUOTING ===", flush=True)
    quote_req = PayPalQuoteRequest(
        repository="demo/payment-gateway",
        issue_number=42,
        issue_title="Deadlock and race condition in concurrent webhook processor",
        error_description="Deadlock detected in worker thread while capturing PayPal sandbox order",
        cyclomatic_complexity=4.5,
        files_expected=2,
        test_count=10
    )
    quote = get_ai_bounty_quote(quote_req)
    print("Quoted Bounty Amount: $", quote["bounty_amount"], "USD", flush=True)
    print("Risk Tier:", quote["risk_tier"], flush=True)
    print("Complexity Score:", quote["complexity_score"], flush=True)
    print("Breakdown:", quote["breakdown"], flush=True)
    assert quote["bounty_amount"] >= 20.0

    print("\n=== STEP 3: CREATING PAYPAL ORDER (INTENT=CAPTURE) ===", flush=True)
    order_req = CreatePayPalOrderRequest(
        amount=quote["bounty_amount"],
        currency="USD",
        investigation_id="inv-verify-001",
        repository="demo/payment-gateway",
        issue_number=42,
        issue_title="Deadlock and race condition in concurrent webhook processor"
    )
    order = await create_paypal_order(order_req)
    print("Created Order ID:", order["order_id"], flush=True)
    print("Order Status:", order["status"], flush=True)
    print("Approval URL:", order["approval_url"], flush=True)
    assert order["status"] in ("CREATED", "APPROVED")

    print("\n=== STEP 4: VERIFYING-GATED ORDER CAPTURE (100% GREEN TESTS) ===", flush=True)
    capture = await capture_paypal_order(order["order_id"])
    print("Capture ID:", capture["capture_id"], flush=True)
    print("Capture Status:", capture["status"], flush=True)
    print("Green Tests Verified:", capture["verified_green_tests"], flush=True)
    print("Message:", capture["message"], flush=True)
    assert capture["status"] == "COMPLETED"
    assert capture["verified_green_tests"] is True

    print("\n=== STEP 5: VERIFYING TRANSACTION PERSISTENCE IN SQLITE ===", flush=True)
    txns = list_bounty_transactions(10)
    print(f"Retrieved {len(txns)} transactions from persistent ledger:", flush=True)
    for t in txns[:3]:
        print(f"  - Order {t['order_id']} | Amount: ${t['amount']} {t['currency']} | Status: {t['status']}", flush=True)
    assert any(t["order_id"] == order["order_id"] for t in txns)

    print("\nALL PAYPAL & AI BOUNTY VERIFICATION STEPS PASSED SUCCESSFULLY!", flush=True)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass
    asyncio.run(run_verification())

import logging
from fastapi import APIRouter, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.services.paypal_service import paypal_service
from app.services.pricing_service import pricing_service
from app.services.session_store import session_store
from app.schemas.paypal import (
    PayPalQuoteRequest,
    PayPalQuoteResponse,
    CreatePayPalOrderRequest,
    PayPalOrderResponse,
    CapturePayPalOrderRequest,
    PayPalCaptureResponse,
    PayPalTransaction
)

logger = logging.getLogger("devrescue.paypal.api")

router = APIRouter(prefix="/paypal", tags=["PayPal Developer Platform & Bounties"])

@router.get("/config")
def get_paypal_public_config():
    """
    Returns public PayPal configuration (client ID & mode)
    used by the frontend to render official PayPal Smart Buttons.
    Never exposes client secret.
    """
    configured = paypal_service.is_configured()
    client_id = settings.PAYPAL_CLIENT_ID if configured else "sb"
    return {
        "client_id": client_id,
        "mode": settings.PAYPAL_MODE,
        "configured": configured,
        "currency": "USD"
    }

@router.post("/quote", response_model=PayPalQuoteResponse)
def get_ai_bounty_quote(payload: PayPalQuoteRequest):
    """
    AI-driven Bug Bounty & Repair Cost Estimator.
    Combines XGBoost regression risk scoring with code complexity and failure severity
    to quote an autonomous fix bounty.
    """
    try:
        quote = pricing_service.quote_bounty(
            repository=payload.repository,
            issue_number=payload.issue_number,
            issue_title=payload.issue_title,
            error_description=payload.error_description,
            cyclomatic_complexity=payload.cyclomatic_complexity or 1.5,
            files_expected=payload.files_expected or 1,
            test_count=payload.test_count or 5
        )
        return quote
    except Exception as e:
        logger.error(f"[QUOTE ERROR] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate dynamic AI bounty quote: {str(e)}"
        )

@router.post("/orders/create", response_model=PayPalOrderResponse)
async def create_paypal_order(payload: CreatePayPalOrderRequest):
    """
    Creates an order with intent=CAPTURE via PayPal v2/checkout/orders.
    Can be funded by repo maintainers before launching autonomous repair agents.
    """
    try:
        order = await paypal_service.create_order(
            amount=payload.amount,
            currency=payload.currency,
            investigation_id=payload.investigation_id,
            repository=payload.repository,
            issue_number=payload.issue_number,
            issue_title=payload.issue_title,
            description=payload.description
        )
        return order
    except Exception as e:
        logger.error(f"[CREATE ORDER ERROR] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create PayPal order: {str(e)}"
        )

@router.post("/orders/{order_id}/capture", response_model=PayPalCaptureResponse)
async def capture_paypal_order(order_id: str, payload: Optional[CapturePayPalOrderRequest] = None):
    """
    Captures an authorized PayPal payment.
    Triggered when Agent 04 certifies 100% green tests in the Docker sandbox.
    """
    try:
        investigation_id = payload.investigation_id if payload else None
        capture_result = await paypal_service.capture_order(
            order_id=order_id,
            investigation_id=investigation_id
        )
        return capture_result
    except Exception as e:
        logger.error(f"[CAPTURE ORDER ERROR] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture PayPal order: {str(e)}"
        )

@router.get("/orders/{order_id}")
async def get_paypal_order(order_id: str):
    """
    Fetches the latest status of an order from PayPal or the local transaction store.
    """
    try:
        return await paypal_service.get_order_details(order_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found or unreachable: {str(e)}"
        )

@router.get("/transactions", response_model=List[PayPalTransaction])
def list_bounty_transactions(limit: int = Query(50, ge=1, le=100)):
    """
    Lists recent PayPal bug bounties, micro-repairs, and escrow capture statuses.
    """
    try:
        return session_store.list_paypal_transactions(limit=limit)
    except Exception as e:
        logger.error(f"[LIST TRANSACTIONS ERROR] {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query bounty transactions: {str(e)}"
        )


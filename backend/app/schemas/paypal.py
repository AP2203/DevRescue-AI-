from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class PayPalQuoteRequest(BaseModel):
    repository: Optional[str] = Field(None, description="Target repository full name (e.g. owner/repo)")
    issue_number: Optional[int] = Field(None, description="GitHub Issue number")
    issue_title: Optional[str] = Field(None, description="GitHub Issue Title")
    error_description: Optional[str] = Field("", description="Error stack trace or problem description")
    cyclomatic_complexity: Optional[float] = Field(1.5, description="Estimated code complexity")
    files_expected: Optional[int] = Field(1, description="Estimated files affected")
    test_count: Optional[int] = Field(5, description="Expected regression test suite size")

class PayPalQuoteResponse(BaseModel):
    bounty_amount: float = Field(..., description="Calculated bounty price in USD")
    currency: str = Field("USD", description="Currency code")
    risk_tier: str = Field(..., description="Risk tier: LOW, MEDIUM, or HIGH")
    complexity_score: float = Field(..., description="Composite complexity score from 1.0 to 10.0")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="Transparent pricing factor breakdown")
    recommendation: str = Field(..., description="Autonomous agent resource allocation recommendation")

class CreatePayPalOrderRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Bounty amount to authorize/capture")
    currency: str = Field("USD", description="Currency code (default USD)")
    investigation_id: Optional[str] = Field(None, description="Linked investigation ID")
    repository: Optional[str] = Field(None, description="Target GitHub repository")
    issue_number: Optional[int] = Field(None, description="Target GitHub issue number")
    issue_title: Optional[str] = Field(None, description="Target GitHub issue title")
    description: Optional[str] = Field("DevRescue AI Autonomous Bug Bounty", description="Order description")

class PayPalOrderResponse(BaseModel):
    order_id: str
    status: str
    approval_url: Optional[str] = None
    amount: float
    currency: str
    investigation_id: Optional[str] = None
    created_at: float

class CapturePayPalOrderRequest(BaseModel):
    order_id: str
    investigation_id: Optional[str] = None

class PayPalCaptureResponse(BaseModel):
    order_id: str
    status: str
    capture_id: Optional[str] = None
    amount: float
    currency: str
    investigation_id: Optional[str] = None
    verified_green_tests: bool = True
    message: str

class PayPalTransaction(BaseModel):
    order_id: str
    capture_id: Optional[str] = None
    investigation_id: Optional[str] = None
    repository: Optional[str] = None
    issue_number: Optional[int] = None
    amount: float
    currency: str = "USD"
    status: str  # CREATED, APPROVED, CAPTURED, FAILED
    payer_email: Optional[str] = None
    payer_name: Optional[str] = None
    created_at: float
    updated_at: float

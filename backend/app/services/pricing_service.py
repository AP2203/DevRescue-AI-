import re
import math
from typing import Dict, Any, Optional
from app.services.risk_prediction_service import risk_service
from app.schemas.risk import RiskFeatureInput

class DynamicPricingService:
    """
    AI-driven Bug Bounty & Repair Cost Estimator.
    Combines the 13-feature XGBoost regression risk model with semantic error analysis
    to calculate fair, transparent developer bounties funded via PayPal Sandbox.
    """

    CRITICAL_KEYWORDS = {
        "deadlock": 15.0,
        "race condition": 15.0,
        "memory leak": 12.0,
        "segmentation fault": 14.0,
        "security": 18.0,
        "vulnerability": 18.0,
        "cve": 20.0,
        "data loss": 20.0,
        "concurrency": 12.0,
        "recursionerror": 8.0,
        "overflow": 10.0,
        "unhandled exception": 5.0,
        "nullpointer": 5.0,
        "typeerror": 4.0,
        "indexerror": 4.0
    }

    def quote_bounty(
        self,
        repository: Optional[str] = None,
        issue_number: Optional[int] = None,
        issue_title: Optional[str] = None,
        error_description: Optional[str] = None,
        cyclomatic_complexity: float = 1.5,
        files_expected: int = 1,
        test_count: int = 5
    ) -> Dict[str, Any]:
        """
        Calculates a dynamic bounty quote based on code complexity, test scope, and ML risk prediction.
        """
        text_corpus = f"{issue_title or ''} {error_description or ''}".lower()
        
        # 1. Semantic severity bonus from error keywords
        severity_bonus = 0.0
        detected_triggers = []
        for kw, surcharge in self.CRITICAL_KEYWORDS.items():
            if kw in text_corpus:
                severity_bonus += surcharge
                detected_triggers.append(kw)
        severity_bonus = min(severity_bonus, 30.0)  # cap severity bonus

        # 2. Heuristic features for XGBoost model inference
        safe_files = max(1, files_expected)
        est_lines = safe_files * 8
        feature_input = RiskFeatureInput(
            files_changed=safe_files,
            lines_added=est_lines,
            lines_removed=max(1, int(est_lines * 0.3)),
            total_changed_lines=est_lines + max(1, int(est_lines * 0.3)),
            patch_size=est_lines * 45,
            functions_changed=safe_files,
            classes_changed=1 if safe_files > 1 else 0,
            cyclomatic_complexity=float(cyclomatic_complexity),
            code_size=safe_files * 400,
            dependency_changes=1 if "import" in text_corpus or "module" in text_corpus else 0,
            test_count=max(1, test_count),
            tests_passed=max(1, test_count - 1),
            tests_failed=1
        )

        try:
            prediction = risk_service.predict(feature_input)
            risk_tier = prediction.risk_level  # LOW, MEDIUM, or HIGH
            risk_score = prediction.risk_score
        except Exception:
            # Resilient fallback
            risk_tier = "MEDIUM" if safe_files > 1 or cyclomatic_complexity > 3.0 else "LOW"
            risk_score = 0.45

        # 3. Base pricing matrix by risk tier
        if risk_tier == "LOW":
            base_fee = 15.0
            complexity_multiplier = 1.0
        elif risk_tier == "MEDIUM":
            base_fee = 35.0
            complexity_multiplier = 1.3
        else:
            base_fee = 65.0
            complexity_multiplier = 1.6

        # 4. Granular breakdown components
        complexity_fee = round(min(20.0, (cyclomatic_complexity * 2.5)), 2)
        blast_radius_fee = round(safe_files * 4.0, 2)
        sandbox_compute_fee = round(max(3.0, test_count * 0.5), 2)
        nemotron_tokens_fee = round(base_fee * 0.25, 2)

        raw_total = base_fee + complexity_fee + blast_radius_fee + sandbox_compute_fee + severity_bonus
        # Round neatly to nearest dollar or .00
        bounty_amount = round(raw_total, 2)
        bounty_amount = max(10.0, min(150.0, bounty_amount))

        complexity_score = round(
            min(10.0, 1.0 + (cyclomatic_complexity * 0.8) + (safe_files * 1.2) + (len(detected_triggers) * 1.5)),
            1
        )

        recommendation = (
            f"Allocating 5-agent pipeline with {risk_tier} risk profile. "
            f"Escrow will hold ${bounty_amount:.2f} USD via PayPal Sandbox until Agent 04 certifies 100% green tests."
        )

        return {
            "bounty_amount": bounty_amount,
            "currency": "USD",
            "risk_tier": risk_tier,
            "complexity_score": complexity_score,
            "breakdown": {
                "base_fee": base_fee,
                "complexity_fee": complexity_fee,
                "blast_radius_fee": blast_radius_fee,
                "sandbox_compute_fee": sandbox_compute_fee,
                "nemotron_reasoning_fee": nemotron_tokens_fee,
                "severity_surcharge": round(severity_bonus, 2),
                "detected_critical_factors": detected_triggers,
                "predicted_risk_score": risk_score
            },
            "recommendation": recommendation
        }

pricing_service = DynamicPricingService()


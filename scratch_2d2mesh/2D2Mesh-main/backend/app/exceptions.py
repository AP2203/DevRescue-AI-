"""Centralized, typed exceptions that map to a consistent API error envelope."""
from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base application error with HTTP status and machine-readable code."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "Internal server error",
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class TokenExpiredError(AppError):
    status_code = 401
    code = "token_expired"


class AuthorizationError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class JobStateError(AppError):
    status_code = 409
    code = "job_state_error"


class StorageError(AppError):
    status_code = 502
    code = "storage_error"


class AIGenerationError(AppError):
    status_code = 502
    code = "ai_generation_failed"


class RateLimitHit(Exception):
    """Internal signal raised by the rate limiter middleware."""

    def __init__(self, detail: str = "Too many requests") -> None:
        super().__init__(detail)
        self.detail = detail


class RateLimitExceeded(Exception):
    """Raised by the JWT-route sliding window limiter."""

    pass

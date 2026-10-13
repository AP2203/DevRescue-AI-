"""Password hashing and JWT creation/validation."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.config import get_settings
from app.exceptions import AuthenticationError, TokenExpiredError, ValidationError

_PASSWORD_REQUIREMENTS = {
    "length": (8, "Password must be at least 8 characters long."),
    "lower": (r"[a-z]", "Password must contain a lowercase letter."),
    "upper": (r"[A-Z]", "Password must contain an uppercase letter."),
    "digit": (r"\d", "Password must contain a digit."),
}


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (salt embedded in the hash)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(plain: str) -> None:
    details: Dict[str, str] = {}
    if len(plain) < _PASSWORD_REQUIREMENTS["length"][0]:
        details["length"] = _PASSWORD_REQUIREMENTS["length"][1]
    for name, (pattern, msg) in list(_PASSWORD_REQUIREMENTS.items())[1:]:
        if not re.search(pattern, plain):
            details[name] = msg
    if details:
        raise ValidationError("Password does not meet requirements", details=details)


def _build_token(subject: str, token_type: str, expires: timedelta, extra: Optional[Dict[str, Any]] = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: Dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _secret_for(token_type), algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str, username: str) -> str:
    settings = get_settings()
    return _build_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"role": role, "username": username},
    )


def create_refresh_token(user_id: str) -> str:
    settings = get_settings()
    return _build_token(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def _secret_for(token_type: str) -> str:
    """Use a dedicated refresh-token secret when configured, else the main key."""
    settings = get_settings()
    if token_type == "refresh" and settings.JWT_REFRESH_SECRET:
        return settings.JWT_REFRESH_SECRET
    return settings.SECRET_KEY


def _decode(token: str, expected_type: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, _secret_for(expected_type), algorithms=[get_settings().JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("Token type mismatch")
    return payload


def decode_access_token(token: str) -> Dict[str, Any]:
    return _decode(token, "access")


def decode_refresh_token(token: str) -> Dict[str, Any]:
    return _decode(token, "refresh")

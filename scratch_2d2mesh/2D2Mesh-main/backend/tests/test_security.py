"""Unit tests for password hashing and JWT handling."""
from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.exceptions import AuthenticationError, ValidationError


def test_password_hash_roundtrip():
    hashed = hash_password("StrongPass123!")
    assert hashed != "StrongPass123!"
    assert verify_password("StrongPass123!", hashed)
    assert not verify_password("WrongPass123!", hashed)


def test_password_strength_rejects_weak():
    with pytest.raises(ValidationError):
        validate_password_strength("short")
    with pytest.raises(ValidationError):
        validate_password_strength("lowercaseonly1")


def test_jwt_roundtrip():
    token = create_access_token("user123", "admin", "alice")
    payload = decode_access_token(token)
    assert payload["sub"] == "user123"
    assert payload["role"] == "admin"
    assert payload["username"] == "alice"
    assert payload["type"] == "access"


def test_refresh_token_rejected_as_access():
    token = create_refresh_token("user123")
    with pytest.raises(AuthenticationError):
        decode_access_token(token)


def test_missing_subject_rejected():
    token = create_access_token("user123", "user", "bob")
    payload = decode_access_token(token)
    assert payload["sub"] == "user123"


def test_garbage_token_rejected():
    with pytest.raises(AuthenticationError):
        decode_access_token("not-a-jwt")

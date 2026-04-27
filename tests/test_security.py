"""Password hashing + JWT basics."""

from __future__ import annotations

import time

import pytest

from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("S3cret!")
    assert hashed.startswith("$argon2")
    assert verify_password("S3cret!", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_access_token_roundtrip() -> None:
    token = create_access_token(subject="user-1", role="customer")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["role"] == "customer"
    assert claims["exp"] > int(time.time())


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-real-token")


def test_refresh_token_hash_is_stable() -> None:
    raw = generate_refresh_token()
    first = hash_refresh_token(raw)
    second = hash_refresh_token(raw)
    assert first == second
    # Different tokens must hash differently.
    other = generate_refresh_token()
    assert hash_refresh_token(other) != first

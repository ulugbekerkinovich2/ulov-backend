"""Phone normalisation unit tests (no DB / no Redis)."""

from __future__ import annotations

import pytest

from app.core.phone import PhoneError, is_valid_phone, normalize_phone


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+998901234567", "+998901234567"),
        ("998901234567", "+998901234567"),
        ("+998 90 123 45 67", "+998901234567"),
        ("+998-90-123-45-67", "+998901234567"),
        ("+998 (90) 123-45-67", "+998901234567"),
    ],
)
def test_normalize_returns_e164(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "not-a-phone",
        "+1",
        "999",
        "abc123",
    ],
)
def test_normalize_rejects_garbage(raw: str) -> None:
    with pytest.raises(PhoneError):
        normalize_phone(raw)


def test_is_valid_phone_true() -> None:
    assert is_valid_phone("+998901234567") is True


def test_is_valid_phone_false() -> None:
    assert is_valid_phone("bogus") is False

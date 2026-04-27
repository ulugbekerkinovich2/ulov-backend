"""Plate utility unit tests (no DB / no Redis)."""

from __future__ import annotations

import pytest

from app.core.plate import (
    PlateError,
    PlateType,
    detect_plate_type,
    normalize_plate,
    validate_plate_type,
    validate_tech_passport,
    validate_vin,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01 A 123 BC", "01A123BC"),
        ("01a123bc", "01A123BC"),
        ("01-A-123-BC", "01A123BC"),
    ],
)
def test_normalize_standard(raw: str, expected: str) -> None:
    assert normalize_plate(raw) == expected


@pytest.mark.parametrize(
    "raw,kind",
    [
        ("01A123BC", PlateType.STANDARD),
        ("01123ABC", PlateType.LEGAL),
        ("ABC123", PlateType.OTHER),
        ("UZ77", PlateType.OTHER),
    ],
)
def test_detect_type(raw: str, kind: PlateType) -> None:
    assert detect_plate_type(raw) == kind


@pytest.mark.parametrize("raw", ["", "   ", "!!!", None])
def test_normalize_rejects_garbage(raw) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(PlateError):
        normalize_plate(raw)


def test_enforce_standard_rejects_wrong_shape() -> None:
    with pytest.raises(PlateError):
        validate_plate_type("01123ABC", PlateType.STANDARD)


def test_vin_accepts_valid() -> None:
    assert validate_vin("1HGBH41JXMN109186") == "1HGBH41JXMN109186"


@pytest.mark.parametrize(
    "bad", ["short", "1IJBH41JXMN109186", "TOOLONG1234567890123"]
)
def test_vin_rejects_invalid(bad: str) -> None:
    with pytest.raises(PlateError):
        validate_vin(bad)


def test_tech_passport() -> None:
    assert validate_tech_passport("AAA12345") == "AAA12345"
    with pytest.raises(PlateError):
        validate_tech_passport("x")

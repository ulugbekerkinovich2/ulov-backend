"""License plate validation + formatting.

Mirrors the logic of ``front-user/src/lib/plate.ts``. Three recognised shapes:

  * ``standard``  — ``00 X 000 XX``  (2 digits · 1 letter · 3 digits · 2 letters)
  * ``legal``     — ``00 000 XXX``   (2 digits · 3 digits · 3 letters)
  * ``other``     — free form (1..15 chars, alnum + spaces/dashes)

All plates are stored **without spaces** in the DB; display formatting is a
frontend concern. The API returns whatever the frontend sent, minus spaces.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional


class PlateType(str, Enum):
    STANDARD = "standard"
    LEGAL = "legal"
    OTHER = "other"


class PlateError(ValueError):
    """Raised on invalid plate input."""


# Characters kept when we normalise — uppercased.
_ALLOWED = re.compile(r"[^A-Z0-9]")

# Shape regexes operate on the normalised (stripped) form.
_STANDARD_RE = re.compile(r"^\d{2}[A-Z]\d{3}[A-Z]{2}$")
_LEGAL_RE = re.compile(r"^\d{2}\d{3}[A-Z]{3}$")
_OTHER_RE = re.compile(r"^[A-Z0-9]{1,15}$")


def _strip(raw: str) -> str:
    """Uppercase + drop everything not alnum."""
    return _ALLOWED.sub("", raw.upper())


def normalize_plate(raw: str) -> str:
    """Return the canonical, space-less form.

    Raises :class:`PlateError` if the plate does not match any recognised
    shape.
    """
    if raw is None or not str(raw).strip():
        raise PlateError("Plate is required")
    stripped = _strip(str(raw))
    if not stripped:
        raise PlateError("Plate has no valid characters")
    if (
        _STANDARD_RE.match(stripped)
        or _LEGAL_RE.match(stripped)
        or _OTHER_RE.match(stripped)
    ):
        return stripped
    raise PlateError("Unrecognised plate format")


def detect_plate_type(raw: str) -> PlateType:
    """Return the best-matching :class:`PlateType` for ``raw``.

    Raises :class:`PlateError` if nothing matches.
    """
    stripped = normalize_plate(raw)
    if _STANDARD_RE.match(stripped):
        return PlateType.STANDARD
    if _LEGAL_RE.match(stripped):
        return PlateType.LEGAL
    return PlateType.OTHER


def validate_plate_type(raw: str, expected: PlateType) -> str:
    """Normalise + require the plate to match ``expected``.

    Returns the normalised plate on success.
    """
    stripped = normalize_plate(raw)
    actual = detect_plate_type(stripped)
    # STANDARD and LEGAL are stricter — if caller insisted on one but the
    # shape is different, reject. ``other`` accepts anything normalisable.
    if expected in (PlateType.STANDARD, PlateType.LEGAL) and actual != expected:
        raise PlateError(
            f"Plate does not match expected '{expected.value}' format"
        )
    return stripped


# ---------------------------------------------------------------------------
# VIN and tech-passport (kept here so all vehicle identifiers live together)
# ---------------------------------------------------------------------------
# VIN is either the standard 17-char ISO 3779 form or a 12-char short form
# we encounter on locally-imported vehicles. Both exclude I, O and Q.
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{12}$|^[A-HJ-NPR-Z0-9]{17}$")
# Uzbek tech passport: loose check — 8 chars, digits+letters
_TECH_PASSPORT_RE = re.compile(r"^[A-Z0-9]{6,10}$")


def validate_vin(raw: Optional[str]) -> Optional[str]:
    if raw is None or not str(raw).strip():
        return None
    stripped = _strip(str(raw))
    if not _VIN_RE.match(stripped):
        raise PlateError("VIN must be 12 or 17 alnum characters (no I/O/Q)")
    return stripped


def validate_tech_passport(raw: Optional[str]) -> Optional[str]:
    if raw is None or not str(raw).strip():
        return None
    stripped = _strip(str(raw))
    if not _TECH_PASSPORT_RE.match(stripped):
        raise PlateError("Tech passport must be 6-10 alnum characters")
    return stripped

"""Phone number utilities.

All phones stored in the DB are E.164 strings (``+998XXXXXXXXX``). Input from
users arrives in every conceivable format (``+998 90 123-45-67``, ``0901234567``,
``+99890 1234567``, …) — we normalise once at the API boundary and never
re-parse.

``normalize_phone`` raises :class:`PhoneError` (a :class:`ValueError` subclass)
on invalid input. Inside pydantic validators a :class:`ValueError` is caught
and surfaced as a 422 field error automatically.
"""

from __future__ import annotations

import phonenumbers

UZ_REGION = "UZ"


class PhoneError(ValueError):
    """Raised by :func:`normalize_phone` on malformed input."""


def normalize_phone(raw: str) -> str:
    """Return E.164 (e.g. ``+998901234567``).

    Raises :class:`PhoneError` on missing/invalid input.
    """
    if raw is None or not str(raw).strip():
        raise PhoneError("Phone number is required")
    try:
        parsed = phonenumbers.parse(str(raw), UZ_REGION)
    except phonenumbers.NumberParseException as exc:
        raise PhoneError("Invalid phone number format") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise PhoneError("Invalid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def is_valid_phone(raw: str) -> bool:
    try:
        normalize_phone(raw)
    except PhoneError:
        return False
    return True

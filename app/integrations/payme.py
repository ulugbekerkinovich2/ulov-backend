"""Payme Merchant API adapter.

Payme posts a JSON-RPC body and authenticates with HTTP Basic — username is
``Paycom`` (test) or the merchant id (prod), password is the merchant secret
key. The methods we handle:

  * ``CheckPerformTransaction`` — Payme asks if the order can be paid.
  * ``CreateTransaction``       — start a transaction; returns a Payme
                                  ``transaction`` id we persist.
  * ``PerformTransaction``      — finalise (mark paid).
  * ``CancelTransaction``       — refund / cancel.
  * ``CheckTransaction``        — Payme polls status.

Errors use Payme's structured error envelope with negative ``code``s the
spec mandates. We **never** return HTTP 4xx/5xx for protocol-level errors —
Payme expects ``200 OK`` with ``{"error": {...}}`` in the body.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.modules.billing import service as billing_svc
from app.modules.billing.models import Payment

log = get_logger(__name__)


# Payme protocol error codes (subset).
ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_INVALID_ACCOUNT = -31050  # we use this for unknown payment_id
ERR_UNAUTHORIZED = -32504


def _err(code: int, message: str, data: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "code": code,
        "message": {"uz": message, "ru": message, "en": message},
    }
    if data is not None:
        body["data"] = data
    return {"error": body}


def verify_basic_auth(header: Optional[str]) -> bool:
    """Return ``True`` when ``Authorization: Basic ...`` matches the
    configured merchant credentials.

    Test mode allows username ``Paycom``; prod requires the merchant id.
    """
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    if ":" not in raw:
        return False
    username, password = raw.split(":", 1)
    if password != settings.PAYME_SECRET or not settings.PAYME_SECRET:
        return False
    if settings.PAYME_TEST_MODE and username == "Paycom":
        return True
    return username == settings.PAYME_MERCHANT_ID


# ---------------------------------------------------------------------------
# Method dispatch
# ---------------------------------------------------------------------------
def _payment_id_from_account(params: Dict[str, Any]) -> Optional[UUID]:
    account = params.get("account") or {}
    raw = account.get("payment_id") or account.get("order_id")
    if raw is None:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def _load_payment(db: Session, payment_id: Optional[UUID]) -> Optional[Payment]:
    if payment_id is None:
        return None
    from sqlalchemy import select

    return db.execute(
        select(Payment).where(Payment.id == payment_id)
    ).scalar_one_or_none()


def _check_perform(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    payment = _load_payment(db, _payment_id_from_account(params))
    if payment is None:
        return _err(ERR_INVALID_ACCOUNT, "payment_id not found", "payment_id")
    if int(params.get("amount") or 0) != int(payment.amount):
        return _err(ERR_INVALID_AMOUNT, "amount mismatch")
    if payment.status not in {"pending"}:
        return _err(ERR_INVALID_ACCOUNT, "payment already finalised", "payment_id")
    return {"result": {"allow": True}}


def _create_transaction(
    db: Session, params: Dict[str, Any]
) -> Dict[str, Any]:
    payment = _load_payment(db, _payment_id_from_account(params))
    if payment is None:
        return _err(ERR_INVALID_ACCOUNT, "payment_id not found", "payment_id")
    if int(params.get("amount") or 0) != int(payment.amount):
        return _err(ERR_INVALID_AMOUNT, "amount mismatch")

    payme_id = str(params.get("id") or "")
    if not payme_id:
        return _err(ERR_TRANSACTION_NOT_FOUND, "transaction id required")

    # Idempotent: a duplicate Create for the same Payme txn returns the same
    # state without flipping status.
    if payment.external_ref and payment.external_ref != payme_id:
        return _err(ERR_INVALID_ACCOUNT, "transaction already attached")
    if not payment.external_ref:
        payment.external_ref = payme_id
        db.flush()

    return {
        "result": {
            "create_time": int(params.get("time") or 0),
            "transaction": str(payment.id),
            "state": 1,  # 1 = created/pending in Payme's vocabulary
        }
    }


def _perform_transaction(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = str(params.get("id") or "")
    if not payme_id:
        return _err(ERR_TRANSACTION_NOT_FOUND, "transaction id required")

    from sqlalchemy import select

    payment = db.execute(
        select(Payment).where(Payment.external_ref == payme_id)
    ).scalar_one_or_none()
    if payment is None:
        return _err(ERR_TRANSACTION_NOT_FOUND, "transaction not found")

    billing_svc.apply_webhook(
        db,
        payment_id=payment.id,
        external_ref=payme_id,
        status="paid",
    )
    return {
        "result": {
            "transaction": str(payment.id),
            "perform_time": int(params.get("time") or 0),
            "state": 2,  # 2 = performed
        }
    }


def _cancel_transaction(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = str(params.get("id") or "")
    from sqlalchemy import select

    payment = db.execute(
        select(Payment).where(Payment.external_ref == payme_id)
    ).scalar_one_or_none()
    if payment is None:
        return _err(ERR_TRANSACTION_NOT_FOUND, "transaction not found")

    billing_svc.apply_webhook(
        db,
        payment_id=payment.id,
        external_ref=payme_id,
        status="failed",
    )
    return {
        "result": {
            "transaction": str(payment.id),
            "cancel_time": int(params.get("time") or 0),
            "state": -2,  # -2 = cancelled after perform
        }
    }


def _check_transaction(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    payme_id = str(params.get("id") or "")
    from sqlalchemy import select

    payment = db.execute(
        select(Payment).where(Payment.external_ref == payme_id)
    ).scalar_one_or_none()
    if payment is None:
        return _err(ERR_TRANSACTION_NOT_FOUND, "transaction not found")

    state = {
        "pending": 1,
        "paid": 2,
        "failed": -2,
        "refunded": -2,
    }.get(payment.status, 1)
    return {
        "result": {
            "transaction": str(payment.id),
            "state": state,
        }
    }


METHODS = {
    "CheckPerformTransaction": _check_perform,
    "CreateTransaction": _create_transaction,
    "PerformTransaction": _perform_transaction,
    "CancelTransaction": _cancel_transaction,
    "CheckTransaction": _check_transaction,
}


def dispatch(
    db: Session, body: Dict[str, Any], *, authorization: Optional[str]
) -> Dict[str, Any]:
    """Process a Payme JSON-RPC envelope and return the response body.

    The HTTP layer should always reply ``200 OK`` regardless of protocol
    errors — Payme treats non-200 as transport failure and retries.
    """
    rpc_id = body.get("id")

    if not verify_basic_auth(authorization):
        return {**_err(ERR_UNAUTHORIZED, "unauthorized"), "id": rpc_id}

    method = body.get("method")
    params = body.get("params") or {}
    handler = METHODS.get(str(method))
    if handler is None:
        return {
            **_err(ERR_TRANSACTION_NOT_FOUND, f"unknown method {method}"),
            "id": rpc_id,
        }

    out = handler(db, params)
    out["id"] = rpc_id
    log.info("payme_rpc", method=method, has_error="error" in out)
    return out


# Tuple kept for backwards-compat helper imports.
def parse_basic(header: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not header or not header.lower().startswith("basic "):
        return None, None
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None, None
    if ":" not in raw:
        return None, None
    u, p = raw.split(":", 1)
    return u, p

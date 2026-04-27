"""Click Merchant API adapter.

Click sends two consecutive form-encoded callbacks for every transaction:

  * ``action=0`` — Prepare. Validate the order and return a
    ``merchant_prepare_id`` we'll see in the next call.
  * ``action=1`` — Complete. Mark the payment paid (or failed if
    ``error != 0``).

The signature is an MD5 hash of:
    f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}"
    f"{merchant_prepare_id?}{amount}{action}{sign_time}"

We keep the adapter pure — the HTTP router posts the form payload to
``handle()`` and surfaces whatever the adapter returns as JSON.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging import get_logger
from app.modules.billing import service as billing_svc
from app.modules.billing.models import Payment

log = get_logger(__name__)

# Click error codes (subset).
ERR_OK = 0
ERR_SIGN_CHECK_FAILED = -1
ERR_INCORRECT_AMOUNT = -2
ERR_ACTION_NOT_FOUND = -3
ERR_TRANS_CANCELLED = -9
ERR_USER_NOT_FOUND = -5
ERR_TRANS_DOES_NOT_EXIST = -6
ERR_TRANS_ALREADY_PAID = -4

ACTION_PREPARE = 0
ACTION_COMPLETE = 1


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def verify_signature(form: Dict[str, Any]) -> bool:
    expected_signature = form.get("sign_string")
    if not expected_signature or not settings.CLICK_SECRET_KEY:
        return False
    parts = [
        str(form.get("click_trans_id", "")),
        str(form.get("service_id", "")),
        settings.CLICK_SECRET_KEY,
        str(form.get("merchant_trans_id", "")),
    ]
    if str(form.get("action")) == str(ACTION_COMPLETE):
        parts.append(str(form.get("merchant_prepare_id", "")))
    parts.append(str(form.get("amount", "")))
    parts.append(str(form.get("action", "")))
    parts.append(str(form.get("sign_time", "")))
    expected = _md5("".join(parts))
    return expected == expected_signature


def _err(payment: Optional[Payment], code: int, note: str) -> Dict[str, Any]:
    return {
        "click_trans_id": None,
        "merchant_trans_id": str(payment.id) if payment else None,
        "merchant_prepare_id": None,
        "error": code,
        "error_note": note,
    }


def _load_payment(db: Session, merchant_trans_id: str) -> Optional[Payment]:
    try:
        pid = UUID(merchant_trans_id)
    except (TypeError, ValueError):
        return None
    return db.execute(select(Payment).where(Payment.id == pid)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------
def _prepare(db: Session, form: Dict[str, Any]) -> Dict[str, Any]:
    payment = _load_payment(db, str(form.get("merchant_trans_id", "")))
    if payment is None:
        return _err(None, ERR_USER_NOT_FOUND, "payment not found")
    if int(form.get("amount", 0)) != int(payment.amount // 100):
        # Click amount is in soum (UZS); our `amount` is tiyin (×100).
        return _err(payment, ERR_INCORRECT_AMOUNT, "amount mismatch")
    if payment.status != "pending":
        return _err(payment, ERR_TRANS_ALREADY_PAID, "already finalised")

    return {
        "click_trans_id": form.get("click_trans_id"),
        "merchant_trans_id": str(payment.id),
        "merchant_prepare_id": str(payment.id),
        "error": ERR_OK,
        "error_note": "Success",
    }


def _complete(db: Session, form: Dict[str, Any]) -> Dict[str, Any]:
    payment = _load_payment(db, str(form.get("merchant_trans_id", "")))
    if payment is None:
        return _err(None, ERR_USER_NOT_FOUND, "payment not found")

    incoming_error = int(form.get("error", 0))
    status = "paid" if incoming_error == 0 else "failed"

    billing_svc.apply_webhook(
        db,
        payment_id=payment.id,
        external_ref=str(form.get("click_trans_id", "")),
        status=status,
    )
    return {
        "click_trans_id": form.get("click_trans_id"),
        "merchant_trans_id": str(payment.id),
        "merchant_confirm_id": str(payment.id),
        "error": ERR_OK if status == "paid" else ERR_TRANS_CANCELLED,
        "error_note": "Success" if status == "paid" else "Cancelled",
    }


def handle(db: Session, form: Dict[str, Any]) -> Dict[str, Any]:
    if not verify_signature(form):
        return _err(None, ERR_SIGN_CHECK_FAILED, "sign check failed")
    action = str(form.get("action"))
    if action == str(ACTION_PREPARE):
        return _prepare(db, form)
    if action == str(ACTION_COMPLETE):
        return _complete(db, form)
    return _err(None, ERR_ACTION_NOT_FOUND, f"unknown action {action}")

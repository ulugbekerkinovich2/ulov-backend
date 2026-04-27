"""Billing domain logic.

Two flows live here:

  * **Checkout** — owner buys / renews a subscription. We mint a pending
    ``Payment`` row and (Phase 7) hand back a provider redirect URL.

  * **Webhook** — provider POSTs the payment outcome. We flip the row to
    ``paid`` (or ``failed``), stamp ``paid_at``, and on success extend the
    centre's ``subscription_until`` by the plan's duration.

Webhook handling is **idempotent**: providers retry on failure, so we use
``external_ref`` uniqueness to swallow duplicates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.deps import CurrentUser
from app.modules.billing.models import Payment, SubscriptionPlan
from app.modules.notifications import service as notifs
from app.modules.service_centers import repository as centers_repo

UUIDLike = Union[UUID, str]
log = get_logger(__name__)


def _get_plan(db: Session, code: str) -> SubscriptionPlan:
    p = db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.code == code)
        .where(SubscriptionPlan.active.is_(True))
    ).scalar_one_or_none()
    if p is None:
        raise NotFoundError("Plan not found", code="BILLING_PLAN_NOT_FOUND")
    return p


def checkout_subscription(
    db: Session,
    user: CurrentUser,
    *,
    plan_code: str,
    center_id: UUIDLike,
    provider: str,
) -> Payment:
    center = centers_repo.get_by_id(db, center_id)
    if center is None:
        raise NotFoundError("Centre not found", code="CENTER_NOT_FOUND")
    if user.role != "admin" and str(center.owner_user_id) != str(user.id):
        raise ForbiddenError("Not your centre", code="CENTER_NOT_OWNER")

    plan = _get_plan(db, plan_code)
    payment = Payment(
        user_id=user.id,
        kind="subscription",
        target_id=center.id,
        plan_id=plan.id,
        amount=plan.monthly_price,
        provider=provider,
        status="pending",
    )
    db.add(payment)
    db.flush()
    log.info(
        "billing_checkout_created",
        payment_id=str(payment.id),
        plan=plan_code,
        center_id=str(center.id),
        provider=provider,
        amount=plan.monthly_price,
    )
    return payment


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def apply_webhook(
    db: Session,
    *,
    payment_id: UUIDLike,
    external_ref: str,
    status: str,
) -> Payment:
    payment = db.execute(
        select(Payment).where(Payment.id == payment_id)
    ).scalar_one_or_none()
    if payment is None:
        raise NotFoundError("Payment not found", code="BILLING_PAYMENT_NOT_FOUND")

    # Idempotent: a duplicate delivery for an already-finalised payment is a
    # no-op and we return the row as-is. We also treat repeated delivery of
    # the same external_ref on a pending payment as a no-op.
    if payment.status in {"paid", "refunded"}:
        return payment
    if payment.status == "failed" and status == "failed":
        return payment

    if payment.external_ref and payment.external_ref != external_ref:
        raise ConflictError(
            "external_ref mismatch", code="BILLING_REF_MISMATCH"
        )

    payment.status = status
    payment.external_ref = external_ref
    if status == "paid":
        payment.paid_at = _utcnow()

    if status == "paid" and payment.kind == "subscription":
        center = centers_repo.get_by_id(db, payment.target_id)
        if center is not None and payment.plan_id:
            plan = db.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == payment.plan_id)
            ).scalar_one_or_none()
            duration = plan.duration_days if plan else 30
            until = _utcnow() + timedelta(days=duration)
            centers_repo.update_fields(
                db,
                center.id,
                subscription_plan_id=payment.plan_id,
                subscription_until=until.isoformat(),
            )

    db.flush()

    if status == "paid":
        notifs.create_notification(
            db,
            user_id=payment.user_id,
            kind="billing.paid",
            title="To‘lov muvaffaqiyatli",
            body=f"To‘lov #{str(payment.id)[:8]} qabul qilindi.",
            payload={
                "payment_id": str(payment.id),
                "amount": payment.amount,
                "kind": payment.kind,
            },
        )
    log.info(
        "billing_webhook_applied",
        payment_id=str(payment.id),
        status=status,
        external_ref=external_ref,
    )
    return payment

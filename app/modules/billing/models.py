"""Billing — subscription plans + payment intents.

A ``SubscriptionPlan`` is reference data (admin-managed). A ``Payment`` is
an intent created by a centre owner; the provider's webhook flips it to
``paid`` and records the external reference. We keep the payment table
provider-agnostic — Payme/Click/Stripe land in the same table differing
only by ``provider``.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, UUIDMixin

PAYMENT_PROVIDER_VALUES = ("payme", "click", "stripe", "manual")
PAYMENT_KIND_VALUES = ("subscription", "insurance", "service")

# ``payment_status`` enum is shared with the insurance module (Phase 5).
# We re-bind here without ``create_type`` so neither migration nor model
# create_all emits a duplicate ``CREATE TYPE``.

payment_status_enum = PG_ENUM(
    "pending", "paid", "failed", "refunded",
    name="payment_status",
    create_type=False,
)
payment_provider_enum = PG_ENUM(
    *PAYMENT_PROVIDER_VALUES, name="payment_provider", create_type=True
)
payment_kind_enum = PG_ENUM(
    *PAYMENT_KIND_VALUES, name="payment_kind", create_type=True
)


class SubscriptionPlan(UUIDMixin, Base):
    __tablename__ = "subscription_plans"

    code = Column(String(64), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    monthly_price = Column(BigInteger, nullable=False)  # tiyin
    duration_days = Column(Integer, nullable=False, server_default=text("30"))
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Payment(UUIDMixin, Base):
    __tablename__ = "payments"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(payment_kind_enum, nullable=False)
    # When ``kind="subscription"``, ``target_id`` is the centre id; when
    # ``kind="insurance"``, the insurance_policies row; when ``kind="service"``
    # it points at services.id. Polymorphic — no FK enforced.
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount = Column(BigInteger, nullable=False)  # tiyin
    provider = Column(payment_provider_enum, nullable=False)
    status = Column(
        payment_status_enum, nullable=False, server_default="pending"
    )
    external_ref = Column(String(255), nullable=True, unique=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    paid_at = Column(DateTime(timezone=True), nullable=True)

"""Insurance tariffs + customer policies.

A ``Tariff`` is a reference catalogue row (admin-managed). A ``Policy`` is
the customer's purchased contract referencing a tariff and a car.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.base import Base, UUIDMixin

PAYMENT_STATUS_VALUES = ("pending", "paid", "failed", "refunded")

payment_status_enum = PG_ENUM(
    *PAYMENT_STATUS_VALUES, name="payment_status", create_type=True
)


class InsuranceCompany(UUIDMixin, Base):
    __tablename__ = "insurance_companies"

    name = Column(String(255), nullable=False)
    rating = Column(BigInteger, nullable=False, server_default="0")
    reviews_count = Column(BigInteger, nullable=False, server_default="0")
    logo_url = Column(String(512), nullable=True)
    base_price = Column(BigInteger, nullable=False)
    perks = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InsuranceTariff(UUIDMixin, Base):
    __tablename__ = "insurance_tariffs"

    code = Column(String(64), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    base_price = Column(BigInteger, nullable=False)  # tiyin
    coefficients = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InsurancePolicy(UUIDMixin, Base):
    __tablename__ = "insurance_policies"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tariff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("insurance_tariffs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("insurance_companies.id", ondelete="RESTRICT"),
        nullable=True, # For backward compat or if only tariff matters
    )
    price = Column(BigInteger, nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    payment_status = Column(
        payment_status_enum, nullable=False, server_default="pending"
    )
    payment_provider = Column(String(32), nullable=True)
    external_ref = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

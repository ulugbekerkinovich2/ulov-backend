"""Services + items + transitions + condition images.

This is the ERP heart: a single ``Service`` row tracks a vehicle through the
state machine waiting → in_progress → paused → completed (or cancelled).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, UUIDMixin

SERVICE_STATUS_VALUES = ("waiting", "in_progress", "paused", "completed", "cancelled")
CONDITION_IMAGE_STAGE_VALUES = ("before", "during", "after")

service_status_enum = PG_ENUM(
    *SERVICE_STATUS_VALUES, name="service_status", create_type=True
)
condition_image_stage_enum = PG_ENUM(
    *CONDITION_IMAGE_STAGE_VALUES, name="condition_image_stage", create_type=True
)


class Service(UUIDMixin, Base):
    __tablename__ = "services"

    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    center_id = Column(
        UUID(as_uuid=True),
        ForeignKey("service_centers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    mechanic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mechanics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships used by routers to enrich the response with nested
    # car / centre / mechanic objects without N+1 round-trips.
    car = relationship("Car", lazy="joined")
    center = relationship("ServiceCenter", lazy="joined")
    mechanic = relationship("Mechanic", lazy="joined")

    status = Column(service_status_enum, nullable=False, server_default="waiting")

    mileage_at_intake = Column(Integer, nullable=False)
    next_recommended_mileage = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    paused_elapsed_s = Column(
        Integer, nullable=False, server_default=text("0")
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_reason = Column(String(500), nullable=True)
    pause_reason = Column(String(500), nullable=True)

    deleted_at = Column(DateTime(timezone=True), nullable=True)


class ServiceItem(UUIDMixin, Base):
    """Inline line items on a service — labour + parts."""

    __tablename__ = "service_items"

    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_type = Column(String(64), nullable=False)
    parts = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    notes = Column(Text, nullable=True)

    # Prices in tiyin (1 UZS == 100 tiyin) — BigInteger to avoid overflow.
    service_price = Column(BigInteger, nullable=False, server_default=text("0"))
    parts_price = Column(BigInteger, nullable=False, server_default=text("0"))

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ServiceTransition(UUIDMixin, Base):
    """Append-only audit of every state change."""

    __tablename__ = "service_transitions"

    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status = Column(service_status_enum, nullable=True)
    to_status = Column(service_status_enum, nullable=False)
    by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = Column(String(500), nullable=True)
    at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConditionImage(UUIDMixin, Base):
    """Photographs taken before/during/after work — immutable evidence."""

    __tablename__ = "condition_images"

    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url = Column(String(500), nullable=False)
    stage = Column(condition_image_stage_enum, nullable=False)
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

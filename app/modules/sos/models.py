"""SOS providers + request log."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, UUIDMixin

SOS_CATEGORY_VALUES = ("tow", "roadside", "fuel", "ambulance", "police")
SOS_REQUEST_STATUS_VALUES = ("requested", "dispatched", "completed", "cancelled")

sos_category_enum = PG_ENUM(
    *SOS_CATEGORY_VALUES, name="sos_category", create_type=True
)
sos_request_status_enum = PG_ENUM(
    *SOS_REQUEST_STATUS_VALUES, name="sos_request_status", create_type=True
)


class SosProvider(UUIDMixin, Base):
    __tablename__ = "sos_providers"

    category = Column(sos_category_enum, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    city = Column(String(100), nullable=True, index=True)
    available_24_7 = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SosRequest(UUIDMixin, Base):
    __tablename__ = "sos_requests"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sos_providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(
        sos_request_status_enum, nullable=False, server_default="requested"
    )
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    note = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

"""Trips + GPS points.

A ``Trip`` is started by the customer, accumulates GPS points until they
finalise it. We keep the schema minimal: distance/duration/avg_speed are
computed on finish from the points.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base, UUIDMixin


class Trip(UUIDMixin, Base):
    __tablename__ = "trips"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    started_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at = Column(DateTime(timezone=True), nullable=True)

    distance_km = Column(Numeric(10, 3), nullable=False, server_default=text("0"))
    duration_s = Column(Integer, nullable=False, server_default=text("0"))
    avg_speed = Column(Numeric(6, 2), nullable=False, server_default=text("0"))
    fuel_l_est = Column(Numeric(8, 3), nullable=False, server_default=text("0"))

    polyline = Column(Text, nullable=True)


class TripPoint(UUIDMixin, Base):
    __tablename__ = "trip_points"

    trip_id = Column(
        UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    ts = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

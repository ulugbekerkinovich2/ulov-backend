"""Fuel stations — geolocated, with a per-fuel-type price map."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base, UUIDMixin


class FuelStation(UUIDMixin, Base):
    __tablename__ = "fuel_stations"

    name = Column(String(255), nullable=False)
    brand = Column(String(64), nullable=True)
    address = Column(String(500), nullable=False)
    location = Column(
        JSONB, nullable=False
    )
    # prices = {"ai92": 12000, "ai95": 13500, "diesel": 11000, ...}; tiyin
    prices = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

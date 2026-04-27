"""Cars + mileage readings.

A ``Car`` is owned by one customer (``owner_id``) and may pass through many
service centres over time (via the ``services`` table, Phase 3).
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

PLATE_TYPE_VALUES = ("standard", "legal", "other")
MILEAGE_SOURCE_VALUES = ("user", "service")

plate_type_enum = PG_ENUM(
    *PLATE_TYPE_VALUES,
    name="plate_type",
    create_type=True,
)
mileage_source_enum = PG_ENUM(
    *MILEAGE_SOURCE_VALUES,
    name="mileage_source",
    create_type=True,
)


class Car(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "cars"

    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner = relationship("User", lazy="joined")

    brand = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    year = Column(SmallInteger, nullable=False)
    color = Column(String(32), nullable=True)

    # Plate stored without spaces; display formatting is a client concern.
    plate = Column(String(15), nullable=False, unique=True)
    plate_type = Column(plate_type_enum, nullable=False)

    # Mileage in whole km — enough for any realistic number.
    mileage = Column(Integer, nullable=False, server_default=text("0"))

    vin = Column(String(17), nullable=True, unique=True)
    tech_passport = Column(String(10), nullable=True)

    # Insurance + tinting policies are date pairs; NULL means "not tracked".
    insurance_from = Column(Date, nullable=True)
    insurance_to = Column(Date, nullable=True)
    insurance_company = Column(String(100), nullable=True)
    tint_from = Column(Date, nullable=True)
    tint_to = Column(Date, nullable=True)

    photo_url = Column(String(500), nullable=True)


class MileageReading(UUIDMixin, Base):
    """Append-only history of mileage observations.

    Every time a ``Car.mileage`` is updated, a row is appended here with the
    source (user self-report vs. recorded at service intake). Enables
    correct "km driven this month" analytics without querying transaction
    logs.
    """

    __tablename__ = "mileage_readings"

    car_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value = Column(Integer, nullable=False)
    source = Column(mileage_source_enum, nullable=False, server_default="user")
    recorded_at = Column(
        BigInteger,
        nullable=False,
        # We store epoch ms here so ordering is trivial across time zones.
        # DB default = now() in ms.
        server_default=text("(EXTRACT(EPOCH FROM now()) * 1000)::bigint"),
    )

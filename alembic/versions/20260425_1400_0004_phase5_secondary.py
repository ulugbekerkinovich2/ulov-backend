"""phase 5 secondary — trips, sos, fuel_stations, insurance

Revision ID: 0004_phase5_secondary
Revises: 0003_phase3_erp
Create Date: 2026-04-25 14:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
# from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase5_secondary"
down_revision: Union[str, None] = "0003_phase3_erp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOS_CATEGORY_VALUES = ("tow", "roadside", "fuel", "ambulance", "police")
SOS_REQUEST_STATUS_VALUES = ("requested", "dispatched", "completed", "cancelled")
PAYMENT_STATUS_VALUES = ("pending", "paid", "failed", "refunded")


def _create_enum(name: str, values) -> None:
    enum = postgresql.ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(name: str) -> None:
    postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    _create_enum("sos_category", SOS_CATEGORY_VALUES)
    _create_enum("sos_request_status", SOS_REQUEST_STATUS_VALUES)
    _create_enum("payment_status", PAYMENT_STATUS_VALUES)

    # ---- trips -----------------------------------------------------------
    op.create_table(
        "trips",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("car_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "distance_km",
            sa.Numeric(10, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "duration_s", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "avg_speed",
            sa.Numeric(6, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "fuel_l_est",
            sa.Numeric(8, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("polyline", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_trips_user"
        ),
        sa.ForeignKeyConstraint(
            ["car_id"], ["cars.id"], ondelete="SET NULL", name="fk_trips_car"
        ),
    )
    op.create_index("ix_trips_user_id", "trips", ["user_id"])
    op.create_index("ix_trips_car_id", "trips", ["car_id"])

    op.create_table(
        "trip_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["trip_id"], ["trips.id"], ondelete="CASCADE", name="fk_trip_points_trip"
        ),
    )
    op.create_index("ix_trip_points_trip_id", "trip_points", ["trip_id"])

    # ---- sos -------------------------------------------------------------
    op.create_table(
        "sos_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                *SOS_CATEGORY_VALUES, name="sos_category", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column(
            "available_24_7",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sos_providers_category", "sos_providers", ["category"])
    op.create_index("ix_sos_providers_city", "sos_providers", ["city"])

    op.create_table(
        "sos_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *SOS_REQUEST_STATUS_VALUES,
                name="sos_request_status",
                create_type=False,
            ),
            nullable=False,
            server_default="requested",
        ),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_sos_requests_user"
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["sos_providers.id"],
            ondelete="SET NULL",
            name="fk_sos_requests_provider",
        ),
    )
    op.create_index("ix_sos_requests_user_id", "sos_requests", ["user_id"])

    # ---- fuel_stations ---------------------------------------------------
    op.create_table(
        "fuel_stations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column(
            "location",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "prices",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # op.execute(
    #     "CREATE INDEX ix_fuel_stations_location ON fuel_stations USING gist(location)"
    # )

    # ---- insurance -------------------------------------------------------
    op.create_table(
        "insurance_tariffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_price", sa.BigInteger(), nullable=False),
        sa.Column(
            "coefficients",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_insurance_tariffs_code"),
    )

    op.create_table(
        "insurance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("car_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tariff_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column(
            "payment_status",
            postgresql.ENUM(
                *PAYMENT_STATUS_VALUES, name="payment_status", create_type=False
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payment_provider", sa.String(length=32), nullable=True),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_insurance_policies_user",
        ),
        sa.ForeignKeyConstraint(
            ["car_id"],
            ["cars.id"],
            ondelete="RESTRICT",
            name="fk_insurance_policies_car",
        ),
        sa.ForeignKeyConstraint(
            ["tariff_id"],
            ["insurance_tariffs.id"],
            ondelete="RESTRICT",
            name="fk_insurance_policies_tariff",
        ),
    )
    op.create_index(
        "ix_insurance_policies_user_id", "insurance_policies", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_insurance_policies_user_id", table_name="insurance_policies")
    op.drop_table("insurance_policies")
    op.drop_table("insurance_tariffs")

    op.execute("DROP INDEX IF EXISTS ix_fuel_stations_location")
    op.drop_table("fuel_stations")

    op.drop_index("ix_sos_requests_user_id", table_name="sos_requests")
    op.drop_table("sos_requests")
    op.drop_index("ix_sos_providers_city", table_name="sos_providers")
    op.drop_index("ix_sos_providers_category", table_name="sos_providers")
    op.drop_table("sos_providers")

    op.drop_index("ix_trip_points_trip_id", table_name="trip_points")
    op.drop_table("trip_points")
    op.drop_index("ix_trips_car_id", table_name="trips")
    op.drop_index("ix_trips_user_id", table_name="trips")
    op.drop_table("trips")

    _drop_enum("payment_status")
    _drop_enum("sos_request_status")
    _drop_enum("sos_category")

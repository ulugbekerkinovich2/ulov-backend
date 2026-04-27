"""customer core — cars, mileage_readings, reviews, content_pages, notifications, devices

Revision ID: 0002_customer_core
Revises: 0001_initial_auth
Create Date: 2026-04-24 13:00:00

Five new domains wired in one migration. Foreign keys to ``centers`` /
``services`` are intentionally omitted — those tables land in the Phase 3
migration which adds the constraints retroactively.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_customer_core"
down_revision: Union[str, None] = "0001_initial_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLATE_TYPE_VALUES = ("standard", "legal", "other")
MILEAGE_SOURCE_VALUES = ("user", "service")
CONTENT_KINDS = ("traffic_rules", "road_signs", "fines", "tips")
DEVICE_PLATFORM_VALUES = ("ios", "android", "web")


def _create_enum(name: str, values) -> None:
    enum = postgresql.ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(name: str) -> None:
    postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    # ---- Enums ------------------------------------------------------------
    _create_enum("plate_type", PLATE_TYPE_VALUES)
    _create_enum("mileage_source", MILEAGE_SOURCE_VALUES)
    _create_enum("content_kind", CONTENT_KINDS)
    _create_enum("device_platform", DEVICE_PLATFORM_VALUES)

    # ---- Cars -------------------------------------------------------------
    op.create_table(
        "cars",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("plate", sa.String(length=15), nullable=False),
        sa.Column(
            "plate_type",
            postgresql.ENUM(
                *PLATE_TYPE_VALUES, name="plate_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "mileage",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("tech_passport", sa.String(length=10), nullable=True),
        sa.Column("insurance_from", sa.Date(), nullable=True),
        sa.Column("insurance_to", sa.Date(), nullable=True),
        sa.Column("insurance_company", sa.String(length=100), nullable=True),
        sa.Column("tint_from", sa.Date(), nullable=True),
        sa.Column("tint_to", sa.Date(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="CASCADE",
            name="fk_cars_owner",
        ),
        sa.UniqueConstraint("plate", name="uq_cars_plate"),
        sa.UniqueConstraint("vin", name="uq_cars_vin"),
    )
    op.create_index("ix_cars_owner_id", "cars", ["owner_id"])

    # ---- Mileage readings -------------------------------------------------
    op.create_table(
        "mileage_readings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("car_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM(
                *MILEAGE_SOURCE_VALUES, name="mileage_source", create_type=False
            ),
            nullable=False,
            server_default="user",
        ),
        sa.Column(
            "recorded_at",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text(
                "(EXTRACT(EPOCH FROM now()) * 1000)::bigint"
            ),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["car_id"], ["cars.id"], ondelete="CASCADE",
            name="fk_mileage_car",
        ),
    )
    op.create_index(
        "ix_mileage_readings_car_id", "mileage_readings", ["car_id"]
    )
    op.create_index(
        "ix_mileage_readings_recorded_at",
        "mileage_readings",
        ["car_id", "recorded_at"],
    )

    # ---- Reviews ----------------------------------------------------------
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # FK to centers added in Phase 3 migration.
        sa.Column("center_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("reply_at", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_reviews_user",
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
    )
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_center_id", "reviews", ["center_id"])

    # ---- Content pages ----------------------------------------------------
    op.create_table(
        "content_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                *CONTENT_KINDS, name="content_kind", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("lang", sa.String(length=2), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
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
        sa.UniqueConstraint(
            "kind", "lang", "slug", name="uq_content_pages_kind_lang_slug"
        ),
    )
    op.create_index("ix_content_pages_kind", "content_pages", ["kind"])

    # ---- Notifications ----------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_notifications_user",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index(
        "ix_notifications_read_at", "notifications", ["user_id", "read_at"]
    )

    # ---- Devices ----------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=500), nullable=False),
        sa.Column(
            "platform",
            postgresql.ENUM(
                *DEVICE_PLATFORM_VALUES,
                name="device_platform",
                create_type=False,
            ),
            nullable=False,
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
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_devices_user",
        ),
        sa.UniqueConstraint("user_id", "token", name="uq_devices_user_token"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_table("devices")

    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_kind", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_content_pages_kind", table_name="content_pages")
    op.drop_table("content_pages")

    op.drop_index("ix_reviews_center_id", table_name="reviews")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index(
        "ix_mileage_readings_recorded_at", table_name="mileage_readings"
    )
    op.drop_index("ix_mileage_readings_car_id", table_name="mileage_readings")
    op.drop_table("mileage_readings")

    op.drop_index("ix_cars_owner_id", table_name="cars")
    op.drop_table("cars")

    _drop_enum("device_platform")
    _drop_enum("content_kind")
    _drop_enum("mileage_source")
    _drop_enum("plate_type")

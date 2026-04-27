"""phase 3 erp — service_centers, mechanics, services, items, transitions, condition_images

Revision ID: 0003_phase3_erp
Revises: 0002_customer_core
Create Date: 2026-04-25 10:00:00

Adds the centre/mechanics/service-state-machine tables and back-fills the FK
constraints on ``reviews`` (center_id, service_id) that were left dangling by
``0002_customer_core``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
# from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3_erp"
down_revision: Union[str, None] = "0002_customer_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SERVICE_STATUS_VALUES = ("waiting", "in_progress", "paused", "completed", "cancelled")
CONDITION_IMAGE_STAGE_VALUES = ("before", "during", "after")


def _create_enum(name: str, values) -> None:
    enum = postgresql.ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(name: str) -> None:
    postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    # ---- Enums ------------------------------------------------------------
    _create_enum("service_status", SERVICE_STATUS_VALUES)
    _create_enum("condition_image_stage", CONDITION_IMAGE_STAGE_VALUES)

    # ---- service_centers --------------------------------------------------
    op.create_table(
        "service_centers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "location",
            postgresql.JSONB(),
            nullable=True,
        ),
        sa.Column(
            "schedule",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "services",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subscription_until", sa.String(length=32), nullable=True),
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
            ["owner_user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_service_centers_owner",
        ),
    )
    op.create_index(
        "ix_service_centers_owner_user_id",
        "service_centers",
        ["owner_user_id"],
    )
    # op.execute(
    #     "CREATE INDEX ix_service_centers_location "
    #     "ON service_centers USING gist(location)"
    # )

    # ---- mechanics --------------------------------------------------------
    op.create_table(
        "mechanics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "service_types",
            postgresql.ARRAY(sa.String(length=64)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["center_id"], ["service_centers.id"], ondelete="CASCADE",
            name="fk_mechanics_center",
        ),
        sa.UniqueConstraint("login", name="uq_mechanics_login"),
    )
    op.create_index("ix_mechanics_center_id", "mechanics", ["center_id"])
    op.execute(
        "CREATE INDEX ix_mechanics_center_active ON mechanics(center_id) "
        "WHERE deleted_at IS NULL"
    )

    # ---- services ---------------------------------------------------------
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("car_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mechanic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                *SERVICE_STATUS_VALUES, name="service_status", create_type=False
            ),
            nullable=False,
            server_default="waiting",
        ),
        sa.Column("mileage_at_intake", sa.Integer(), nullable=False),
        sa.Column("next_recommended_mileage", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "paused_elapsed_s",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("pause_reason", sa.String(length=500), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["car_id"], ["cars.id"], ondelete="RESTRICT",
            name="fk_services_car",
        ),
        sa.ForeignKeyConstraint(
            ["center_id"], ["service_centers.id"], ondelete="RESTRICT",
            name="fk_services_center",
        ),
        sa.ForeignKeyConstraint(
            ["mechanic_id"], ["mechanics.id"], ondelete="SET NULL",
            name="fk_services_mechanic",
        ),
    )
    op.create_index("ix_services_car_id", "services", ["car_id"])
    op.create_index("ix_services_center_id", "services", ["center_id"])
    op.create_index("ix_services_mechanic_id", "services", ["mechanic_id"])
    op.create_index(
        "ix_services_center_status", "services", ["center_id", "status"]
    )

    # ---- service_items ----------------------------------------------------
    op.create_table(
        "service_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_type", sa.String(length=64), nullable=False),
        sa.Column(
            "parts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "service_price",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "parts_price",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], ondelete="CASCADE",
            name="fk_service_items_service",
        ),
    )
    op.create_index("ix_service_items_service_id", "service_items", ["service_id"])

    # ---- service_transitions ---------------------------------------------
    op.create_table(
        "service_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "from_status",
            postgresql.ENUM(
                *SERVICE_STATUS_VALUES, name="service_status", create_type=False
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            postgresql.ENUM(
                *SERVICE_STATUS_VALUES, name="service_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], ondelete="CASCADE",
            name="fk_service_transitions_service",
        ),
        sa.ForeignKeyConstraint(
            ["by_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_service_transitions_user",
        ),
    )
    op.create_index(
        "ix_service_transitions_service_at",
        "service_transitions",
        ["service_id", sa.text("at DESC")],
    )

    # ---- condition_images ------------------------------------------------
    op.create_table(
        "condition_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column(
            "stage",
            postgresql.ENUM(
                *CONDITION_IMAGE_STAGE_VALUES,
                name="condition_image_stage",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], ondelete="CASCADE",
            name="fk_condition_images_service",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], ondelete="SET NULL",
            name="fk_condition_images_user",
        ),
    )
    op.create_index(
        "ix_condition_images_service_id", "condition_images", ["service_id"]
    )

    # ---- Back-fill FKs left dangling by 0001 / 0002 -----------------------
    op.create_foreign_key(
        "fk_users_center",
        "users",
        "service_centers",
        ["center_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reviews_center",
        "reviews",
        "service_centers",
        ["center_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_reviews_service",
        "reviews",
        "services",
        ["service_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reviews_service", "reviews", type_="foreignkey")
    op.drop_constraint("fk_reviews_center", "reviews", type_="foreignkey")
    op.drop_constraint("fk_users_center", "users", type_="foreignkey")

    op.drop_index("ix_condition_images_service_id", table_name="condition_images")
    op.drop_table("condition_images")

    op.drop_index(
        "ix_service_transitions_service_at", table_name="service_transitions"
    )
    op.drop_table("service_transitions")

    op.drop_index("ix_service_items_service_id", table_name="service_items")
    op.drop_table("service_items")

    op.drop_index("ix_services_center_status", table_name="services")
    op.drop_index("ix_services_mechanic_id", table_name="services")
    op.drop_index("ix_services_center_id", table_name="services")
    op.drop_index("ix_services_car_id", table_name="services")
    op.drop_table("services")

    op.execute("DROP INDEX IF EXISTS ix_mechanics_center_active")
    op.drop_index("ix_mechanics_center_id", table_name="mechanics")
    op.drop_table("mechanics")

    op.execute("DROP INDEX IF EXISTS ix_service_centers_location")
    op.drop_index(
        "ix_service_centers_owner_user_id", table_name="service_centers"
    )
    op.drop_table("service_centers")

    _drop_enum("condition_image_stage")
    _drop_enum("service_status")

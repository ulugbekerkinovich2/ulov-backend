"""phase 6 billing — subscription_plans + payments

Revision ID: 0005_phase6_billing
Revises: 0004_phase5_secondary
Create Date: 2026-04-25 16:00:00

Stats module is read-only over Phase 3 tables — no schema change for it.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase6_billing"
down_revision: Union[str, None] = "0004_phase5_secondary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAYMENT_PROVIDER_VALUES = ("payme", "click", "stripe", "manual")
PAYMENT_KIND_VALUES = ("subscription", "insurance", "service")


def _create_enum(name: str, values) -> None:
    enum = postgresql.ENUM(*values, name=name, create_type=False)
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(name: str) -> None:
    postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    _create_enum("payment_provider", PAYMENT_PROVIDER_VALUES)
    _create_enum("payment_kind", PAYMENT_KIND_VALUES)

    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("monthly_price", sa.BigInteger(), nullable=False),
        sa.Column(
            "duration_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
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
        sa.UniqueConstraint("code", name="uq_subscription_plans_code"),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                *PAYMENT_KIND_VALUES, name="payment_kind", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "provider",
            postgresql.ENUM(
                *PAYMENT_PROVIDER_VALUES,
                name="payment_provider",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "paid",
                "failed",
                "refunded",
                name="payment_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("external_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_payments_user"
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["subscription_plans.id"],
            ondelete="SET NULL",
            name="fk_payments_plan",
        ),
        sa.UniqueConstraint("external_ref", name="uq_payments_external_ref"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_target_id", "payments", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_payments_target_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("subscription_plans")

    _drop_enum("payment_kind")
    _drop_enum("payment_provider")

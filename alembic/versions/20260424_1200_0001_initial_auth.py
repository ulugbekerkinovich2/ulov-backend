"""initial auth — users + refresh_tokens + user_role enum + postgis

Revision ID: 0001_initial_auth
Revises:
Create Date: 2026-04-24 12:00:00

Hand-crafted (not autogen) so the migration is deterministic and the ordering
of "CREATE TYPE" vs "CREATE TABLE" is explicit.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_auth"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_ROLE_VALUES = ("customer", "mechanic", "owner", "admin")


def upgrade() -> None:
    # PostGIS is used by later phases (service_centers, fuel_stations). The
    # extension is shipped with the postgis/postgis Docker image; on managed
    # Postgres it must be installed by the DBA. "IF NOT EXISTS" keeps the
    # migration idempotent on re-runs.
    # op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Enum type owned by this migration.
    user_role = postgresql.ENUM(
        *USER_ROLE_VALUES,
        name="user_role",
        create_type=False,
    )
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(
                *USER_ROLE_VALUES,
                name="user_role",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'customer'::user_role"),
        ),
        sa.Column("center_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "is_active",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_center_id", "users", ["center_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_refresh_tokens_user_id",
        ),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"]
    )
    # Housekeeping: cleaning up expired tokens benefits from a sorted index.
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_users_center_id", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
    # Leave the postgis extension in place — other phases rely on it.

"""service_centers.gallery_urls — up to 5 photo URLs

Revision ID: 0007_center_gallery
Revises: 0006_phase9_audit
Create Date: 2026-05-02 09:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_center_gallery"
down_revision: Union[str, None] = "0006_phase9_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "service_centers",
        sa.Column(
            "gallery_urls",
            sa.ARRAY(sa.String(length=500)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("service_centers", "gallery_urls")

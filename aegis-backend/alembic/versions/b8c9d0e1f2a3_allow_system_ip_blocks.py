"""allow system-authored IP blocks

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow automatic blocks without inventing a human creator."""
    op.alter_column(
        "ip_blocks",
        "created_by",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    """Restore human-only blocks after removing automatic rows."""
    op.execute("DELETE FROM ip_blocks WHERE created_by IS NULL")
    op.alter_column(
        "ip_blocks",
        "created_by",
        existing_type=sa.Integer(),
        nullable=False,
    )

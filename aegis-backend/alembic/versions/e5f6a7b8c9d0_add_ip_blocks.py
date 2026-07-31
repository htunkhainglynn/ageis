"""add ip blocks

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the soft-delete IP block policy table."""
    op.create_table(
        "ip_blocks",
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'auto')",
            name="ck_ip_blocks_source",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_ip_blocks_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ip_blocks_ip_address"), "ip_blocks", ["ip_address"])
    op.create_index(op.f("ix_ip_blocks_source"), "ip_blocks", ["source"])
    op.create_index(op.f("ix_ip_blocks_status"), "ip_blocks", ["status"])
    op.create_index(op.f("ix_ip_blocks_created_by"), "ip_blocks", ["created_by"])
    op.create_index(
        "uq_ip_blocks_active_ip_address",
        "ip_blocks",
        ["ip_address"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    """Remove the IP block policy table."""
    op.drop_index("uq_ip_blocks_active_ip_address", table_name="ip_blocks")
    op.drop_index(op.f("ix_ip_blocks_created_by"), table_name="ip_blocks")
    op.drop_index(op.f("ix_ip_blocks_status"), table_name="ip_blocks")
    op.drop_index(op.f("ix_ip_blocks_source"), table_name="ip_blocks")
    op.drop_index(op.f("ix_ip_blocks_ip_address"), table_name="ip_blocks")
    op.drop_table("ip_blocks")

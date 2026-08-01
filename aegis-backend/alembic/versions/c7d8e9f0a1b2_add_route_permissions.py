"""add route permissions

Revision ID: c7d8e9f0a1b2
Revises: b8c9d0e1f2a3
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "route_permissions",
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path_pattern", sa.String(2048), nullable=False),
        sa.Column("required_scope", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_route_permissions_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_route_permissions_method"), "route_permissions", ["method"])
    op.create_index(op.f("ix_route_permissions_path_pattern"), "route_permissions", ["path_pattern"])
    op.create_index(op.f("ix_route_permissions_status"), "route_permissions", ["status"])
    op.create_index(op.f("ix_route_permissions_created_by"), "route_permissions", ["created_by"])


def downgrade() -> None:
    op.drop_index(op.f("ix_route_permissions_created_by"), table_name="route_permissions")
    op.drop_index(op.f("ix_route_permissions_status"), table_name="route_permissions")
    op.drop_index(op.f("ix_route_permissions_path_pattern"), table_name="route_permissions")
    op.drop_index(op.f("ix_route_permissions_method"), table_name="route_permissions")
    op.drop_table("route_permissions")

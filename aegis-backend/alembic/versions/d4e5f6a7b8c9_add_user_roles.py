"""add user roles

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add a backwards-compatible role column for existing users."""
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=32),
            server_default="api_consumer",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'viewer', 'api_consumer')",
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def downgrade() -> None:
    """Remove user role authorization metadata."""
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")

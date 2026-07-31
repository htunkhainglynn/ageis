"""add_rate_limit_rules_table

Revision ID: b1c2d3e4f5a6
Revises: 8479f045cebe
Create Date: 2026-07-25 23:45:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "8479f045cebe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_rules",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_value", sa.String(length=255), nullable=True),
        sa.Column("algorithm", sa.String(length=30), nullable=False),
        sa.Column("limit_count", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("burst_allowance", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "((scope_type = 'global' AND scope_value IS NULL) OR "
            "(scope_type IN ('api_key', 'route') AND scope_value IS NOT NULL))",
            name="ck_rate_limit_rules_scope_value",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_rate_limit_rules_scope_type"), "rate_limit_rules", ["scope_type"], unique=False)
    op.create_index(op.f("ix_rate_limit_rules_scope_value"), "rate_limit_rules", ["scope_value"], unique=False)
    op.create_index(op.f("ix_rate_limit_rules_status"), "rate_limit_rules", ["status"], unique=False)
    op.create_index(op.f("ix_rate_limit_rules_created_by"), "rate_limit_rules", ["created_by"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_limit_rules_created_by"), table_name="rate_limit_rules")
    op.drop_index(op.f("ix_rate_limit_rules_status"), table_name="rate_limit_rules")
    op.drop_index(op.f("ix_rate_limit_rules_scope_value"), table_name="rate_limit_rules")
    op.drop_index(op.f("ix_rate_limit_rules_scope_type"), table_name="rate_limit_rules")
    op.drop_table("rate_limit_rules")

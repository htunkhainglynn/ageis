"""add threat rules

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-31
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "threat_rules",
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("severity IN ('low','medium','high','critical')", name="ck_threat_rules_severity"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_threat_rules_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_threat_rules_severity"), "threat_rules", ["severity"])
    op.create_index(op.f("ix_threat_rules_status"), "threat_rules", ["status"])
    op.create_index(op.f("ix_threat_rules_created_by"), "threat_rules", ["created_by"])


def downgrade() -> None:
    op.drop_index(op.f("ix_threat_rules_created_by"), table_name="threat_rules")
    op.drop_index(op.f("ix_threat_rules_status"), table_name="threat_rules")
    op.drop_index(op.f("ix_threat_rules_severity"), table_name="threat_rules")
    op.drop_table("threat_rules")

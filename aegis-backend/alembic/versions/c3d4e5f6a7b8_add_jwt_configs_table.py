"""add_jwt_configs_table

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-07-26 19:10:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jwt_configs",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("algorithm", sa.String(length=10), nullable=False),
        sa.Column("signing_key", sa.Text(), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("audience", sa.String(length=255), nullable=True),
        sa.Column("access_token_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("refresh_token_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="disabled"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "((algorithm = 'HS256' AND public_key IS NULL) OR "
            "(algorithm IN ('RS256', 'ES256') AND public_key IS NOT NULL))",
            name="ck_jwt_configs_algorithm_public_key",
        ),
        sa.CheckConstraint(
            "access_token_ttl_seconds < refresh_token_ttl_seconds",
            name="ck_jwt_configs_access_ttl_lt_refresh_ttl",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(op.f("ix_jwt_configs_created_by"), "jwt_configs", ["created_by"], unique=False)
    op.create_index(op.f("ix_jwt_configs_status"), "jwt_configs", ["status"], unique=False)
    op.create_index(
        "uq_jwt_configs_single_active_status",
        "jwt_configs",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_jwt_configs_single_active_status", table_name="jwt_configs")
    op.drop_index(op.f("ix_jwt_configs_status"), table_name="jwt_configs")
    op.drop_index(op.f("ix_jwt_configs_created_by"), table_name="jwt_configs")
    op.drop_table("jwt_configs")

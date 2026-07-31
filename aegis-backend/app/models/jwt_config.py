from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class JWTConfigAlgorithm(str, Enum):
    """Supported JWT verification algorithms."""

    HS256 = "HS256"
    RS256 = "RS256"
    ES256 = "ES256"


class JWTConfigStatus(str, Enum):
    """Supported JWT configuration statuses."""

    ACTIVE = "active"
    DISABLED = "disabled"


class JWTConfig(BaseModel):
    """JWT validation configuration model for control-plane management."""

    __tablename__ = "jwt_configs"
    __table_args__ = (
        CheckConstraint(
            "((algorithm = 'HS256' AND public_key IS NULL) OR "
            "(algorithm IN ('RS256', 'ES256') AND public_key IS NOT NULL))",
            name="ck_jwt_configs_algorithm_public_key",
        ),
        CheckConstraint(
            "access_token_ttl_seconds < refresh_token_ttl_seconds",
            name="ck_jwt_configs_access_ttl_lt_refresh_ttl",
        ),
        Index(
            "uq_jwt_configs_single_active_status",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(10), nullable=False)
    signing_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    refresh_token_ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JWTConfigStatus.DISABLED.value,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

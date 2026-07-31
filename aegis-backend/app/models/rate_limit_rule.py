from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RateLimitRuleScopeType(str, Enum):
    """Supported scopes for a rate limit rule."""

    GLOBAL = "global"
    API_KEY = "api_key"
    ROUTE = "route"


class RateLimitRuleAlgorithm(str, Enum):
    """Supported rate limiting algorithms for downstream proxy enforcement."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitRuleStatus(str, Enum):
    """Supported statuses for rate limit rules."""

    ACTIVE = "active"
    DISABLED = "disabled"


class RateLimitRule(BaseModel):
    """Configuration rule model for proxy-side rate limit enforcement."""

    __tablename__ = "rate_limit_rules"
    __table_args__ = (
        CheckConstraint(
            "((scope_type = 'global' AND scope_value IS NULL) OR "
            "(scope_type IN ('api_key', 'route') AND scope_value IS NOT NULL))",
            name="ck_rate_limit_rules_scope_value",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    algorithm: Mapped[str] = mapped_column(String(30), nullable=False)
    limit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    burst_allowance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=RateLimitRuleStatus.ACTIVE.value,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

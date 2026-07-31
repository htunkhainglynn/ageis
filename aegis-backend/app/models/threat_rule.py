from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatRuleStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ThreatRule(BaseModel):
    """RE2-compatible request-target pattern enforced by the proxy."""

    __tablename__ = "threat_rules"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_threat_rules_severity",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_threat_rules_status",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ThreatRuleStatus.ACTIVE.value, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

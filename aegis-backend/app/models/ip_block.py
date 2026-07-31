from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IPBlockSource(str, Enum):
    """Supported origins for an IP block."""

    MANUAL = "manual"
    AUTO = "auto"


class IPBlockStatus(str, Enum):
    """Supported IP block lifecycle states."""

    ACTIVE = "active"
    DISABLED = "disabled"


class IPBlock(BaseModel):
    """An exact IPv4 or IPv6 address blocked by the reverse proxy."""

    __tablename__ = "ip_blocks"
    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'auto')",
            name="ck_ip_blocks_source",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_ip_blocks_status",
        ),
        Index(
            "uq_ip_blocks_active_ip_address",
            "ip_address",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IPBlockSource.MANUAL.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IPBlockStatus.ACTIVE.value,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

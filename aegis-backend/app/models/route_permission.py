from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RoutePermissionStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class RoutePermission(BaseModel):
    """Exact method/path authorization policy consumed by the reverse proxy."""

    __tablename__ = "route_permissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_route_permissions_status",
        ),
    )

    method: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    path_pattern: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    required_scope: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RoutePermissionStatus.ACTIVE.value, index=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

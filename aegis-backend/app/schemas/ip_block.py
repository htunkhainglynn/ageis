from datetime import datetime
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.ip_block import IPBlockSource, IPBlockStatus


class IPBlockCreateRequest(BaseModel):
    """Request schema for manually blocking an exact client IP address."""

    ip_address: str = Field(min_length=2, max_length=45)
    reason: str = Field(min_length=1, max_length=500)
    status: IPBlockStatus = IPBlockStatus.ACTIVE

    @field_validator("ip_address")
    @classmethod
    def normalize_ip_address(cls, value: str) -> str:
        """Validate and canonicalize IPv4 and IPv6 address strings."""
        return str(ip_address(value.strip()))


class IPBlockUpdateRequest(BaseModel):
    """Request schema for updating mutable IP block fields."""

    reason: str | None = Field(default=None, min_length=1, max_length=500)
    status: IPBlockStatus | None = None


class IPBlockCreateInDB(BaseModel):
    """Internal schema for creating a persisted IP block."""

    ip_address: str
    reason: str
    source: str
    status: str
    created_by: int


class IPBlockUpdateInDB(BaseModel):
    """Internal schema for updating a persisted IP block."""

    reason: str | None = None
    status: str | None = None


class IPBlockResponse(BaseModel):
    """Operator-facing IP block metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ip_address: str
    reason: str
    source: IPBlockSource
    status: IPBlockStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class IPBlockListResponse(BaseModel):
    """Paginated IP block list."""

    items: list[IPBlockResponse]
    skip: int
    limit: int
    total: int

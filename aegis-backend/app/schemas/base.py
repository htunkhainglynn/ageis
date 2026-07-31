from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """Standard API response wrapper."""

    status: str
    message: str
    data: DataT | None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(BaseModel):
    """Standard API error response payload."""

    status: str = "error"
    errorCode: str
    message: str
    data: None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def success_response(message: str, data: DataT | None) -> ApiResponse[DataT]:
    """Build a success response payload."""
    return ApiResponse(status="success", message=message, data=data)

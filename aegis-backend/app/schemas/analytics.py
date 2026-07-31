from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SecurityEventCreateRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    source_ip: str = Field(min_length=2, max_length=45)
    api_key_id: int | None = Field(default=None, gt=0)
    rule_id: int | None = Field(default=None, gt=0)
    method: str = Field(min_length=1, max_length=10)
    path: str = Field(min_length=1, max_length=2048)
    status_code: int = Field(ge=100, le=599)

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.strip().upper()


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    source_ip: str
    api_key_id: int | None
    rule_id: int | None
    method: str
    path: str
    status_code: int
    created_at: datetime


class SecurityEventListResponse(BaseModel):
    items: list[SecurityEventResponse]
    skip: int
    limit: int
    total: int


class AnalyticsSummaryResponse(BaseModel):
    hours: int
    total_requests: int
    forwarded_requests: int
    blocked_requests: int
    rate_limited_requests: int
    server_errors: int
    events_by_type: dict[str, int]

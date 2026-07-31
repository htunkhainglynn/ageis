from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.rate_limit_rule import (
    RateLimitRuleAlgorithm,
    RateLimitRuleScopeType,
    RateLimitRuleStatus,
)


class RateLimitRuleCreateRequest(BaseModel):
    """Request schema for creating a rate limit configuration rule."""

    name: str = Field(min_length=1, max_length=255)
    scope_type: RateLimitRuleScopeType
    scope_value: str | None = Field(default=None, min_length=1, max_length=255)
    algorithm: RateLimitRuleAlgorithm
    limit_count: int = Field(gt=0)
    window_seconds: int = Field(gt=0)
    burst_allowance: int | None = Field(default=None, gt=0)
    status: RateLimitRuleStatus = RateLimitRuleStatus.ACTIVE

    @model_validator(mode="after")
    def validate_scope(self) -> "RateLimitRuleCreateRequest":
        """Ensure scope value constraints match scope type."""
        if self.scope_type == RateLimitRuleScopeType.GLOBAL and self.scope_value is not None:
            raise ValueError("scope_value must be null for global scope.")
        if self.scope_type in {RateLimitRuleScopeType.API_KEY, RateLimitRuleScopeType.ROUTE} and self.scope_value is None:
            raise ValueError("scope_value is required for api_key and route scopes.")
        return self


class RateLimitRuleUpdateRequest(BaseModel):
    """Request schema for partial rate limit rule updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    scope_type: RateLimitRuleScopeType | None = None
    scope_value: str | None = Field(default=None, min_length=1, max_length=255)
    algorithm: RateLimitRuleAlgorithm | None = None
    limit_count: int | None = Field(default=None, gt=0)
    window_seconds: int | None = Field(default=None, gt=0)
    burst_allowance: int | None = Field(default=None, gt=0)
    status: RateLimitRuleStatus | None = None


class RateLimitRuleCreateInDB(BaseModel):
    """Internal schema for creating persisted rate limit rules."""

    name: str
    scope_type: str
    scope_value: str | None = None
    algorithm: str
    limit_count: int
    window_seconds: int
    burst_allowance: int | None = None
    status: str
    created_by: int


class RateLimitRuleUpdateInDB(BaseModel):
    """Internal schema for updating persisted rate limit rules."""

    name: str | None = None
    scope_type: str | None = None
    scope_value: str | None = None
    algorithm: str | None = None
    limit_count: int | None = None
    window_seconds: int | None = None
    burst_allowance: int | None = None
    status: str | None = None


class RateLimitRuleResponse(BaseModel):
    """Response schema for a single rate limit rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: RateLimitRuleScopeType
    scope_value: str | None
    algorithm: RateLimitRuleAlgorithm
    limit_count: int
    window_seconds: int
    burst_allowance: int | None
    status: RateLimitRuleStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class RateLimitRuleListResponse(BaseModel):
    """Paginated list response for rate limit rules."""

    items: list[RateLimitRuleResponse]
    skip: int
    limit: int
    total: int

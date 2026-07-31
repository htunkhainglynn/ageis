from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.jwt_config import JWTConfigAlgorithm
from app.models.rate_limit_rule import (
    RateLimitRuleAlgorithm,
    RateLimitRuleScopeType,
)


class ProxyJWTValidationPolicy(BaseModel):
    """Active JWT verification material consumed only by the reverse proxy."""

    id: int
    algorithm: JWTConfigAlgorithm
    verification_key: str
    issuer: str | None
    audience: str | None


class ProxyRateLimitPolicy(BaseModel):
    """Active rate-limit rule consumed by the reverse proxy."""

    id: int
    scope_type: RateLimitRuleScopeType
    scope_value: str | None
    algorithm: RateLimitRuleAlgorithm
    limit_count: int
    window_seconds: int
    burst_allowance: int | None


class ProxyPolicySnapshot(BaseModel):
    """Atomic REST policy snapshot used until gRPC synchronization is added."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    jwt: ProxyJWTValidationPolicy | None
    rate_limit_rules: list[ProxyRateLimitPolicy]

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.threat_rule import ThreatRuleStatus, ThreatSeverity


def validate_re2_pattern(value: str | None) -> str | None:
    """Reject empty/unsafe constructs outside Go's RE2 syntax."""
    if value is None:
        return None
    pattern = value.strip()
    unsupported = (r"(?=", r"(?!", r"(?<=", r"(?<!", r"\1", r"\2", r"\3")
    if any(token in pattern for token in unsupported):
        raise ValueError("pattern must use RE2-compatible syntax")
    re.compile(pattern)
    return pattern


class ThreatRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    pattern: str = Field(min_length=1, max_length=1000)
    severity: ThreatSeverity
    status: ThreatRuleStatus = ThreatRuleStatus.ACTIVE

    _validate_pattern = field_validator("pattern")(validate_re2_pattern)


class ThreatRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    pattern: str | None = Field(default=None, min_length=1, max_length=1000)
    severity: ThreatSeverity | None = None
    status: ThreatRuleStatus | None = None

    _validate_pattern = field_validator("pattern")(validate_re2_pattern)


class ThreatRuleCreateInDB(BaseModel):
    name: str
    pattern: str
    severity: str
    status: str
    created_by: int


class ThreatRuleUpdateInDB(BaseModel):
    name: str | None = None
    pattern: str | None = None
    severity: str | None = None
    status: str | None = None


class ThreatRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pattern: str
    severity: ThreatSeverity
    status: ThreatRuleStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class ThreatRuleListResponse(BaseModel):
    items: list[ThreatRuleResponse]
    skip: int
    limit: int
    total: int

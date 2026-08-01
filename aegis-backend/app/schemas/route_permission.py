import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.route_permission import RoutePermissionStatus


class HTTPMethod(str, Enum):
    GET = "GET"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    TRACE = "TRACE"


def _validate_path(value: str) -> str:
    value = value.strip()
    if not value.startswith("/") or "*" in value or "?" in value:
        raise ValueError("path_pattern must be an exact path beginning with '/'.")
    return value


def _validate_scope(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+:[A-Za-z0-9._*-]+", value):
        raise ValueError("required_scope must use resource:action format.")
    return value


def _reject_null(value: object) -> object:
    if value is None:
        raise ValueError("field cannot be null when supplied.")
    return value


class RoutePermissionCreateRequest(BaseModel):
    method: HTTPMethod
    path_pattern: str = Field(min_length=1, max_length=2048)
    required_scope: str = Field(min_length=3, max_length=255)
    status: RoutePermissionStatus = RoutePermissionStatus.ACTIVE

    _validate_path_pattern = field_validator("path_pattern")(_validate_path)
    _validate_required_scope = field_validator("required_scope")(_validate_scope)


class RoutePermissionUpdateRequest(BaseModel):
    method: HTTPMethod | None = None
    path_pattern: str | None = Field(default=None, min_length=1, max_length=2048)
    required_scope: str | None = Field(default=None, min_length=3, max_length=255)
    status: RoutePermissionStatus | None = None

    _validate_path_pattern = field_validator("path_pattern")(_validate_path)
    _validate_required_scope = field_validator("required_scope")(_validate_scope)
    _reject_null_method = field_validator("method", mode="before")(_reject_null)
    _reject_null_path = field_validator("path_pattern", mode="before")(_reject_null)
    _reject_null_scope = field_validator("required_scope", mode="before")(_reject_null)
    _reject_null_status = field_validator("status", mode="before")(_reject_null)


class RoutePermissionCreateInDB(BaseModel):
    method: str
    path_pattern: str
    required_scope: str
    status: str
    created_by: int


class RoutePermissionUpdateInDB(BaseModel):
    method: str | None = None
    path_pattern: str | None = None
    required_scope: str | None = None
    status: str | None = None


class RoutePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method: HTTPMethod
    path_pattern: str
    required_scope: str
    status: RoutePermissionStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class RoutePermissionListResponse(BaseModel):
    items: list[RoutePermissionResponse]
    skip: int
    limit: int
    total: int

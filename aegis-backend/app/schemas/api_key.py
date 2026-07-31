from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.api_key import APIKeyStatus


class APIKeyCreateRequest(BaseModel):
    """Request schema for creating an API key."""

    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class APIKeyUpdateRequest(BaseModel):
    """Request schema for updating API key metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    scopes: list[str] | None = None


class APIKeyCreateInDB(BaseModel):
    """Internal schema for API key persistence creation."""

    key_hash: str
    key_prefix: str
    owner_id: int
    name: str
    scopes: list[str]
    status: str
    expires_at: datetime | None = None


class APIKeyUpdateInDB(BaseModel):
    """Internal schema for API key persistence updates."""

    name: str | None = None
    scopes: list[str] | None = None
    status: str | None = None
    last_used_at: datetime | None = None


class APIKeyMetadataResponse(BaseModel):
    """Metadata-only response schema for API key resources."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key_prefix: str
    owner_id: int
    name: str
    scopes: list[str]
    status: APIKeyStatus
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class APIKeyCreatedResponse(APIKeyMetadataResponse):
    """Create response schema that returns raw key once."""

    api_key: str


class APIKeyListResponse(BaseModel):
    """Paginated list response for API keys."""

    items: list[APIKeyMetadataResponse]
    skip: int
    limit: int
    total: int


class APIKeyValidationRequest(BaseModel):
    """Private reverse-proxy request carrying a presented API key."""

    api_key: str = Field(min_length=8, max_length=512)


class APIKeyValidationResponse(BaseModel):
    """Non-secret key attributes required by the reverse proxy."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key_prefix: str
    owner_id: int
    scopes: list[str]
    status: APIKeyStatus
    expires_at: datetime | None

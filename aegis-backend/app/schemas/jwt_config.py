from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.jwt_config import JWTConfigAlgorithm, JWTConfigStatus


class JWTConfigCreateRequest(BaseModel):
    """Request schema for creating a JWT validation configuration."""

    name: str = Field(min_length=1, max_length=255)
    algorithm: JWTConfigAlgorithm
    signing_key: str = Field(min_length=1)
    public_key: str | None = Field(default=None, min_length=1)
    issuer: str | None = Field(default=None, min_length=1, max_length=255)
    audience: str | None = Field(default=None, min_length=1, max_length=255)
    access_token_ttl_seconds: int = Field(gt=0)
    refresh_token_ttl_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_algorithm_and_ttls(self) -> "JWTConfigCreateRequest":
        """Ensure algorithm and TTL constraints are satisfied."""
        if self.algorithm == JWTConfigAlgorithm.HS256 and self.public_key is not None:
            raise ValueError("public_key must be null for HS256.")

        if self.algorithm in {JWTConfigAlgorithm.RS256, JWTConfigAlgorithm.ES256} and self.public_key is None:
            raise ValueError("public_key is required for RS256 and ES256.")

        if self.access_token_ttl_seconds >= self.refresh_token_ttl_seconds:
            raise ValueError("access_token_ttl_seconds must be shorter than refresh_token_ttl_seconds.")

        return self


class JWTConfigUpdateRequest(BaseModel):
    """Request schema for updating non-key JWT config fields."""

    issuer: str | None = Field(default=None, min_length=1, max_length=255)
    audience: str | None = Field(default=None, min_length=1, max_length=255)
    access_token_ttl_seconds: int | None = Field(default=None, gt=0)
    refresh_token_ttl_seconds: int | None = Field(default=None, gt=0)


class JWTConfigCreateInDB(BaseModel):
    """Internal schema for persisting newly-created JWT configs."""

    name: str
    algorithm: str
    signing_key: str
    public_key: str | None = None
    issuer: str | None = None
    audience: str | None = None
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    status: str
    created_by: int


class JWTConfigUpdateInDB(BaseModel):
    """Internal schema for persisting partial JWT config updates."""

    issuer: str | None = None
    audience: str | None = None
    access_token_ttl_seconds: int | None = None
    refresh_token_ttl_seconds: int | None = None
    status: str | None = None


class JWTConfigResponse(BaseModel):
    """Response schema for a single JWT config."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    algorithm: JWTConfigAlgorithm
    signing_key_masked: str
    public_key_masked: str | None
    issuer: str | None
    audience: str | None
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    status: JWTConfigStatus
    created_by: int
    created_at: datetime
    updated_at: datetime


class JWTConfigListResponse(BaseModel):
    """Paginated list response for JWT configs."""

    items: list[JWTConfigResponse]
    skip: int
    limit: int
    total: int

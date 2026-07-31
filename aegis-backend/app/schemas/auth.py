from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Request schema for login operation."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Request schema for refresh token operation."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request schema for logout operation."""

    access_token: str


class AuthTokenResponse(BaseModel):
    """Response schema for token issuance."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded and validated JWT payload schema."""

    sub: str
    type: str
    email: EmailStr
    role: str

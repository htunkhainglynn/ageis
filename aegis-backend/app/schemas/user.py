from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Request schema for creating a user."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Request schema for updating a user."""

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    role: UserRole | None = None


class UserCreateInDB(BaseModel):
    """Internal schema for user persistence creation."""

    email: EmailStr
    full_name: str
    hashed_password: str
    is_active: bool = True
    role: str = UserRole.API_CONSUMER.value


class UserUpdateInDB(BaseModel):
    """Internal schema for user persistence updates."""

    full_name: str | None = None
    hashed_password: str | None = None
    is_active: bool | None = None
    role: str | None = None


class UserResponse(BaseModel):
    """Response schema for a user entity."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Paginated list response for users."""

    items: list[UserResponse]
    skip: int
    limit: int
    total: int

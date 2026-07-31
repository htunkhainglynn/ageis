from app.core.exceptions import ConflictException, NotFoundException
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserCreate,
    UserCreateInDB,
    UserListResponse,
    UserResponse,
    UserUpdate,
    UserUpdateInDB,
)
from app.services.base import BaseService


class UserService(BaseService[User, UserCreate, UserUpdate]):
    """Business logic for user operations."""

    def __init__(self, user_repository: UserRepository) -> None:
        super().__init__(repository=user_repository)
        self.user_repository = user_repository

    async def create_user(self, payload: UserCreate) -> UserResponse:
        """Create a new user with hashed password."""
        existing_user = await self.user_repository.get_by_email(payload.email)
        if existing_user is not None:
            raise ConflictException(
                error_code="USER_ALREADY_EXISTS",
                message="A user with this email already exists.",
            )

        user_input = UserCreateInDB(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            is_active=True,
        )
        db_user = await self.user_repository.create_user(user_input)
        return UserResponse.model_validate(db_user)

    async def list_users(self, skip: int, limit: int) -> UserListResponse:
        """List users with pagination metadata."""
        users = await self.user_repository.get_all(skip=skip, limit=limit)
        total = await self.user_repository.count_all()
        return UserListResponse(
            items=[UserResponse.model_validate(user) for user in users],
            skip=skip,
            limit=limit,
            total=total,
        )

    async def get_user_by_id(self, user_id: int) -> UserResponse:
        """Retrieve user by id."""
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException(
                error_code="USER_NOT_FOUND",
                message="User not found.",
            )
        return UserResponse.model_validate(user)

    async def update_user(self, user_id: int, payload: UserUpdate) -> UserResponse:
        """Update user attributes."""
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException(
                error_code="USER_NOT_FOUND",
                message="User not found.",
            )

        user_update = UserUpdateInDB(
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password) if payload.password is not None else None,
            is_active=payload.is_active,
        )
        user = await self.user_repository.update_user(user=user, payload=user_update)
        return UserResponse.model_validate(user)

    async def delete_user(self, user_id: int) -> None:
        """Delete an existing user."""
        deleted = await self.user_repository.delete(user_id)
        if not deleted:
            raise NotFoundException(
                error_code="USER_NOT_FOUND",
                message="User not found.",
            )

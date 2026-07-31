from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_subject
from app.repositories.user_repository import UserRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Provide a request-scoped user service instance."""
    user_repository = UserRepository(db=db)
    return UserService(user_repository=user_repository)


@router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user account with email, full name, and password.",
)
async def create_user(
    payload: UserCreate,
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserResponse]:
    """Create user.

    Create a new user resource and return persisted user details.
    """
    created_user = await user_service.create_user(payload)
    return success_response(message="User created successfully.", data=created_user)


@router.get(
    "",
    response_model=ApiResponse[UserListResponse],
    summary="List users",
    description="List users with pagination for authenticated clients.",
)
async def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    _: str = Depends(get_current_subject),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserListResponse]:
    """List users.

    Return paginated users list for authenticated clients.
    """
    users = await user_service.list_users(skip=skip, limit=limit)
    return success_response(message="Users fetched successfully.", data=users)


@router.get(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="Get user by id",
    description="Fetch a user by numeric id for authenticated clients.",
)
async def get_user_by_id(
    user_id: int,
    _: str = Depends(get_current_subject),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserResponse]:
    """Get user by id.

    Return a single user by unique identifier.
    """
    user = await user_service.get_user_by_id(user_id=user_id)
    return success_response(message="User fetched successfully.", data=user)


@router.put(
    "/{user_id}",
    response_model=ApiResponse[UserResponse],
    summary="Update user",
    description="Update mutable fields of an existing user.",
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    _: str = Depends(get_current_subject),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[UserResponse]:
    """Update user.

    Update user fields by unique identifier.
    """
    user = await user_service.update_user(user_id=user_id, payload=payload)
    return success_response(message="User updated successfully.", data=user)


@router.delete(
    "/{user_id}",
    response_model=ApiResponse[None],
    summary="Delete user",
    description="Delete an existing user by id.",
)
async def delete_user(
    user_id: int,
    _: str = Depends(get_current_subject),
    user_service: UserService = Depends(get_user_service),
) -> ApiResponse[None]:
    """Delete user.

    Delete a user by unique identifier.
    """
    await user_service.delete_user(user_id=user_id)
    return success_response(message="User deleted successfully.", data=None)

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuthTokenResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
)
from app.schemas.base import ApiResponse, success_response
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Provide a request-scoped auth service instance."""
    user_repository = UserRepository(db=db)
    return AuthService(user_repository=user_repository)


@router.post(
    "/login",
    response_model=ApiResponse[AuthTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Authenticate user credentials and issue JWT access and refresh tokens.",
)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[AuthTokenResponse]:
    """Login user.

    Authenticate user credentials and issue access/refresh tokens.
    """
    token_data = await auth_service.login(payload)
    return success_response(message="Login successful.", data=token_data)


@router.post(
    "/refresh",
    response_model=ApiResponse[AuthTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Issue a new access token using a valid refresh token.",
)
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[AuthTokenResponse]:
    """Refresh access token.

    Issue a new access token using a valid refresh token.
    """
    token_data = await auth_service.refresh_access_token(payload.refresh_token)
    return success_response(message="Access token refreshed successfully.", data=token_data)


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Invalidate an existing access token in Redis.",
)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> ApiResponse[None]:
    """Logout user.

    Invalidate an access token in Redis storage.
    """
    await auth_service.logout(payload.access_token)
    return success_response(message="Logout successful.", data=None)

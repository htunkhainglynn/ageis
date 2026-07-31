import secrets

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import (
    ForbiddenException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from app.core.security import get_current_subject
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


async def get_current_user(
    actor_subject: str = Depends(get_current_subject),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated token subject to an active persisted user."""
    try:
        actor_id = int(actor_subject)
    except ValueError as exc:
        raise UnauthorizedException(
            error_code="AUTH_INVALID_SUBJECT",
            message="Invalid authentication subject.",
        ) from exc

    user = await UserRepository(db=db).get_by_id(actor_id)
    if user is None:
        raise UnauthorizedException(
            error_code="AUTH_USER_NOT_FOUND",
            message="Authenticated user not found.",
        )
    if not user.is_active:
        raise UnauthorizedException(
            error_code="AUTH_USER_INACTIVE",
            message="User is inactive.",
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow only administrators to access a route."""
    if current_user.role != UserRole.ADMIN.value:
        raise ForbiddenException(
            error_code="AUTH_ADMIN_REQUIRED",
            message="Administrator permission is required.",
        )
    return current_user


async def require_api_key_manager(current_user: User = Depends(get_current_user)) -> User:
    """Allow administrators and API consumers to manage API keys."""
    if current_user.role not in {
        UserRole.ADMIN.value,
        UserRole.API_CONSUMER.value,
    }:
        raise ForbiddenException(
            error_code="API_KEY_FORBIDDEN",
            message="You are not allowed to manage API keys.",
        )
    return current_user


async def require_analytics_viewer(current_user: User = Depends(get_current_user)) -> User:
    """Allow administrators and read-only viewers to inspect analytics."""
    if current_user.role not in {UserRole.ADMIN.value, UserRole.VIEWER.value}:
        raise ForbiddenException(
            error_code="ANALYTICS_FORBIDDEN",
            message="You are not allowed to view analytics.",
        )
    return current_user


async def require_internal_api_token(
    internal_token: str | None = Header(
        default=None,
        alias="X-Aegis-Internal-Token",
    ),
) -> None:
    """Authenticate reverse-proxy calls to private Control Plane contracts."""
    expected_token = settings.INTERNAL_API_TOKEN.strip()
    if expected_token == "":
        raise ServiceUnavailableException(
            error_code="INTERNAL_API_NOT_CONFIGURED",
            message="Internal API authentication is not configured.",
        )
    if internal_token is None or not secrets.compare_digest(internal_token, expected_token):
        raise UnauthorizedException(
            error_code="INTERNAL_API_UNAUTHORIZED",
            message="Internal API authentication failed.",
        )

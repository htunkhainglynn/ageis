from datetime import datetime, timezone

from app.core.exceptions import UnauthorizedException
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_active,
    revoke_token,
    store_token,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthTokenResponse, LoginRequest


class AuthService:
    """Business logic for authentication and token lifecycle."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def login(self, payload: LoginRequest) -> AuthTokenResponse:
        """Authenticate user and return access/refresh tokens."""
        user = await self.user_repository.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise UnauthorizedException(
                error_code="AUTH_INVALID_CREDENTIALS",
                message="Invalid email or password.",
            )
        if not user.is_active:
            raise UnauthorizedException(
                error_code="AUTH_USER_INACTIVE",
                message="User is inactive.",
            )

        access_token, access_expiry = create_access_token(str(user.id))
        refresh_token, refresh_expiry = create_refresh_token(str(user.id))

        access_ttl = int((access_expiry - datetime.now(timezone.utc)).total_seconds())
        refresh_ttl = int((refresh_expiry - datetime.now(timezone.utc)).total_seconds())

        await store_token(access_token, str(user.id), TokenType.ACCESS, access_ttl)
        await store_token(refresh_token, str(user.id), TokenType.REFRESH, refresh_ttl)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_access_token(self, refresh_token: str) -> AuthTokenResponse:
        """Issue a new access token using refresh token."""
        payload = decode_token(refresh_token)
        subject = payload.sub
        if payload.type != TokenType.REFRESH:
            raise UnauthorizedException(
                error_code="AUTH_INVALID_TOKEN_TYPE",
                message="Refresh token is required.",
            )
        if not await is_token_active(refresh_token, subject, TokenType.REFRESH):
            raise UnauthorizedException(
                error_code="AUTH_TOKEN_REVOKED",
                message="Refresh token has been revoked.",
            )

        access_token, access_expiry = create_access_token(subject)
        access_ttl = int((access_expiry - datetime.now(timezone.utc)).total_seconds())
        await store_token(access_token, subject, TokenType.ACCESS, access_ttl)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def logout(self, access_token: str) -> None:
        """Invalidate an active access token."""
        payload = decode_token(access_token)
        subject = payload.sub
        if payload.type != TokenType.ACCESS:
            raise UnauthorizedException(
                error_code="AUTH_INVALID_TOKEN_TYPE",
                message="Access token is required.",
            )

        await revoke_token(access_token, subject, TokenType.ACCESS)

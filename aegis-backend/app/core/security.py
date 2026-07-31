from datetime import datetime, timedelta, timezone

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.redis import delete_cache, get_cache, set_cache
from app.schemas.auth import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType:
    """Token type constants."""

    ACCESS: str = "access"
    REFRESH: str = "refresh"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(subject: str, email: str, role: str) -> tuple[str, datetime]:
    """Create a signed JWT access token."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "type": TokenType.ACCESS,
        "email": email,
        "role": role,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt.SECRET_KEY, algorithm=settings.jwt.ALGORITHM)
    return token, expires_at


def create_refresh_token(subject: str, email: str, role: str) -> tuple[str, datetime]:
    """Create a signed JWT refresh token."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": subject,
        "type": TokenType.REFRESH,
        "email": email,
        "role": role,
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.jwt.SECRET_KEY, algorithm=settings.jwt.ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.jwt.SECRET_KEY, algorithms=[settings.jwt.ALGORITHM])
        subject = payload.get("sub")
        token_type = payload.get("type")
        email = payload.get("email")
        role = payload.get("role")
        if (
            not isinstance(subject, str)
            or not isinstance(token_type, str)
            or not isinstance(email, str)
            or not isinstance(role, str)
        ):
            raise UnauthorizedException(
                error_code="AUTH_INVALID_TOKEN",
                message="Invalid token payload.",
            )
        return TokenPayload(sub=subject, type=token_type, email=email, role=role)
    except JWTError as exc:
        raise UnauthorizedException(
            error_code="AUTH_INVALID_TOKEN",
            message="Invalid or expired token.",
        ) from exc


async def store_token(token: str, subject: str, token_type: str, ttl_seconds: int) -> None:
    """Store issued token in Redis with TTL."""
    await set_cache(f"token:{token_type}:{subject}:{token}", "1", ttl_seconds)


async def is_token_active(token: str, subject: str, token_type: str) -> bool:
    """Validate whether token still exists in Redis."""
    cached = await get_cache(f"token:{token_type}:{subject}:{token}")
    return cached is not None


async def revoke_token(token: str, subject: str, token_type: str) -> None:
    """Invalidate a token in Redis."""
    await delete_cache(f"token:{token_type}:{subject}:{token}")


async def get_current_subject(token: str = Depends(oauth2_scheme)) -> str:
    """Extract and validate current authenticated subject from access token."""
    payload = decode_token(token)
    subject = payload.sub
    if payload.type != TokenType.ACCESS:
        raise UnauthorizedException(
            error_code="AUTH_INVALID_TOKEN_TYPE",
            message="Access token is required.",
        )
    if not await is_token_active(token, subject, TokenType.ACCESS):
        raise UnauthorizedException(
            error_code="AUTH_TOKEN_REVOKED",
            message="Token has been revoked.",
        )
    return subject

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException, TooManyRequestsException
from app.core import redis


async def enforce_api_key_creation_rate_limit(owner_id: int) -> None:
    """Enforce per-user API key creation rate limit using Redis."""
    if redis.redis_client is None:
        raise ServiceUnavailableException(
            error_code="RATE_LIMIT_UNAVAILABLE",
            message="Rate limiting service is unavailable.",
        )

    rate_limit_key = f"rate_limit:api_key:create:{owner_id}"
    try:
        current_count = int(await redis.redis_client.incr(rate_limit_key))
        if current_count == 1:
            await redis.redis_client.expire(rate_limit_key, settings.api_key.CREATE_RATE_WINDOW_SECONDS)
    except RedisError as exc:
        raise ServiceUnavailableException(
            error_code="RATE_LIMIT_UNAVAILABLE",
            message="Rate limiting service is unavailable.",
        ) from exc

    if current_count > settings.api_key.CREATE_RATE_LIMIT:
        raise TooManyRequestsException(
            error_code="API_KEY_CREATE_RATE_LIMIT_EXCEEDED",
            message="API key creation rate limit exceeded.",
        )

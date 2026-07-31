from typing import Any

from redis import asyncio as aioredis
from redis.asyncio.client import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.utils.logger import logger

redis_client: Redis | None = None


async def init_redis() -> bool:
    """Initialize Redis client and validate connectivity."""
    global redis_client
    try:
        redis_client = aioredis.Redis(
            host=settings.redis.HOST,
            port=settings.redis.PORT,
            password=settings.redis.PASSWORD,
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("Redis connection established")
        return True
    except RedisError:
        logger.exception("Failed to connect to Redis during startup")
        redis_client = None
        return False


async def close_redis() -> None:
    """Close Redis client connection."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def check_redis_health() -> bool:
    """Check whether Redis is reachable."""
    if redis_client is None:
        return False
    try:
        await redis_client.ping()
        return True
    except RedisError:
        return False


async def set_cache(key: str, value: str, ttl_seconds: int) -> None:
    """Write a cached value into Redis with TTL."""
    if redis_client is None:
        return
    await redis_client.setex(key, ttl_seconds, value)


async def get_cache(key: str) -> str | None:
    """Read a cached value from Redis."""
    if redis_client is None:
        return None
    cached_value: Any = await redis_client.get(key)
    return cached_value if isinstance(cached_value, str) else None


async def delete_cache(key: str) -> None:
    """Delete a cached value from Redis."""
    if redis_client is None:
        return
    await redis_client.delete(key)

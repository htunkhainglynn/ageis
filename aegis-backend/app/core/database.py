from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.utils.logger import logger

engine = create_async_engine(settings.database.URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async SQLAlchemy session for request scope."""
    async with AsyncSessionLocal() as session:
        yield session


async def check_database_health() -> bool:
    """Check whether the database is reachable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


async def init_database() -> bool:
    """Validate database connectivity during startup."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database connection established")
        return True
    except SQLAlchemyError:
        logger.exception("Failed to connect to database during startup")
        return False


async def close_database() -> None:
    """Close SQLAlchemy engine resources."""
    await engine.dispose()

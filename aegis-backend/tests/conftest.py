from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import get_current_subject, hash_password
from app.main import app
from app.models import Base
from app.models.user import User


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated in-memory database session for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_local = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_local() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client with dependency overrides for tests."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_current_subject() -> str:
        return app.state.test_actor_subject

    async def bypass_rate_limit(_: int) -> None:
        return

    app.state.test_actor_subject = "1"
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_subject] = override_get_current_subject
    monkeypatch.setattr("app.services.api_key_service.enforce_api_key_creation_rate_limit", bypass_rate_limit)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_users(db_session: AsyncSession) -> None:
    """Seed two users for ownership and authorization tests."""
    user_one = User(
        id=1,
        email="owner@example.com",
        full_name="Owner User",
        hashed_password=hash_password("Passw0rd!"),
        is_active=True,
    )
    user_two = User(
        id=2,
        email="other@example.com",
        full_name="Other User",
        hashed_password=hash_password("Passw0rd!"),
        is_active=True,
    )

    db_session.add(user_one)
    db_session.add(user_two)
    await db_session.commit()

    user_one.role = "admin"
    user_two.role = "member"

"""Tests for the development-only seed and reporting tools."""

from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from dev_data_common import (  # noqa: E402
    ADMIN_EMAIL,
    CONSUMER1_EMAIL,
    CONSUMER2_EMAIL,
    DevSecrets,
    VIEWER_EMAIL,
    require_development_environment,
)
from list_dev_data import render_dev_data_report  # noqa: E402
from seed_dev_data import seed_dev_data  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.encryption import decrypt_jwt_signing_key  # noqa: E402
from app.core.security import verify_password  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.api_key import APIKey, APIKeyStatus  # noqa: E402
from app.models.jwt_config import JWTConfig, JWTConfigStatus  # noqa: E402
from app.models.rate_limit_rule import (  # noqa: E402
    RateLimitRule,
    RateLimitRuleScopeType,
)
from app.models.user import User, UserRole  # noqa: E402


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide the complete schema in an isolated in-memory database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def dev_secrets() -> DevSecrets:
    """Use explicit non-fallback test values."""
    return DevSecrets(
        admin_password="Test-Admin-Password!1",
        user_password="Test-User-Password!1",
        consumer1_active_key="ak_t1_ACTIVE_TEST_VALUE_123456789",
        consumer1_revoked_key="ak_tr_REVOKED_TEST_VALUE_12345678",
        consumer2_active_key="ak_t2_ACTIVE_TEST_VALUE_123456789",
        jwt_signing_key="test-HS256-signing-key-with-at-least-32-bytes",
        fallback_variables=(),
    )


def test_environment_guard_requires_two_development_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dev tooling must reject missing, production, or contradictory settings."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(RuntimeError, match="ENVIRONMENT=development"):
        require_development_environment("development")

    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="APP_ENV"):
        require_development_environment("production")

    require_development_environment("development")


def test_runtime_secrets_generate_keys_but_only_fallback_passwords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Raw keys and signing material are fresh runtime values, not source fallbacks."""
    for variable in (
        "AEGIS_DEV_ADMIN_PASSWORD",
        "AEGIS_DEV_USER_PASSWORD",
        "AEGIS_DEV_CONSUMER1_ACTIVE_KEY",
        "AEGIS_DEV_CONSUMER1_REVOKED_KEY",
        "AEGIS_DEV_CONSUMER2_ACTIVE_KEY",
        "AEGIS_DEV_JWT_SIGNING_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    first = DevSecrets.from_environment()
    second = DevSecrets.from_environment()

    assert first.fallback_variables == (
        "AEGIS_DEV_ADMIN_PASSWORD",
        "AEGIS_DEV_USER_PASSWORD",
    )
    assert first.consumer1_active_key.startswith("ak_")
    assert len(
        {
            first.consumer1_active_key,
            first.consumer1_revoked_key,
            first.consumer2_active_key,
        }
    ) == 3
    assert first.consumer1_active_key != second.consumer1_active_key
    assert first.jwt_signing_key != second.jwt_signing_key


@pytest.mark.asyncio
async def test_seed_is_idempotent_secure_and_report_is_sanitized(
    db_session: AsyncSession,
    dev_secrets: DevSecrets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two runs keep one logical dataset and use production crypto helpers."""
    monkeypatch.setattr(
        settings,
        "JWT_CONFIG_ENCRYPTION_KEY",
        Fernet.generate_key().decode(),
    )

    first = await seed_dev_data(db_session, dev_secrets)
    second = await seed_dev_data(db_session, dev_secrets)

    assert [user.id for user in first.users] == [user.id for user in second.users]
    assert [key.id for key in first.api_keys] == [key.id for key in second.api_keys]
    assert first.jwt_config.id == second.jwt_config.id

    user_count = await db_session.scalar(select(func.count(User.id)))
    key_count = await db_session.scalar(select(func.count(APIKey.id)))
    rule_count = await db_session.scalar(select(func.count(RateLimitRule.id)))
    jwt_count = await db_session.scalar(select(func.count(JWTConfig.id)))
    assert (user_count, key_count, rule_count, jwt_count) == (4, 3, 3, 1)

    users = {
        user.email: user
        for user in (
            await db_session.execute(select(User).order_by(User.id.asc()))
        ).scalars()
    }
    assert users[ADMIN_EMAIL].role == UserRole.ADMIN.value
    assert users[VIEWER_EMAIL].role == UserRole.VIEWER.value
    assert users[CONSUMER1_EMAIL].role == UserRole.API_CONSUMER.value
    assert users[CONSUMER2_EMAIL].role == UserRole.API_CONSUMER.value
    assert verify_password(dev_secrets.admin_password, users[ADMIN_EMAIL].hashed_password)
    assert verify_password(dev_secrets.user_password, users[VIEWER_EMAIL].hashed_password)

    api_keys = list(
        (
            await db_session.execute(select(APIKey).order_by(APIKey.id.asc()))
        )
        .scalars()
        .all()
    )
    raw_keys = (
        dev_secrets.consumer1_active_key,
        dev_secrets.consumer2_active_key,
        dev_secrets.consumer1_revoked_key,
    )
    assert all(
        verify_password(raw_key, api_key.key_hash)
        for raw_key, api_key in zip(raw_keys, api_keys, strict=True)
    )
    assert [api_key.status for api_key in api_keys] == [
        APIKeyStatus.ACTIVE.value,
        APIKeyStatus.ACTIVE.value,
        APIKeyStatus.REVOKED.value,
    ]

    rules = list(
        (
            await db_session.execute(
                select(RateLimitRule).order_by(RateLimitRule.id.asc())
            )
        )
        .scalars()
        .all()
    )
    consumer1_rule = next(
        rule
        for rule in rules
        if rule.scope_type == RateLimitRuleScopeType.API_KEY.value
    )
    assert consumer1_rule.scope_value == str(api_keys[0].id)
    assert (consumer1_rule.limit_count, consumer1_rule.window_seconds) == (3, 10)

    jwt_config = (
        await db_session.execute(select(JWTConfig))
    ).scalar_one()
    assert jwt_config.status == JWTConfigStatus.ACTIVE.value
    assert jwt_config.signing_key != dev_secrets.jwt_signing_key
    assert decrypt_jwt_signing_key(jwt_config.signing_key) == dev_secrets.jwt_signing_key

    report = await render_dev_data_report(db_session)
    assert ADMIN_EMAIL in report
    assert consumer1_rule.scope_value in report
    assert "****ytes" in report
    assert "hashed_password" not in report
    assert "key_hash" not in report
    for secret in raw_keys + (dev_secrets.jwt_signing_key,):
        assert secret not in report

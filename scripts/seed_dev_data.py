#!/usr/bin/env python3
"""Idempotently seed deterministic Aegis data for local development only."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from dev_data_common import (
    ADMIN_EMAIL,
    CONSUMER1_ACTIVE_KEY_NAME,
    CONSUMER1_EMAIL,
    CONSUMER1_REVOKED_KEY_NAME,
    CONSUMER1_RULE_NAME,
    CONSUMER2_ACTIVE_KEY_NAME,
    CONSUMER2_EMAIL,
    DevSecrets,
    ECHO_ROUTE_RULE_NAME,
    GLOBAL_RULE_NAME,
    JWT_AUDIENCE,
    JWT_CONFIG_NAME,
    JWT_ISSUER,
    VIEWER_EMAIL,
    print_fallback_warning,
    require_development_environment,
)
from jose import jwt
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, close_database
from app.core.encryption import encrypt_jwt_signing_key
from app.core.security import hash_password, verify_password
from app.models.api_key import APIKey, APIKeyStatus
from app.models.jwt_config import (
    JWTConfig,
    JWTConfigAlgorithm,
    JWTConfigStatus,
)
from app.models.rate_limit_rule import (
    RateLimitRule,
    RateLimitRuleAlgorithm,
    RateLimitRuleScopeType,
    RateLimitRuleStatus,
)
from app.models.user import User, UserRole


@dataclass(frozen=True)
class SeedResult:
    """Values needed for the manual POC after the transaction commits."""

    users: tuple[User, ...]
    api_keys: tuple[APIKey, ...]
    rate_limit_rules: tuple[RateLimitRule, ...]
    jwt_config: JWTConfig


USER_SPECS = (
    (ADMIN_EMAIL, "Aegis Development Administrator", UserRole.ADMIN),
    (VIEWER_EMAIL, "Aegis Development Viewer", UserRole.VIEWER),
    (CONSUMER1_EMAIL, "Aegis Development Consumer One", UserRole.API_CONSUMER),
    (CONSUMER2_EMAIL, "Aegis Development Consumer Two", UserRole.API_CONSUMER),
)


async def _upsert_user(
    session: AsyncSession,
    email: str,
    full_name: str,
    role: UserRole,
    password: str,
) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=True,
            role=role.value,
        )
        session.add(user)
    else:
        user.full_name = full_name
        user.is_active = True
        user.role = role.value
        try:
            password_matches = verify_password(password, user.hashed_password)
        except (TypeError, ValueError):
            password_matches = False
        if not password_matches:
            user.hashed_password = hash_password(password)
    await session.flush()
    return user


async def _upsert_api_key(
    session: AsyncSession,
    *,
    owner: User,
    name: str,
    raw_key: str,
    status: APIKeyStatus,
) -> APIKey:
    result = await session.execute(
        select(APIKey)
        .where(APIKey.owner_id == owner.id, APIKey.name == name)
        .order_by(APIKey.id.asc())
        .limit(1)
    )
    api_key = result.scalar_one_or_none()
    prefix = raw_key[: settings.api_key.PREFIX_LENGTH]
    key_matches = False
    if api_key is not None:
        try:
            key_matches = verify_password(raw_key, api_key.key_hash)
        except (TypeError, ValueError):
            key_matches = False

    if api_key is None:
        api_key = APIKey(
            owner_id=owner.id,
            name=name,
            key_hash=hash_password(raw_key),
            key_prefix=prefix,
            scopes=["echo:read"],
            status=status.value,
            expires_at=None,
        )
        session.add(api_key)
    else:
        api_key.key_prefix = prefix
        api_key.scopes = ["echo:read"]
        api_key.status = status.value
        api_key.expires_at = None
        if not key_matches:
            api_key.key_hash = hash_password(raw_key)
    await session.flush()
    return api_key


async def _upsert_rate_limit_rule(
    session: AsyncSession,
    *,
    name: str,
    scope_type: RateLimitRuleScopeType,
    scope_value: str | None,
    algorithm: RateLimitRuleAlgorithm,
    limit_count: int,
    window_seconds: int,
    created_by: int,
) -> RateLimitRule:
    scope_clause = (
        RateLimitRule.scope_value.is_(None)
        if scope_value is None
        else RateLimitRule.scope_value == scope_value
    )
    result = await session.execute(
        select(RateLimitRule)
        .where(RateLimitRule.scope_type == scope_type.value, scope_clause)
        .order_by(
            case(
                (RateLimitRule.status == RateLimitRuleStatus.ACTIVE.value, 0),
                else_=1,
            ),
            RateLimitRule.id.asc(),
        )
        .limit(1)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        rule = RateLimitRule(
            name=name,
            scope_type=scope_type.value,
            scope_value=scope_value,
            algorithm=algorithm.value,
            limit_count=limit_count,
            window_seconds=window_seconds,
            burst_allowance=None,
            status=RateLimitRuleStatus.ACTIVE.value,
            created_by=created_by,
        )
        session.add(rule)
    else:
        rule.name = name
        rule.algorithm = algorithm.value
        rule.limit_count = limit_count
        rule.window_seconds = window_seconds
        rule.burst_allowance = None
        rule.status = RateLimitRuleStatus.ACTIVE.value
        rule.created_by = created_by
    await session.flush()
    return rule


async def _upsert_jwt_config(
    session: AsyncSession,
    *,
    admin_id: int,
    signing_key: str,
) -> JWTConfig:
    result = await session.execute(
        select(JWTConfig)
        .where(JWTConfig.name == JWT_CONFIG_NAME)
        .order_by(JWTConfig.id.asc())
        .limit(1)
    )
    jwt_config = result.scalar_one_or_none()

    await session.execute(
        update(JWTConfig)
        .where(
            JWTConfig.status == JWTConfigStatus.ACTIVE.value,
            JWTConfig.id != (jwt_config.id if jwt_config is not None else -1),
        )
        .values(status=JWTConfigStatus.DISABLED.value)
    )

    encrypted_key = encrypt_jwt_signing_key(signing_key)
    if jwt_config is None:
        jwt_config = JWTConfig(
            name=JWT_CONFIG_NAME,
            algorithm=JWTConfigAlgorithm.HS256.value,
            signing_key=encrypted_key,
            public_key=None,
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            access_token_ttl_seconds=900,
            refresh_token_ttl_seconds=3600,
            status=JWTConfigStatus.ACTIVE.value,
            created_by=admin_id,
        )
        session.add(jwt_config)
    else:
        jwt_config.algorithm = JWTConfigAlgorithm.HS256.value
        jwt_config.signing_key = encrypted_key
        jwt_config.public_key = None
        jwt_config.issuer = JWT_ISSUER
        jwt_config.audience = JWT_AUDIENCE
        jwt_config.access_token_ttl_seconds = 900
        jwt_config.refresh_token_ttl_seconds = 3600
        jwt_config.status = JWTConfigStatus.ACTIVE.value
        jwt_config.created_by = admin_id
    await session.flush()
    return jwt_config


async def seed_dev_data(session: AsyncSession, secrets: DevSecrets) -> SeedResult:
    """Upsert the complete deterministic dev dataset in one transaction."""
    users: list[User] = []
    for email, full_name, role in USER_SPECS:
        password = (
            secrets.admin_password if role == UserRole.ADMIN else secrets.user_password
        )
        users.append(
            await _upsert_user(session, email, full_name, role, password)
        )

    users_by_email = {user.email: user for user in users}
    admin = users_by_email[ADMIN_EMAIL]
    consumer1 = users_by_email[CONSUMER1_EMAIL]
    consumer2 = users_by_email[CONSUMER2_EMAIL]

    api_keys = (
        await _upsert_api_key(
            session,
            owner=consumer1,
            name=CONSUMER1_ACTIVE_KEY_NAME,
            raw_key=secrets.consumer1_active_key,
            status=APIKeyStatus.ACTIVE,
        ),
        await _upsert_api_key(
            session,
            owner=consumer2,
            name=CONSUMER2_ACTIVE_KEY_NAME,
            raw_key=secrets.consumer2_active_key,
            status=APIKeyStatus.ACTIVE,
        ),
        await _upsert_api_key(
            session,
            owner=consumer1,
            name=CONSUMER1_REVOKED_KEY_NAME,
            raw_key=secrets.consumer1_revoked_key,
            status=APIKeyStatus.REVOKED,
        ),
    )

    rate_limit_rules = (
        await _upsert_rate_limit_rule(
            session,
            name=GLOBAL_RULE_NAME,
            scope_type=RateLimitRuleScopeType.GLOBAL,
            scope_value=None,
            algorithm=RateLimitRuleAlgorithm.FIXED_WINDOW,
            limit_count=100,
            window_seconds=60,
            created_by=admin.id,
        ),
        await _upsert_rate_limit_rule(
            session,
            name=CONSUMER1_RULE_NAME,
            scope_type=RateLimitRuleScopeType.API_KEY,
            scope_value=str(api_keys[0].id),
            algorithm=RateLimitRuleAlgorithm.SLIDING_WINDOW,
            limit_count=3,
            window_seconds=10,
            created_by=admin.id,
        ),
        await _upsert_rate_limit_rule(
            session,
            name=ECHO_ROUTE_RULE_NAME,
            scope_type=RateLimitRuleScopeType.ROUTE,
            scope_value="/api/echo",
            algorithm=RateLimitRuleAlgorithm.FIXED_WINDOW,
            limit_count=10,
            window_seconds=10,
            created_by=admin.id,
        ),
    )

    jwt_config = await _upsert_jwt_config(
        session,
        admin_id=admin.id,
        signing_key=secrets.jwt_signing_key,
    )
    await session.commit()
    return SeedResult(
        users=tuple(users),
        api_keys=api_keys,
        rate_limit_rules=rate_limit_rules,
        jwt_config=jwt_config,
    )


def create_demo_jwt(signing_key: str) -> str:
    """Create a short-lived JWT matching the seeded proxy validation policy."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": "aegis-dev-poc",
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        signing_key,
        algorithm=JWTConfigAlgorithm.HS256.value,
    )


def print_seed_result(result: SeedResult, secrets: DevSecrets) -> None:
    """Print usable POC variables without persisting raw credentials."""
    print("\nAegis development data is ready (existing rows were safely updated).")
    print("\nDevelopment logins:")
    print(f"  Admin:       {ADMIN_EMAIL}")
    print(f"  Admin pass:  {secrets.admin_password}")
    print(f"  Viewer:      {VIEWER_EMAIL}")
    print(f"  Consumer 1:  {CONSUMER1_EMAIL}")
    print(f"  Consumer 2:  {CONSUMER2_EMAIL}")
    print(f"  User pass:   {secrets.user_password}")
    print("\nCopy these runtime-only values into the shell used for POC curl commands:")
    print(f"export AEGIS_CONSUMER1_KEY='{secrets.consumer1_active_key}'")
    print(f"export AEGIS_CONSUMER1_REVOKED_KEY='{secrets.consumer1_revoked_key}'")
    print(f"export AEGIS_CONSUMER2_KEY='{secrets.consumer2_active_key}'")
    print(f"export AEGIS_DEMO_JWT='{create_demo_jwt(secrets.jwt_signing_key)}'")
    print(
        "\nAPI keys were rotated and are shown only in this output. "
        "The demo JWT expires in one hour."
    )
    print("Rerun this idempotent script to rotate the keys and refresh the JWT.")
    print(
        f"Seeded IDs: users={','.join(str(user.id) for user in result.users)}; "
        f"api_keys={','.join(str(key.id) for key in result.api_keys)}; "
        f"jwt_config={result.jwt_config.id}"
    )


async def _main() -> None:
    require_development_environment(settings.APP_ENV)
    secrets = DevSecrets.from_environment()
    print_fallback_warning(secrets.fallback_variables)
    try:
        async with AsyncSessionLocal() as session:
            result = await seed_dev_data(session, secrets)
        print_seed_result(result, secrets)
    finally:
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"Seed aborted: {exc}") from exc

#!/usr/bin/env python3
"""Read-only report for the deterministic Aegis development dataset."""

from __future__ import annotations

import asyncio

from dev_data_common import (
    ADMIN_EMAIL,
    CONSUMER1_EMAIL,
    CONSUMER2_EMAIL,
    DEV_API_KEY_NAMES,
    DEV_RATE_RULE_NAMES,
    JWT_CONFIG_NAME,
    VIEWER_EMAIL,
    format_table,
    mask_secret,
    require_development_environment,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, close_database
from app.core.encryption import decrypt_jwt_signing_key
from app.models.api_key import APIKey
from app.models.jwt_config import JWTConfig
from app.models.rate_limit_rule import RateLimitRule
from app.models.user import User

DEV_USER_EMAILS = (ADMIN_EMAIL, VIEWER_EMAIL, CONSUMER1_EMAIL, CONSUMER2_EMAIL)


async def render_dev_data_report(session: AsyncSession) -> str:
    """Query and render only rows belonging to the named development dataset."""
    users = list(
        (
            await session.execute(
                select(User)
                .where(User.email.in_(DEV_USER_EMAILS))
                .order_by(User.id.asc())
            )
        )
        .scalars()
        .all()
    )
    owners = {user.id: user.email for user in users}

    api_keys = list(
        (
            await session.execute(
                select(APIKey)
                .where(APIKey.name.in_(DEV_API_KEY_NAMES))
                .order_by(APIKey.id.asc())
            )
        )
        .scalars()
        .all()
    )
    rules = list(
        (
            await session.execute(
                select(RateLimitRule)
                .where(RateLimitRule.name.in_(DEV_RATE_RULE_NAMES))
                .order_by(RateLimitRule.id.asc())
            )
        )
        .scalars()
        .all()
    )
    jwt_configs = list(
        (
            await session.execute(
                select(JWTConfig)
                .where(JWTConfig.name == JWT_CONFIG_NAME)
                .order_by(JWTConfig.id.asc())
            )
        )
        .scalars()
        .all()
    )

    sections = [
        "USERS",
        format_table(
            ("email", "role", "id"),
            [(user.email, user.role, user.id) for user in users],
        ),
        "",
        "API KEYS",
        format_table(
            ("owner", "key_prefix", "status", "id"),
            [
                (
                    owners.get(api_key.owner_id, f"user:{api_key.owner_id}"),
                    api_key.key_prefix,
                    api_key.status,
                    api_key.id,
                )
                for api_key in api_keys
            ],
        ),
        "",
        "RATE LIMIT RULES",
        format_table(
            (
                "scope_type",
                "scope_value",
                "limit_count",
                "window_seconds",
                "status",
            ),
            [
                (
                    rule.scope_type,
                    rule.scope_value,
                    rule.limit_count,
                    rule.window_seconds,
                    rule.status,
                )
                for rule in rules
            ],
        ),
        "",
        "JWT CONFIG",
        format_table(
            ("algorithm", "status", "masked_key"),
            [
                (
                    jwt_config.algorithm,
                    jwt_config.status,
                    mask_secret(decrypt_jwt_signing_key(jwt_config.signing_key)),
                )
                for jwt_config in jwt_configs
            ],
        ),
    ]
    return "\n".join(sections)


async def _main() -> None:
    require_development_environment(settings.APP_ENV)
    try:
        async with AsyncSessionLocal() as session:
            print(await render_dev_data_report(session))
    finally:
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except RuntimeError as exc:
        raise SystemExit(f"List aborted: {exc}") from exc

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.rate_limit_rule import (
    RateLimitRule,
    RateLimitRuleScopeType,
    RateLimitRuleStatus,
)
from app.services.rate_limit_rule_service import RateLimitRuleService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def override_admin_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use deterministic admin resolution for authorization tests."""

    def is_admin_user(_: RateLimitRuleService, actor_user) -> bool:
        return actor_user.id == 1

    monkeypatch.setattr(RateLimitRuleService, "_is_admin_user", is_admin_user)


async def test_create_rate_limit_rule_success(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify admin can create a rate limit rule."""
    response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Global default",
            "scope_type": "global",
            "scope_value": None,
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "status": "active",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["name"] == "Global default"
    assert payload["data"]["created_by"] == 1

    result = await db_session.execute(select(RateLimitRule).where(RateLimitRule.name == "Global default"))
    rule = result.scalar_one()
    assert rule.scope_type == RateLimitRuleScopeType.GLOBAL.value
    assert rule.status == RateLimitRuleStatus.ACTIVE.value


async def test_create_rate_limit_rule_rejects_invalid_scope_value(client, seeded_users) -> None:
    """Verify scope_value validation for global scope."""
    response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Invalid global",
            "scope_type": "global",
            "scope_value": "should-not-be-set",
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "status": "active",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errorCode"] == "REQUEST_VALIDATION_ERROR"


async def test_create_rate_limit_rule_rejects_duplicate_active_scope(client, seeded_users) -> None:
    """Verify only one active rule can exist for the same scope tuple."""
    first_response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Route rule one",
            "scope_type": "route",
            "scope_value": "/api/v1/users",
            "algorithm": "sliding_window",
            "limit_count": 60,
            "window_seconds": 60,
            "status": "active",
        },
    )
    assert first_response.status_code == status.HTTP_201_CREATED

    second_response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Route rule duplicate",
            "scope_type": "route",
            "scope_value": "/api/v1/users",
            "algorithm": "fixed_window",
            "limit_count": 30,
            "window_seconds": 60,
            "status": "active",
        },
    )

    assert second_response.status_code == status.HTTP_409_CONFLICT
    payload = second_response.json()
    assert payload["status"] == "error"
    assert payload["errorCode"] == "RATE_LIMIT_RULE_ALREADY_ACTIVE"


async def test_non_admin_cannot_create_update_or_delete_rate_limit_rule(client, seeded_users) -> None:
    """Verify write endpoints are admin-only."""
    app.state.test_actor_subject = "2"

    create_response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Member rule",
            "scope_type": "global",
            "scope_value": None,
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "status": "active",
        },
    )
    assert create_response.status_code == status.HTTP_403_FORBIDDEN

    app.state.test_actor_subject = "1"
    admin_create_response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Admin rule",
            "scope_type": "global",
            "scope_value": None,
            "algorithm": "fixed_window",
            "limit_count": 100,
            "window_seconds": 60,
            "status": "active",
        },
    )
    rule_id = admin_create_response.json()["data"]["id"]

    app.state.test_actor_subject = "2"
    update_response = await client.patch(
        f"/api/v1/rate-limit-rules/{rule_id}",
        json={"limit_count": 200},
    )
    delete_response = await client.delete(f"/api/v1/rate-limit-rules/{rule_id}")

    assert update_response.status_code == status.HTTP_403_FORBIDDEN
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN


async def test_list_get_update_and_soft_delete_rate_limit_rule(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify read filters, update behavior, and soft-delete."""
    create_response = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "API key scope rule",
            "scope_type": "api_key",
            "scope_value": "10",
            "algorithm": "token_bucket",
            "limit_count": 120,
            "window_seconds": 60,
            "burst_allowance": 20,
            "status": "active",
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    rule_id = create_response.json()["data"]["id"]

    list_response = await client.get("/api/v1/rate-limit-rules?scope_type=api_key&status=active")
    assert list_response.status_code == status.HTTP_200_OK
    list_payload = list_response.json()
    assert list_payload["status"] == "success"
    assert list_payload["data"]["total"] == 1
    assert list_payload["data"]["items"][0]["id"] == rule_id

    app.state.test_actor_subject = "2"
    get_response = await client.get(f"/api/v1/rate-limit-rules/{rule_id}")
    assert get_response.status_code == status.HTTP_200_OK

    app.state.test_actor_subject = "1"
    update_response = await client.patch(
        f"/api/v1/rate-limit-rules/{rule_id}",
        json={"limit_count": 300, "window_seconds": 120},
    )
    assert update_response.status_code == status.HTTP_200_OK
    update_payload = update_response.json()
    assert update_payload["data"]["limit_count"] == 300
    assert update_payload["data"]["window_seconds"] == 120

    disable_response = await client.delete(f"/api/v1/rate-limit-rules/{rule_id}")
    assert disable_response.status_code == status.HTTP_200_OK

    result = await db_session.execute(select(RateLimitRule).where(RateLimitRule.id == rule_id))
    rule = result.scalar_one()
    assert rule.status == RateLimitRuleStatus.DISABLED.value

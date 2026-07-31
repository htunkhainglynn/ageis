import pytest
from cryptography.fernet import Fernet
from fastapi import status

from app.core.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def configure_internal_policy_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide ephemeral credentials for internal policy contract tests."""
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "test-internal-token")
    monkeypatch.setattr(
        settings,
        "JWT_CONFIG_ENCRYPTION_KEY",
        Fernet.generate_key().decode(),
    )


async def test_proxy_snapshot_returns_active_jwt_and_rate_limit_policies(
    client,
    seeded_users,
) -> None:
    """Verify the data plane receives only active enforcement configuration."""
    jwt_create = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Proxy HS config",
            "algorithm": "HS256",
            "signing_key": "proxy-shared-signing-secret",
            "public_key": None,
            "issuer": "aegis-issuer",
            "audience": "aegis-api",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    assert jwt_create.status_code == status.HTTP_201_CREATED
    jwt_id = jwt_create.json()["data"]["id"]
    assert (await client.post(f"/api/v1/jwt-configs/{jwt_id}/activate")).status_code == 200

    active_rule = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Global proxy rule",
            "scope_type": "global",
            "scope_value": None,
            "algorithm": "fixed_window",
            "limit_count": 20,
            "window_seconds": 60,
            "status": "active",
        },
    )
    disabled_rule = await client.post(
        "/api/v1/rate-limit-rules",
        json={
            "name": "Disabled route rule",
            "scope_type": "route",
            "scope_value": "/disabled",
            "algorithm": "sliding_window",
            "limit_count": 10,
            "window_seconds": 30,
            "status": "disabled",
        },
    )
    assert active_rule.status_code == status.HTTP_201_CREATED
    assert disabled_rule.status_code == status.HTTP_201_CREATED
    active_block = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "203.0.113.44", "reason": "Active proxy block"},
    )
    disabled_block = await client.post(
        "/api/v1/ip-blocks",
        json={
            "ip_address": "2001:db8::44",
            "reason": "Disabled proxy block",
            "status": "disabled",
        },
    )
    assert active_block.status_code == status.HTTP_201_CREATED
    assert disabled_block.status_code == status.HTTP_201_CREATED

    response = await client.get(
        "/api/v1/internal/proxy-config",
        headers={"X-Aegis-Internal-Token": "test-internal-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["jwt"] == {
        "id": jwt_id,
        "algorithm": "HS256",
        "verification_key": "proxy-shared-signing-secret",
        "issuer": "aegis-issuer",
        "audience": "aegis-api",
    }
    assert len(data["rate_limit_rules"]) == 1
    assert data["rate_limit_rules"][0]["id"] == active_rule.json()["data"]["id"]
    assert data["rate_limit_rules"][0]["scope_type"] == "global"
    assert data["blocked_ip_addresses"] == ["203.0.113.44"]


async def test_proxy_snapshot_uses_public_key_for_asymmetric_jwt(
    client,
    seeded_users,
) -> None:
    """Verify asymmetric policy never sends private signing material."""
    create_response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Proxy RS config",
            "algorithm": "RS256",
            "signing_key": "private-signing-key",
            "public_key": "public-verification-key",
            "issuer": None,
            "audience": None,
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    config_id = create_response.json()["data"]["id"]
    await client.post(f"/api/v1/jwt-configs/{config_id}/activate")

    response = await client.get(
        "/api/v1/internal/proxy-config",
        headers={"X-Aegis-Internal-Token": "test-internal-token"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["data"]["jwt"]["verification_key"] == "public-verification-key"
    assert "private-signing-key" not in response.text


async def test_proxy_snapshot_requires_internal_authentication(
    client,
    seeded_users,
) -> None:
    """Verify enforcement material is not exposed through the public API."""
    response = await client.get("/api/v1/internal/proxy-config")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["errorCode"] == "INTERNAL_API_UNAUTHORIZED"

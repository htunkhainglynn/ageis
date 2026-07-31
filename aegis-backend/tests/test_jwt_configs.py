import pytest
from cryptography.fernet import Fernet
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.jwt_config import JWTConfig, JWTConfigStatus
from app.services.jwt_config_service import JWTConfigService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def override_admin_and_encryption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use deterministic admin checks and ephemeral encryption keys in tests."""

    def is_admin_user(_: JWTConfigService, actor_user) -> bool:
        return actor_user.id == 1

    monkeypatch.setattr(JWTConfigService, "_is_admin_user", is_admin_user)
    monkeypatch.setattr(settings, "JWT_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())


async def test_create_jwt_config_encrypts_signing_key_and_returns_masked_response(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify create stores encrypted signing key and returns masked previews only."""
    raw_signing_key = "super-secret-signing-key-1234"

    response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Primary HS config",
            "algorithm": "HS256",
            "signing_key": raw_signing_key,
            "public_key": None,
            "issuer": "aegis",
            "audience": "dashboard",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "disabled"
    assert payload["data"]["signing_key_masked"] == f"****{raw_signing_key[-4:]}"
    assert payload["data"]["public_key_masked"] is None

    result = await db_session.execute(select(JWTConfig).where(JWTConfig.name == "Primary HS config"))
    stored = result.scalar_one()
    assert stored.signing_key != raw_signing_key

    decrypted_signing_key = Fernet(settings.JWT_CONFIG_ENCRYPTION_KEY.encode()).decrypt(
        stored.signing_key.encode()
    ).decode()
    assert decrypted_signing_key == raw_signing_key


async def test_create_jwt_config_rejects_missing_public_key_for_rs256(client, seeded_users) -> None:
    """Verify RS256 requires a public key."""
    response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "RS config",
            "algorithm": "RS256",
            "signing_key": "private-key",
            "public_key": None,
            "issuer": "aegis",
            "audience": "dashboard",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errorCode"] == "REQUEST_VALIDATION_ERROR"


async def test_create_jwt_config_rejects_public_key_for_hs256(client, seeded_users) -> None:
    """Verify HS256 must not carry public key material."""
    response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Invalid HS config",
            "algorithm": "HS256",
            "signing_key": "shared-secret",
            "public_key": "should-not-exist",
            "issuer": "aegis",
            "audience": "dashboard",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["errorCode"] == "REQUEST_VALIDATION_ERROR"


async def test_admin_only_enforcement_for_all_jwt_config_endpoints(client, seeded_users) -> None:
    """Verify non-admin users cannot access JWT config endpoints."""
    app.state.test_actor_subject = "2"

    create_response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Member config",
            "algorithm": "HS256",
            "signing_key": "secret-value",
            "public_key": None,
            "issuer": "aegis",
            "audience": "dashboard",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    list_response = await client.get("/api/v1/jwt-configs")

    assert create_response.status_code == status.HTTP_403_FORBIDDEN
    assert list_response.status_code == status.HTTP_403_FORBIDDEN

    app.state.test_actor_subject = "1"
    admin_create = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Admin config",
            "algorithm": "HS256",
            "signing_key": "secret-admin-value",
            "public_key": None,
            "issuer": "aegis",
            "audience": "dashboard",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    config_id = admin_create.json()["data"]["id"]

    app.state.test_actor_subject = "2"
    get_response = await client.get(f"/api/v1/jwt-configs/{config_id}")
    patch_response = await client.patch(
        f"/api/v1/jwt-configs/{config_id}",
        json={"issuer": "new-issuer"},
    )
    activate_response = await client.post(f"/api/v1/jwt-configs/{config_id}/activate")
    delete_response = await client.delete(f"/api/v1/jwt-configs/{config_id}")

    assert get_response.status_code == status.HTTP_403_FORBIDDEN
    assert patch_response.status_code == status.HTTP_403_FORBIDDEN
    assert activate_response.status_code == status.HTTP_403_FORBIDDEN
    assert delete_response.status_code == status.HTTP_403_FORBIDDEN


async def test_activate_jwt_config_keeps_single_active_record(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify activation deactivates prior active config and keeps one active."""
    first_create = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Config A",
            "algorithm": "HS256",
            "signing_key": "secret-a-key",
            "public_key": None,
            "issuer": "issuer-a",
            "audience": "audience-a",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    second_create = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Config B",
            "algorithm": "HS256",
            "signing_key": "secret-b-key",
            "public_key": None,
            "issuer": "issuer-b",
            "audience": "audience-b",
            "access_token_ttl_seconds": 1200,
            "refresh_token_ttl_seconds": 604800,
        },
    )

    first_id = first_create.json()["data"]["id"]
    second_id = second_create.json()["data"]["id"]

    activate_first = await client.post(f"/api/v1/jwt-configs/{first_id}/activate")
    assert activate_first.status_code == status.HTTP_200_OK
    assert activate_first.json()["data"]["status"] == "active"

    activate_second = await client.post(f"/api/v1/jwt-configs/{second_id}/activate")
    assert activate_second.status_code == status.HTTP_200_OK
    assert activate_second.json()["data"]["status"] == "active"

    result = await db_session.execute(select(JWTConfig).order_by(JWTConfig.id.asc()))
    configs = list(result.scalars().all())
    assert len(configs) == 2
    assert configs[0].status == JWTConfigStatus.DISABLED.value
    assert configs[1].status == JWTConfigStatus.ACTIVE.value


async def test_update_and_get_jwt_config_masks_keys_and_validates_ttls(client, seeded_users) -> None:
    """Verify update behavior, masked key output, and TTL validation."""
    create_response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Config update target",
            "algorithm": "HS256",
            "signing_key": "signing-key-9999",
            "public_key": None,
            "issuer": "issuer-x",
            "audience": "audience-x",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    config_id = create_response.json()["data"]["id"]

    invalid_update = await client.patch(
        f"/api/v1/jwt-configs/{config_id}",
        json={
            "access_token_ttl_seconds": 1000,
            "refresh_token_ttl_seconds": 900,
        },
    )
    assert invalid_update.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid_update.json()["errorCode"] == "JWT_CONFIG_INVALID_TTL"

    valid_update = await client.patch(
        f"/api/v1/jwt-configs/{config_id}",
        json={
            "issuer": "issuer-y",
            "audience": "audience-y",
            "access_token_ttl_seconds": 600,
            "refresh_token_ttl_seconds": 3600,
        },
    )
    assert valid_update.status_code == status.HTTP_200_OK
    updated = valid_update.json()["data"]
    assert updated["issuer"] == "issuer-y"
    assert updated["audience"] == "audience-y"
    assert updated["access_token_ttl_seconds"] == 600
    assert updated["refresh_token_ttl_seconds"] == 3600
    assert updated["signing_key_masked"].startswith("****")

    get_response = await client.get(f"/api/v1/jwt-configs/{config_id}")
    assert get_response.status_code == status.HTTP_200_OK
    fetched = get_response.json()["data"]
    assert fetched["signing_key_masked"].startswith("****")
    assert fetched["public_key_masked"] is None


async def test_disable_rejects_active_jwt_config(client, seeded_users) -> None:
    """Verify active config cannot be disabled directly."""
    create_response = await client.post(
        "/api/v1/jwt-configs",
        json={
            "name": "Config active guard",
            "algorithm": "HS256",
            "signing_key": "signing-active-3333",
            "public_key": None,
            "issuer": "issuer",
            "audience": "audience",
            "access_token_ttl_seconds": 900,
            "refresh_token_ttl_seconds": 604800,
        },
    )
    config_id = create_response.json()["data"]["id"]

    activate_response = await client.post(f"/api/v1/jwt-configs/{config_id}/activate")
    assert activate_response.status_code == status.HTTP_200_OK

    delete_response = await client.delete(f"/api/v1/jwt-configs/{config_id}")
    assert delete_response.status_code == status.HTTP_400_BAD_REQUEST
    payload = delete_response.json()
    assert payload["errorCode"] == "JWT_CONFIG_ACTIVE_DELETE_FORBIDDEN"

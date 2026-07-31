import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.config import settings
from app.models.api_key import APIKey, APIKeyStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def configure_internal_api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use an ephemeral internal credential for proxy-contract tests."""
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "test-internal-token")


async def test_create_api_key_returns_raw_key_once(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify API key creation returns raw key and stores only hash."""
    response = await client.post(
        "/api/v1/api-keys",
        json={
            "name": "Primary key",
            "scopes": ["users:read", "users:write"],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["name"] == "Primary key"
    assert payload["data"]["status"] == APIKeyStatus.ACTIVE.value

    raw_key = payload["data"]["api_key"]
    assert isinstance(raw_key, str)
    assert len(raw_key) > 8
    assert payload["data"]["key_prefix"] == raw_key[:8]

    result = await db_session.execute(select(APIKey).where(APIKey.owner_id == 1))
    stored_key = result.scalar_one()
    assert stored_key.key_hash != raw_key
    assert raw_key not in stored_key.key_hash


async def test_list_api_keys_excludes_raw_key(client, seeded_users) -> None:
    """Verify API key listing returns metadata without raw key material."""
    first_create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Key One", "scopes": ["read"]},
    )
    second_create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Key Two", "scopes": ["read", "write"]},
    )

    assert first_create.status_code == status.HTTP_201_CREATED
    assert second_create.status_code == status.HTTP_201_CREATED

    response = await client.get("/api/v1/api-keys?skip=0&limit=10")

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["total"] == 2
    assert len(payload["data"]["items"]) == 2

    for key_item in payload["data"]["items"]:
        assert "api_key" not in key_item
        assert "key_hash" not in key_item


async def test_revoke_api_key_sets_status_revoked(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify API key revoke endpoint soft-revokes keys."""
    create_response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Revokable key", "scopes": ["read"]},
    )
    key_id = create_response.json()["data"]["id"]

    revoke_response = await client.delete(f"/api/v1/api-keys/{key_id}")

    assert revoke_response.status_code == status.HTTP_200_OK
    assert revoke_response.json()["status"] == "success"

    result = await db_session.execute(select(APIKey).where(APIKey.id == key_id))
    stored_key = result.scalar_one()
    assert stored_key.status == APIKeyStatus.REVOKED.value


async def test_user_cannot_revoke_another_users_key(client, seeded_users) -> None:
    """Verify ownership enforcement blocks revocation by other users."""
    create_response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Owner only key", "scopes": ["read"]},
    )
    key_id = create_response.json()["data"]["id"]

    app.state.test_actor_subject = "2"
    forbidden_response = await client.delete(f"/api/v1/api-keys/{key_id}")

    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    payload = forbidden_response.json()
    assert payload["status"] == "error"
    assert payload["errorCode"] == "API_KEY_FORBIDDEN"


async def test_admin_lists_all_keys_while_consumer_lists_only_owned_keys(
    client,
    seeded_users,
) -> None:
    """Verify API-key list visibility follows the role and ownership matrix."""
    admin_create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Admin key", "scopes": ["read"]},
    )
    assert admin_create.status_code == status.HTTP_201_CREATED

    app.state.test_actor_subject = "2"
    consumer_create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Consumer key", "scopes": ["read"]},
    )
    assert consumer_create.status_code == status.HTTP_201_CREATED

    consumer_list = await client.get("/api/v1/api-keys")
    assert consumer_list.status_code == status.HTTP_200_OK
    assert consumer_list.json()["data"]["total"] == 1
    assert consumer_list.json()["data"]["items"][0]["name"] == "Consumer key"

    app.state.test_actor_subject = "1"
    admin_list = await client.get("/api/v1/api-keys")
    assert admin_list.status_code == status.HTTP_200_OK
    assert admin_list.json()["data"]["total"] == 2


async def test_viewer_cannot_access_api_key_management(client, seeded_users) -> None:
    """Verify Viewer has no API-key management access."""
    app.state.test_actor_subject = "3"

    list_response = await client.get("/api/v1/api-keys")
    create_response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Forbidden viewer key", "scopes": ["read"]},
    )

    assert list_response.status_code == status.HTTP_403_FORBIDDEN
    assert create_response.status_code == status.HTTP_403_FORBIDDEN
    assert list_response.json()["errorCode"] == "API_KEY_FORBIDDEN"


async def test_internal_validation_accepts_active_key_without_reexposing_it(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify the proxy contract checks bcrypt and returns non-secret policy data."""
    create_response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Proxy key", "scopes": ["orders:read"]},
    )
    raw_key = create_response.json()["data"]["api_key"]
    key_id = create_response.json()["data"]["id"]

    response = await client.post(
        "/api/v1/api-keys/validate",
        headers={"X-Aegis-Internal-Token": "test-internal-token"},
        json={"api_key": raw_key},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["id"] == key_id
    assert data["scopes"] == ["orders:read"]
    assert "api_key" not in data
    assert "key_hash" not in data
    assert raw_key not in response.text

    result = await db_session.execute(select(APIKey).where(APIKey.id == key_id))
    assert result.scalar_one().last_used_at is not None


async def test_internal_validation_requires_shared_credential(
    client,
    seeded_users,
) -> None:
    """Verify the validation oracle is unavailable to unauthenticated callers."""
    create_response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Protected validation key", "scopes": []},
    )
    raw_key = create_response.json()["data"]["api_key"]

    missing_response = await client.post(
        "/api/v1/api-keys/validate",
        json={"api_key": raw_key},
    )
    wrong_response = await client.post(
        "/api/v1/api-keys/validate",
        headers={"X-Aegis-Internal-Token": "wrong-token"},
        json={"api_key": raw_key},
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert missing_response.json()["errorCode"] == "INTERNAL_API_UNAUTHORIZED"


async def test_internal_validation_rejects_unknown_revoked_and_expired_keys(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify invalid key states map to the proxy client's documented errors."""
    headers = {"X-Aegis-Internal-Token": "test-internal-token"}

    unknown_response = await client.post(
        "/api/v1/api-keys/validate",
        headers=headers,
        json={"api_key": "ak_unknown_key_material"},
    )
    assert unknown_response.status_code == status.HTTP_404_NOT_FOUND
    assert unknown_response.json()["errorCode"] == "API_KEY_NOT_FOUND"

    revoked_create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Revoked proxy key", "scopes": []},
    )
    revoked_key = revoked_create.json()["data"]["api_key"]
    await client.delete(f"/api/v1/api-keys/{revoked_create.json()['data']['id']}")
    revoked_response = await client.post(
        "/api/v1/api-keys/validate",
        headers=headers,
        json={"api_key": revoked_key},
    )
    assert revoked_response.status_code == status.HTTP_403_FORBIDDEN
    assert revoked_response.json()["errorCode"] == "API_KEY_REVOKED"

    expired_create = await client.post(
        "/api/v1/api-keys",
        json={
            "name": "Expired proxy key",
            "scopes": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    expired_key = expired_create.json()["data"]["api_key"]
    expired_id = expired_create.json()["data"]["id"]
    result = await db_session.execute(select(APIKey).where(APIKey.id == expired_id))
    stored_expired_key = result.scalar_one()
    stored_expired_key.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    expired_response = await client.post(
        "/api/v1/api-keys/validate",
        headers=headers,
        json={"api_key": expired_key},
    )
    assert expired_response.status_code == status.HTTP_403_FORBIDDEN
    assert expired_response.json()["errorCode"] == "API_KEY_EXPIRED"

import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.api_key import APIKey, APIKeyStatus

pytestmark = pytest.mark.asyncio


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

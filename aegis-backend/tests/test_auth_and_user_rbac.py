import pytest
from fastapi import status

from app.core.config import settings
from app.core.security import decode_token
from app.main import app
from app.models.user import UserRole

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def isolate_token_storage(monkeypatch: pytest.MonkeyPatch) -> set[str]:
    """Keep authentication tests independent of a running Redis instance."""
    active_tokens: set[str] = set()

    async def store_token(token: str, _subject: str, _token_type: str, _ttl: int) -> None:
        active_tokens.add(token)

    async def is_token_active(token: str, _subject: str, _token_type: str) -> bool:
        return token in active_tokens

    async def revoke_token(token: str, _subject: str, _token_type: str) -> None:
        active_tokens.discard(token)

    monkeypatch.setattr("app.services.auth_service.store_token", store_token)
    monkeypatch.setattr("app.services.auth_service.is_token_active", is_token_active)
    monkeypatch.setattr("app.services.auth_service.revoke_token", revoke_token)
    return active_tokens


async def test_public_registration_defaults_to_api_consumer(client) -> None:
    """Verify public registration cannot self-assign a privileged role."""
    privileged_response = await client.post(
        "/api/v1/users",
        json={
            "email": "new-user@example.com",
            "full_name": "New User",
            "password": "Passw0rd!",
            "role": "admin",
        },
    )
    assert privileged_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "new-user@example.com",
            "full_name": "New User",
            "password": "Passw0rd!",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["data"]["role"] == UserRole.API_CONSUMER.value


async def test_bootstrap_allowlist_can_create_initial_admin(
    client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify initial administration is explicit and environment-controlled."""
    monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAILS", "first-admin@example.com")

    response = await client.post(
        "/api/v1/users",
        json={
            "email": "first-admin@example.com",
            "full_name": "First Admin",
            "password": "Passw0rd!",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["data"]["role"] == UserRole.ADMIN.value


async def test_login_and_refresh_tokens_include_current_email_and_role(
    client,
    seeded_users,
) -> None:
    """Verify the dashboard can derive authorization state from in-memory tokens."""
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "Passw0rd!"},
    )

    assert login_response.status_code == status.HTTP_200_OK
    tokens = login_response.json()["data"]
    access_payload = decode_token(tokens["access_token"])
    assert access_payload.email == "owner@example.com"
    assert access_payload.role == UserRole.ADMIN.value

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == status.HTTP_200_OK
    refreshed_payload = decode_token(refresh_response.json()["data"]["access_token"])
    assert refreshed_payload.email == "owner@example.com"
    assert refreshed_payload.role == UserRole.ADMIN.value


async def test_logout_revokes_the_access_token(
    client,
    seeded_users,
    isolate_token_storage: set[str],
) -> None:
    """Verify logout removes the issued access token from server-side storage."""
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "Passw0rd!"},
    )
    access_token = login_response.json()["data"]["access_token"]
    assert access_token in isolate_token_storage

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"access_token": access_token},
    )

    assert logout_response.status_code == status.HTTP_200_OK
    assert access_token not in isolate_token_storage


async def test_user_management_is_admin_only(client, seeded_users) -> None:
    """Verify API consumers and viewers cannot manage users."""
    for subject in ("2", "3"):
        app.state.test_actor_subject = subject
        list_response = await client.get("/api/v1/users")
        update_response = await client.put(
            "/api/v1/users/1",
            json={"full_name": "Unauthorized update"},
        )
        delete_response = await client.delete("/api/v1/users/1")

        assert list_response.status_code == status.HTTP_403_FORBIDDEN
        assert update_response.status_code == status.HTTP_403_FORBIDDEN
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN


async def test_admin_can_assign_roles_and_list_users(client, seeded_users) -> None:
    """Verify administrators can perform the role-management workflow."""
    update_response = await client.put(
        "/api/v1/users/2",
        json={"role": "viewer"},
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["role"] == UserRole.VIEWER.value

    list_response = await client.get("/api/v1/users")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["data"]["total"] == 3


async def test_admin_delete_soft_deactivates_user(client, seeded_users) -> None:
    """Verify deleting a user preserves the record and ownership history."""
    delete_response = await client.delete("/api/v1/users/2")
    assert delete_response.status_code == status.HTTP_200_OK

    get_response = await client.get("/api/v1/users/2")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["is_active"] is False

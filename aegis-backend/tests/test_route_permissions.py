import pytest
from cryptography.fernet import Fernet
from fastapi import status

from app.main import app
from app.core.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def configure_internal_policy_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "test-internal-token")
    monkeypatch.setattr(settings, "JWT_CONFIG_ENCRYPTION_KEY", Fernet.generate_key().decode())


async def test_route_permission_crud_and_active_proxy_snapshot(client, seeded_users):
    created = await client.post(
        "/api/v1/route-permissions",
        json={"method": "GET", "path_pattern": "/api/echo", "required_scope": "echo:read"},
    )
    assert created.status_code == status.HTTP_201_CREATED
    permission_id = created.json()["data"]["id"]

    listed = await client.get("/api/v1/route-permissions?status=active")
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    fetched = await client.get(f"/api/v1/route-permissions/{permission_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["required_scope"] == "echo:read"

    updated = await client.patch(
        f"/api/v1/route-permissions/{permission_id}",
        json={"required_scope": "echo:write", "path_pattern": "/api/echo/write"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["path_pattern"] == "/api/echo/write"

    disabled = await client.delete(f"/api/v1/route-permissions/{permission_id}")
    assert disabled.status_code == 200
    assert (await client.get(f"/api/v1/route-permissions/{permission_id}")).json()["data"]["status"] == "disabled"

    proxy_config = await client.get(
        "/api/v1/internal/proxy-config",
        headers={"X-Aegis-Internal-Token": "test-internal-token"},
    )
    assert proxy_config.status_code == 200
    assert proxy_config.json()["data"]["route_permissions"] == []

    active = await client.post(
        "/api/v1/route-permissions",
        json={"method": "POST", "path_pattern": "/api/echo", "required_scope": "echo:write"},
    )
    assert active.status_code == status.HTTP_201_CREATED
    proxy_config = await client.get(
        "/api/v1/internal/proxy-config",
        headers={"X-Aegis-Internal-Token": "test-internal-token"},
    )
    assert proxy_config.json()["data"]["route_permissions"] == [
        {"id": active.json()["data"]["id"], "method": "POST", "path_pattern": "/api/echo", "required_scope": "echo:write"}
    ]


async def test_route_permission_validation_and_duplicate_active_scope(client, seeded_users):
    invalid_payloads = [
        {"method": "FETCH", "path_pattern": "/x", "required_scope": "x:read"},
        {"method": "GET", "path_pattern": "x", "required_scope": "x:read"},
        {"method": "GET", "path_pattern": "/x/*", "required_scope": "x:read"},
        {"method": "GET", "path_pattern": "/x", "required_scope": "invalid"},
    ]
    for payload in invalid_payloads:
        assert (await client.post("/api/v1/route-permissions", json=payload)).status_code == 422

    payload = {"method": "GET", "path_pattern": "/duplicate", "required_scope": "demo:read"}
    assert (await client.post("/api/v1/route-permissions", json=payload)).status_code == 201
    duplicate = await client.post("/api/v1/route-permissions", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json()["errorCode"] == "ROUTE_PERMISSION_ALREADY_ACTIVE"

    created_id = (await client.get("/api/v1/route-permissions")).json()["data"]["items"][0]["id"]
    assert (await client.patch(f"/api/v1/route-permissions/{created_id}", json={"path_pattern": None})).status_code == 422


async def test_route_permission_endpoints_are_admin_only(client, seeded_users):
    app.state.test_actor_subject = "2"
    responses = [
        await client.get("/api/v1/route-permissions"),
        await client.post("/api/v1/route-permissions", json={"method": "GET", "path_pattern": "/x", "required_scope": "x:read"}),
    ]
    assert all(response.status_code == 403 for response in responses)

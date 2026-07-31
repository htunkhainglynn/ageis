import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.ip_block import IPBlock, IPBlockSource, IPBlockStatus

pytestmark = pytest.mark.asyncio


async def test_admin_can_manage_manual_ip_block(
    client,
    db_session: AsyncSession,
    seeded_users,
) -> None:
    """Verify create, read, update, filtering, and soft deletion."""
    create_response = await client.post(
        "/api/v1/ip-blocks",
        json={
            "ip_address": "2001:0db8:0000:0000:0000:0000:0000:0001",
            "reason": "Repeated credential attacks",
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    created = create_response.json()["data"]
    assert created["ip_address"] == "2001:db8::1"
    assert created["source"] == IPBlockSource.MANUAL.value
    assert created["status"] == IPBlockStatus.ACTIVE.value
    block_id = created["id"]

    list_response = await client.get("/api/v1/ip-blocks?status=active")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["data"]["total"] == 1
    assert list_response.json()["data"]["items"][0]["id"] == block_id

    update_response = await client.patch(
        f"/api/v1/ip-blocks/{block_id}",
        json={"reason": "Confirmed malicious source"},
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["reason"] == "Confirmed malicious source"

    disable_response = await client.delete(f"/api/v1/ip-blocks/{block_id}")
    assert disable_response.status_code == status.HTTP_200_OK
    result = await db_session.execute(select(IPBlock).where(IPBlock.id == block_id))
    assert result.scalar_one().status == IPBlockStatus.DISABLED.value


async def test_ip_block_rejects_invalid_and_duplicate_active_addresses(
    client,
    seeded_users,
) -> None:
    """Verify address validation and one-active-block-per-address behavior."""
    invalid_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "not-an-ip", "reason": "Invalid"},
    )
    assert invalid_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    first_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "203.0.113.10", "reason": "First"},
    )
    assert first_response.status_code == status.HTTP_201_CREATED

    duplicate_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "203.0.113.10", "reason": "Duplicate"},
    )
    assert duplicate_response.status_code == status.HTTP_409_CONFLICT
    assert duplicate_response.json()["errorCode"] == "IP_BLOCK_ALREADY_ACTIVE"


async def test_disabled_address_can_be_blocked_again_but_not_reactivated_twice(
    client,
    seeded_users,
) -> None:
    """Verify soft-deleted history does not prevent a new active block."""
    original_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "198.51.100.20", "reason": "Original"},
    )
    original_id = original_response.json()["data"]["id"]
    assert (await client.delete(f"/api/v1/ip-blocks/{original_id}")).status_code == status.HTTP_200_OK

    replacement_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "198.51.100.20", "reason": "Replacement"},
    )
    assert replacement_response.status_code == status.HTTP_201_CREATED

    reactivate_response = await client.patch(
        f"/api/v1/ip-blocks/{original_id}",
        json={"status": "active"},
    )
    assert reactivate_response.status_code == status.HTTP_409_CONFLICT
    assert reactivate_response.json()["errorCode"] == "IP_BLOCK_ALREADY_ACTIVE"


async def test_all_ip_block_endpoints_are_admin_only(client, seeded_users) -> None:
    """Verify Viewer and API Consumer roles cannot inspect or mutate blocks."""
    create_response = await client.post(
        "/api/v1/ip-blocks",
        json={"ip_address": "192.0.2.30", "reason": "Admin block"},
    )
    block_id = create_response.json()["data"]["id"]

    for actor_subject in ("2", "3"):
        app.state.test_actor_subject = actor_subject
        responses = [
            await client.get("/api/v1/ip-blocks"),
            await client.get(f"/api/v1/ip-blocks/{block_id}"),
            await client.post(
                "/api/v1/ip-blocks",
                json={"ip_address": "192.0.2.31", "reason": "Forbidden"},
            ),
            await client.patch(
                f"/api/v1/ip-blocks/{block_id}",
                json={"reason": "Forbidden"},
            ),
            await client.delete(f"/api/v1/ip-blocks/{block_id}"),
        ]
        assert all(response.status_code == status.HTTP_403_FORBIDDEN for response in responses)

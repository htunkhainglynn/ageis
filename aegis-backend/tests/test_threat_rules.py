import pytest
from fastapi import status

from app.main import app

pytestmark = pytest.mark.asyncio


async def test_admin_threat_rule_crud_and_validation(client, seeded_users) -> None:
    invalid = await client.post("/api/v1/threat-rules", json={
        "name": "Invalid", "pattern": "(?=lookahead)", "severity": "high"
    })
    assert invalid.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    created = await client.post("/api/v1/threat-rules", json={
        "name": "Traversal", "pattern": r"(?i)(\\.\\./|%2e%2e)",
        "severity": "high",
    })
    assert created.status_code == status.HTTP_201_CREATED
    rule_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "active"

    listed = await client.get("/api/v1/threat-rules?status=active")
    assert listed.status_code == 200
    assert listed.json()["data"]["total"] == 1

    updated = await client.patch(f"/api/v1/threat-rules/{rule_id}", json={
        "severity": "critical", "name": "Traversal critical"
    })
    assert updated.status_code == 200
    assert updated.json()["data"]["severity"] == "critical"

    disabled = await client.delete(f"/api/v1/threat-rules/{rule_id}")
    assert disabled.status_code == 200
    fetched = await client.get(f"/api/v1/threat-rules/{rule_id}")
    assert fetched.json()["data"]["status"] == "disabled"


async def test_threat_rule_endpoints_are_admin_only(client, seeded_users) -> None:
    created = await client.post("/api/v1/threat-rules", json={
        "name": "Scanner", "pattern": r"(?i)/\\.env", "severity": "medium"
    })
    rule_id = created.json()["data"]["id"]

    for subject in ("2", "3"):
        app.state.test_actor_subject = subject
        responses = [
            await client.get("/api/v1/threat-rules"),
            await client.get(f"/api/v1/threat-rules/{rule_id}"),
            await client.post("/api/v1/threat-rules", json={
                "name": "No", "pattern": "bad", "severity": "low"
            }),
            await client.patch(f"/api/v1/threat-rules/{rule_id}", json={"severity": "low"}),
            await client.delete(f"/api/v1/threat-rules/{rule_id}"),
        ]
        assert all(response.status_code == status.HTTP_403_FORBIDDEN for response in responses)

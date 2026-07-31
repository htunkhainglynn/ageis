import pytest
from fastapi import status

from app.core.config import settings
from app.main import app

pytestmark = pytest.mark.asyncio


async def _ingest(client, event_type: str, status_code: int) -> None:
    response = await client.post(
        "/api/v1/internal/security-events",
        headers={"X-Aegis-Internal-Token": "analytics-internal-token"},
        json={
            "event_type": event_type,
            "source_ip": "203.0.113.80",
            "api_key_id": None,
            "rule_id": 4 if event_type == "threat_detected" else None,
            "method": "get",
            "path": "/orders?limit=10",
            "status_code": status_code,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["data"]["method"] == "GET"


async def test_internal_ingestion_and_role_scoped_analytics(
    client, seeded_users, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "analytics-internal-token")
    await _ingest(client, "request_forwarded", 200)
    await _ingest(client, "threat_detected", 403)
    await _ingest(client, "rate_limited", 429)
    await _ingest(client, "upstream_error", 502)

    summary = await client.get("/api/v1/analytics/summary?hours=24")
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["total_requests"] == 4
    assert data["forwarded_requests"] == 1
    assert data["blocked_requests"] == 2
    assert data["rate_limited_requests"] == 1
    assert data["server_errors"] == 1
    assert data["events_by_type"]["threat_detected"] == 1

    app.state.test_actor_subject = "3"
    viewer_events = await client.get("/api/v1/analytics/events?hours=24")
    assert viewer_events.status_code == 200
    assert viewer_events.json()["data"]["total"] == 4

    app.state.test_actor_subject = "2"
    assert (await client.get("/api/v1/analytics/summary")).status_code == 403
    assert (await client.get("/api/v1/analytics/events")).status_code == 403


async def test_security_event_ingestion_requires_internal_auth(
    client, seeded_users, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "INTERNAL_API_TOKEN", "analytics-internal-token")
    response = await client.post(
        "/api/v1/internal/security-events",
        json={
            "event_type": "request_forwarded",
            "source_ip": "203.0.113.80",
            "method": "GET",
            "path": "/",
            "status_code": 200,
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

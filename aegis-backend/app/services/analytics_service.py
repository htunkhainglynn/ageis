from datetime import datetime, timedelta, timezone

from app.core.exceptions import ForbiddenException
from app.models.user import User, UserRole
from app.repositories.security_event_repository import SecurityEventRepository
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    SecurityEventCreateRequest,
    SecurityEventListResponse,
    SecurityEventResponse,
)


class AnalyticsService:
    """Persist sanitized data-plane outcomes and aggregate operator analytics."""

    def __init__(self, repository: SecurityEventRepository) -> None:
        self.repository = repository

    @staticmethod
    def _assert_viewer(actor: User) -> None:
        if actor.role not in {UserRole.ADMIN.value, UserRole.VIEWER.value}:
            raise ForbiddenException(
                error_code="ANALYTICS_FORBIDDEN",
                message="You are not allowed to view analytics.",
            )

    async def ingest(self, payload: SecurityEventCreateRequest) -> SecurityEventResponse:
        event = await self.repository.create_event(payload)
        return SecurityEventResponse.model_validate(event)

    async def list_events(
        self, actor: User, hours: int, skip: int, limit: int
    ) -> SecurityEventListResponse:
        self._assert_viewer(actor)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        events = await self.repository.list_events(since, skip, limit)
        return SecurityEventListResponse(
            items=[SecurityEventResponse.model_validate(event) for event in events],
            skip=skip,
            limit=limit,
            total=await self.repository.count_events(since),
        )

    async def summary(self, actor: User, hours: int) -> AnalyticsSummaryResponse:
        self._assert_viewer(actor)
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        by_type, totals = await self.repository.summary(since)
        return AnalyticsSummaryResponse(
            hours=hours,
            total_requests=totals["total"],
            forwarded_requests=totals["forwarded"],
            blocked_requests=totals["blocked"],
            rate_limited_requests=totals["limited"],
            server_errors=totals["errors"],
            events_by_type=by_type,
        )

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import ForbiddenException
from app.models.ip_block import IPBlockSource, IPBlockStatus
from app.models.user import User, UserRole
from app.repositories.ip_block_repository import IPBlockRepository
from app.repositories.security_event_repository import SecurityEventRepository
from app.schemas.ip_block import IPBlockCreateInDB
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    SecurityEventCreateRequest,
    SecurityEventListResponse,
    SecurityEventResponse,
)


class AnalyticsService:
    """Persist sanitized data-plane outcomes and aggregate operator analytics."""

    def __init__(
        self,
        repository: SecurityEventRepository,
        ip_block_repository: IPBlockRepository,
    ) -> None:
        self.repository = repository
        self.ip_block_repository = ip_block_repository

    @staticmethod
    def _assert_viewer(actor: User) -> None:
        if actor.role not in {UserRole.ADMIN.value, UserRole.VIEWER.value}:
            raise ForbiddenException(
                error_code="ANALYTICS_FORBIDDEN",
                message="You are not allowed to view analytics.",
            )

    async def ingest(self, payload: SecurityEventCreateRequest) -> SecurityEventResponse:
        event = await self.repository.create_event(payload)
        await self._auto_block_if_needed(payload)
        return SecurityEventResponse.model_validate(event)

    async def _auto_block_if_needed(self, payload: SecurityEventCreateRequest) -> None:
        """Promote repeated recent violations into a distributed automatic block."""
        if (
            not settings.AUTO_IP_BLOCK_ENABLED
            or payload.event_type not in {"threat_detected", "rate_limited"}
            or payload.source_ip == "unknown"
        ):
            return
        since = datetime.now(timezone.utc) - timedelta(
            seconds=settings.AUTO_IP_BLOCK_WINDOW_SECONDS
        )
        violations = await self.repository.count_violations(payload.source_ip, since)
        if violations < settings.AUTO_IP_BLOCK_THRESHOLD:
            return
        if await self.ip_block_repository.get_active_by_ip(payload.source_ip) is not None:
            return
        try:
            await self.ip_block_repository.create_block(
                IPBlockCreateInDB(
                    ip_address=payload.source_ip,
                    reason=(
                        f"Automatically blocked after {violations} security "
                        f"violations within {settings.AUTO_IP_BLOCK_WINDOW_SECONDS} seconds"
                    ),
                    source=IPBlockSource.AUTO.value,
                    status=IPBlockStatus.ACTIVE.value,
                    created_by=None,
                )
            )
        except IntegrityError:
            # A concurrent proxy event may have created the same active block.
            await self.ip_block_repository.db.rollback()

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

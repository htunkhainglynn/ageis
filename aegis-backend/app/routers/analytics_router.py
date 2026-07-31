from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_analytics_viewer, require_internal_api_token
from app.core.database import get_db
from app.models.user import User
from app.repositories.security_event_repository import SecurityEventRepository
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    SecurityEventCreateRequest,
    SecurityEventListResponse,
    SecurityEventResponse,
)
from app.schemas.base import ApiResponse, success_response
from app.services.analytics_service import AnalyticsService

router = APIRouter(tags=["Analytics"])


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(SecurityEventRepository(db))


@router.post(
    "/internal/security-events",
    response_model=ApiResponse[SecurityEventResponse],
    status_code=status.HTTP_201_CREATED,
)
async def ingest_security_event(
    payload: SecurityEventCreateRequest,
    _: None = Depends(require_internal_api_token),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[SecurityEventResponse]:
    event = await service.ingest(payload)
    return success_response("Security event recorded.", event)


@router.get(
    "/analytics/summary",
    response_model=ApiResponse[AnalyticsSummaryResponse],
)
async def get_analytics_summary(
    hours: int = Query(default=24, ge=1, le=24 * 90),
    actor: User = Depends(require_analytics_viewer),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[AnalyticsSummaryResponse]:
    return success_response("Analytics summary fetched.", await service.summary(actor, hours))


@router.get(
    "/analytics/events",
    response_model=ApiResponse[SecurityEventListResponse],
)
async def list_security_events(
    hours: int = Query(default=24, ge=1, le=24 * 90),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    actor: User = Depends(require_analytics_viewer),
    service: AnalyticsService = Depends(get_analytics_service),
) -> ApiResponse[SecurityEventListResponse]:
    events = await service.list_events(actor, hours, skip, limit)
    return success_response("Security events fetched.", events)

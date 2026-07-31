from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_subject
from app.models.rate_limit_rule import RateLimitRuleScopeType, RateLimitRuleStatus
from app.repositories.rate_limit_rule_repository import RateLimitRuleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.rate_limit_rule import (
    RateLimitRuleCreateRequest,
    RateLimitRuleListResponse,
    RateLimitRuleResponse,
    RateLimitRuleUpdateRequest,
)
from app.services.rate_limit_rule_service import RateLimitRuleService

router = APIRouter(prefix="/rate-limit-rules", tags=["Rate Limit Rules"])


def get_rate_limit_rule_service(db: AsyncSession = Depends(get_db)) -> RateLimitRuleService:
    """Provide a request-scoped rate limit rule service instance."""
    rate_limit_rule_repository = RateLimitRuleRepository(db=db)
    user_repository = UserRepository(db=db)
    return RateLimitRuleService(
        rate_limit_rule_repository=rate_limit_rule_repository,
        user_repository=user_repository,
    )


@router.post(
    "",
    response_model=ApiResponse[RateLimitRuleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create rate limit rule",
    description="Create a new rate limit configuration rule. Admin only.",
)
async def create_rate_limit_rule(
    payload: RateLimitRuleCreateRequest,
    actor_subject: str = Depends(get_current_subject),
    rate_limit_rule_service: RateLimitRuleService = Depends(get_rate_limit_rule_service),
) -> ApiResponse[RateLimitRuleResponse]:
    """Create rate limit rule."""
    created_rule = await rate_limit_rule_service.create_rule(actor_subject=actor_subject, payload=payload)
    return success_response(message="Rate limit rule created successfully.", data=created_rule)


@router.get(
    "",
    response_model=ApiResponse[RateLimitRuleListResponse],
    summary="List rate limit rules",
    description="List rate limit configuration rules for authenticated users.",
)
async def list_rate_limit_rules(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    scope_type: RateLimitRuleScopeType | None = Query(default=None),
    status_filter: RateLimitRuleStatus | None = Query(default=None, alias="status"),
    actor_subject: str = Depends(get_current_subject),
    rate_limit_rule_service: RateLimitRuleService = Depends(get_rate_limit_rule_service),
) -> ApiResponse[RateLimitRuleListResponse]:
    """List rate limit rules with optional filters."""
    rules = await rate_limit_rule_service.list_rules(
        actor_subject=actor_subject,
        skip=skip,
        limit=limit,
        scope_type=scope_type.value if scope_type is not None else None,
        status=status_filter.value if status_filter is not None else None,
    )
    return success_response(message="Rate limit rules fetched successfully.", data=rules)


@router.get(
    "/{rule_id}",
    response_model=ApiResponse[RateLimitRuleResponse],
    summary="Get rate limit rule",
    description="Retrieve a single rate limit rule by identifier.",
)
async def get_rate_limit_rule(
    rule_id: int,
    actor_subject: str = Depends(get_current_subject),
    rate_limit_rule_service: RateLimitRuleService = Depends(get_rate_limit_rule_service),
) -> ApiResponse[RateLimitRuleResponse]:
    """Get one rate limit rule."""
    rule = await rate_limit_rule_service.get_rule(actor_subject=actor_subject, rule_id=rule_id)
    return success_response(message="Rate limit rule fetched successfully.", data=rule)


@router.patch(
    "/{rule_id}",
    response_model=ApiResponse[RateLimitRuleResponse],
    summary="Update rate limit rule",
    description="Update mutable fields of a rate limit rule. Admin only.",
)
async def update_rate_limit_rule(
    rule_id: int,
    payload: RateLimitRuleUpdateRequest,
    actor_subject: str = Depends(get_current_subject),
    rate_limit_rule_service: RateLimitRuleService = Depends(get_rate_limit_rule_service),
) -> ApiResponse[RateLimitRuleResponse]:
    """Update one rate limit rule."""
    updated_rule = await rate_limit_rule_service.update_rule(
        actor_subject=actor_subject,
        rule_id=rule_id,
        payload=payload,
    )
    return success_response(message="Rate limit rule updated successfully.", data=updated_rule)


@router.delete(
    "/{rule_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Disable rate limit rule",
    description="Soft-delete a rule by setting status=disabled. Admin only.",
)
async def disable_rate_limit_rule(
    rule_id: int,
    actor_subject: str = Depends(get_current_subject),
    rate_limit_rule_service: RateLimitRuleService = Depends(get_rate_limit_rule_service),
) -> ApiResponse[None]:
    """Disable one rate limit rule."""
    await rate_limit_rule_service.disable_rule(actor_subject=actor_subject, rule_id=rule_id)
    return success_response(message="Rate limit rule disabled successfully.", data=None)

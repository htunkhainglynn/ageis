from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models.threat_rule import ThreatRuleStatus
from app.models.user import User
from app.repositories.threat_rule_repository import ThreatRuleRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.threat_rule import (
    ThreatRuleCreateRequest, ThreatRuleListResponse, ThreatRuleResponse,
    ThreatRuleUpdateRequest,
)
from app.services.threat_rule_service import ThreatRuleService

router = APIRouter(prefix="/threat-rules", tags=["Threat Rules"])


def get_service(db: AsyncSession = Depends(get_db)) -> ThreatRuleService:
    return ThreatRuleService(ThreatRuleRepository(db))


@router.post("", response_model=ApiResponse[ThreatRuleResponse], status_code=201)
async def create_rule(payload: ThreatRuleCreateRequest, actor: User = Depends(require_admin),
                      service: ThreatRuleService = Depends(get_service)):
    return success_response("Threat rule created successfully.", await service.create(actor, payload))


@router.get("", response_model=ApiResponse[ThreatRuleListResponse])
async def list_rules(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100),
                     status_filter: ThreatRuleStatus | None = Query(None, alias="status"),
                     actor: User = Depends(require_admin),
                     service: ThreatRuleService = Depends(get_service)):
    return success_response("Threat rules fetched successfully.", await service.list(
        actor, skip, limit, status_filter.value if status_filter else None
    ))


@router.get("/{rule_id}", response_model=ApiResponse[ThreatRuleResponse])
async def get_rule(rule_id: int, actor: User = Depends(require_admin),
                   service: ThreatRuleService = Depends(get_service)):
    return success_response("Threat rule fetched successfully.", await service.get(actor, rule_id))


@router.patch("/{rule_id}", response_model=ApiResponse[ThreatRuleResponse])
async def update_rule(rule_id: int, payload: ThreatRuleUpdateRequest,
                      actor: User = Depends(require_admin),
                      service: ThreatRuleService = Depends(get_service)):
    return success_response("Threat rule updated successfully.", await service.update(actor, rule_id, payload))


@router.delete("/{rule_id}", response_model=ApiResponse[None])
async def disable_rule(rule_id: int, actor: User = Depends(require_admin),
                       service: ThreatRuleService = Depends(get_service)):
    await service.disable(actor, rule_id)
    return success_response("Threat rule disabled successfully.", None)

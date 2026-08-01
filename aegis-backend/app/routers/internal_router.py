from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_internal_api_token
from app.core.database import get_db
from app.repositories.ip_block_repository import IPBlockRepository
from app.repositories.jwt_config_repository import JWTConfigRepository
from app.repositories.rate_limit_rule_repository import RateLimitRuleRepository
from app.repositories.threat_rule_repository import ThreatRuleRepository
from app.repositories.route_permission_repository import RoutePermissionRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.proxy_config import ProxyPolicySnapshot
from app.services.proxy_config_service import ProxyConfigService

router = APIRouter(prefix="/internal", tags=["Internal"])


def get_proxy_config_service(
    db: AsyncSession = Depends(get_db),
) -> ProxyConfigService:
    """Provide a request-scoped proxy policy service."""
    return ProxyConfigService(
        jwt_config_repository=JWTConfigRepository(db=db),
        rate_limit_rule_repository=RateLimitRuleRepository(db=db),
        ip_block_repository=IPBlockRepository(db=db),
        threat_rule_repository=ThreatRuleRepository(db=db),
        route_permission_repository=RoutePermissionRepository(db=db),
    )


@router.get(
    "/proxy-config",
    response_model=ApiResponse[ProxyPolicySnapshot],
    summary="Get active reverse-proxy policy",
    description="Private internal contract containing active enforcement material.",
)
async def get_proxy_config(
    _: None = Depends(require_internal_api_token),
    service: ProxyConfigService = Depends(get_proxy_config_service),
) -> ApiResponse[ProxyPolicySnapshot]:
    """Return active JWT, rate-limit, and IP-block policy to the data plane."""
    snapshot = await service.get_snapshot()
    return success_response(message="Proxy policy fetched successfully.", data=snapshot)

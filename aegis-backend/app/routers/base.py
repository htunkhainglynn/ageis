from fastapi import APIRouter

from app.routers.api_key_router import router as api_key_router
from app.routers.auth_router import router as auth_router
from app.routers.ip_block_router import router as ip_block_router
from app.routers.jwt_config_router import router as jwt_config_router
from app.routers.internal_router import router as internal_router
from app.routers.rate_limit_rule_router import router as rate_limit_rule_router
from app.routers.user_router import router as user_router
from app.routers.threat_rule_router import router as threat_rule_router
from app.routers.analytics_router import router as analytics_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(user_router)
api_router.include_router(auth_router)
api_router.include_router(api_key_router)
api_router.include_router(ip_block_router)
api_router.include_router(rate_limit_rule_router)
api_router.include_router(jwt_config_router)
api_router.include_router(internal_router)
api_router.include_router(threat_rule_router)
api_router.include_router(analytics_router)

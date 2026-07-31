from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models.user import User
from app.repositories.jwt_config_repository import JWTConfigRepository
from app.repositories.user_repository import UserRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.jwt_config import (
    JWTConfigCreateRequest,
    JWTConfigListResponse,
    JWTConfigResponse,
    JWTConfigUpdateRequest,
)
from app.services.jwt_config_service import JWTConfigService

router = APIRouter(prefix="/jwt-configs", tags=["JWT Configs"])


def get_jwt_config_service(db: AsyncSession = Depends(get_db)) -> JWTConfigService:
    """Provide a request-scoped JWT config service instance."""
    jwt_config_repository = JWTConfigRepository(db=db)
    user_repository = UserRepository(db=db)
    return JWTConfigService(jwt_config_repository=jwt_config_repository, user_repository=user_repository)


@router.post(
    "",
    response_model=ApiResponse[JWTConfigResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create JWT config",
    description="Create a new JWT validation config in disabled state. Admin only.",
)
async def create_jwt_config(
    payload: JWTConfigCreateRequest,
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[JWTConfigResponse]:
    """Create JWT config."""
    created_config = await jwt_config_service.create_config(
        actor_subject=str(actor.id),
        payload=payload,
    )
    return success_response(message="JWT config created successfully.", data=created_config)


@router.get(
    "",
    response_model=ApiResponse[JWTConfigListResponse],
    summary="List JWT configs",
    description="List JWT validation configs with masked key material. Admin only.",
)
async def list_jwt_configs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[JWTConfigListResponse]:
    """List JWT configs."""
    configs = await jwt_config_service.list_configs(
        actor_subject=str(actor.id),
        skip=skip,
        limit=limit,
    )
    return success_response(message="JWT configs fetched successfully.", data=configs)


@router.get(
    "/{config_id}",
    response_model=ApiResponse[JWTConfigResponse],
    summary="Get JWT config",
    description="Retrieve one JWT validation config by id with masked key material. Admin only.",
)
async def get_jwt_config(
    config_id: int,
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[JWTConfigResponse]:
    """Get JWT config."""
    jwt_config = await jwt_config_service.get_config(
        actor_subject=str(actor.id),
        config_id=config_id,
    )
    return success_response(message="JWT config fetched successfully.", data=jwt_config)


@router.patch(
    "/{config_id}",
    response_model=ApiResponse[JWTConfigResponse],
    summary="Update JWT config",
    description="Update non-key JWT config fields. Admin only.",
)
async def update_jwt_config(
    config_id: int,
    payload: JWTConfigUpdateRequest,
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[JWTConfigResponse]:
    """Update JWT config."""
    updated_config = await jwt_config_service.update_config(
        actor_subject=str(actor.id),
        config_id=config_id,
        payload=payload,
    )
    return success_response(message="JWT config updated successfully.", data=updated_config)


@router.post(
    "/{config_id}/activate",
    response_model=ApiResponse[JWTConfigResponse],
    summary="Activate JWT config",
    description="Activate one JWT config and disable previously active config. Admin only.",
)
async def activate_jwt_config(
    config_id: int,
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[JWTConfigResponse]:
    """Activate JWT config."""
    activated_config = await jwt_config_service.activate_config(
        actor_subject=str(actor.id),
        config_id=config_id,
    )
    return success_response(message="JWT config activated successfully.", data=activated_config)


@router.delete(
    "/{config_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Disable JWT config",
    description="Soft-delete JWT config by setting status=disabled. Admin only.",
)
async def disable_jwt_config(
    config_id: int,
    actor: User = Depends(require_admin),
    jwt_config_service: JWTConfigService = Depends(get_jwt_config_service),
) -> ApiResponse[None]:
    """Disable JWT config."""
    await jwt_config_service.disable_config(
        actor_subject=str(actor.id),
        config_id=config_id,
    )
    return success_response(message="JWT config disabled successfully.", data=None)

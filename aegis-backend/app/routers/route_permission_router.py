from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import require_admin
from app.core.database import get_db
from app.models.route_permission import RoutePermissionStatus
from app.models.user import User
from app.repositories.route_permission_repository import RoutePermissionRepository
from app.schemas.base import ApiResponse, success_response
from app.schemas.route_permission import (
    RoutePermissionCreateRequest,
    RoutePermissionListResponse,
    RoutePermissionResponse,
    RoutePermissionUpdateRequest,
)
from app.services.route_permission_service import RoutePermissionService

router = APIRouter(prefix="/route-permissions", tags=["Route Permissions"])


def get_service(db: AsyncSession = Depends(get_db)) -> RoutePermissionService:
    return RoutePermissionService(RoutePermissionRepository(db))


@router.post("", response_model=ApiResponse[RoutePermissionResponse], status_code=201)
async def create_permission(
    payload: RoutePermissionCreateRequest,
    actor: User = Depends(require_admin),
    service: RoutePermissionService = Depends(get_service),
):
    return success_response("Route permission created successfully.", await service.create(actor, payload))


@router.get("", response_model=ApiResponse[RoutePermissionListResponse])
async def list_permissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status_filter: RoutePermissionStatus | None = Query(None, alias="status"),
    actor: User = Depends(require_admin),
    service: RoutePermissionService = Depends(get_service),
):
    return success_response(
        "Route permissions fetched successfully.",
        await service.list(actor, skip, limit, status_filter.value if status_filter else None),
    )


@router.get("/{permission_id}", response_model=ApiResponse[RoutePermissionResponse])
async def get_permission(
    permission_id: int,
    actor: User = Depends(require_admin),
    service: RoutePermissionService = Depends(get_service),
):
    return success_response("Route permission fetched successfully.", await service.get(actor, permission_id))


@router.patch("/{permission_id}", response_model=ApiResponse[RoutePermissionResponse])
async def update_permission(
    permission_id: int,
    payload: RoutePermissionUpdateRequest,
    actor: User = Depends(require_admin),
    service: RoutePermissionService = Depends(get_service),
):
    return success_response(
        "Route permission updated successfully.", await service.update(actor, permission_id, payload)
    )


@router.delete("/{permission_id}", response_model=ApiResponse[None])
async def disable_permission(
    permission_id: int,
    actor: User = Depends(require_admin),
    service: RoutePermissionService = Depends(get_service),
):
    await service.disable(actor, permission_id)
    return success_response("Route permission disabled successfully.", None)

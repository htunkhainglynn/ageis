from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.route_permission import RoutePermissionStatus
from app.models.user import User, UserRole
from app.repositories.route_permission_repository import RoutePermissionRepository
from app.schemas.route_permission import (
    RoutePermissionCreateInDB,
    RoutePermissionCreateRequest,
    RoutePermissionListResponse,
    RoutePermissionResponse,
    RoutePermissionUpdateInDB,
    RoutePermissionUpdateRequest,
)


class RoutePermissionService:
    def __init__(self, repository: RoutePermissionRepository) -> None:
        self.repository = repository

    @staticmethod
    def _assert_admin(actor: User) -> None:
        if actor.role != UserRole.ADMIN.value:
            raise ForbiddenException("ROUTE_PERMISSION_FORBIDDEN", "You cannot manage route permissions.")

    async def _assert_unique(self, method: str, path: str, exclude_id: int | None = None) -> None:
        existing = await self.repository.get_active_by_route(method, path, exclude_id)
        if existing is not None:
            raise ConflictException(
                "ROUTE_PERMISSION_ALREADY_ACTIVE",
                "An active route permission already exists for this method and path.",
            )

    async def create(self, actor: User, payload: RoutePermissionCreateRequest) -> RoutePermissionResponse:
        self._assert_admin(actor)
        if payload.status == RoutePermissionStatus.ACTIVE:
            await self._assert_unique(payload.method.value, payload.path_pattern)
        created = await self.repository.create_permission(
            RoutePermissionCreateInDB(
                method=payload.method.value,
                path_pattern=payload.path_pattern,
                required_scope=payload.required_scope,
                status=payload.status.value,
                created_by=actor.id,
            )
        )
        return RoutePermissionResponse.model_validate(created)

    async def list(self, actor: User, skip: int, limit: int, status: str | None) -> RoutePermissionListResponse:
        self._assert_admin(actor)
        items = await self.repository.list_permissions(skip, limit, status)
        return RoutePermissionListResponse(
            items=[RoutePermissionResponse.model_validate(item) for item in items],
            skip=skip,
            limit=limit,
            total=await self.repository.count_permissions(status),
        )

    async def get(self, actor: User, permission_id: int) -> RoutePermissionResponse:
        self._assert_admin(actor)
        permission = await self.repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("ROUTE_PERMISSION_NOT_FOUND", "Route permission not found.")
        return RoutePermissionResponse.model_validate(permission)

    async def update(
        self, actor: User, permission_id: int, payload: RoutePermissionUpdateRequest
    ) -> RoutePermissionResponse:
        self._assert_admin(actor)
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise BadRequestException("ROUTE_PERMISSION_INVALID_UPDATE", "At least one field is required.")
        permission = await self.repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("ROUTE_PERMISSION_NOT_FOUND", "Route permission not found.")
        method = payload.method.value if payload.method is not None else permission.method
        path = payload.path_pattern if payload.path_pattern is not None else permission.path_pattern
        status = payload.status.value if payload.status is not None else permission.status
        if status == RoutePermissionStatus.ACTIVE.value:
            await self._assert_unique(method, path, permission.id)
        if payload.method is not None:
            data["method"] = payload.method.value
        if payload.status is not None:
            data["status"] = payload.status.value
        updated = await self.repository.update_permission(permission, RoutePermissionUpdateInDB(**data))
        return RoutePermissionResponse.model_validate(updated)

    async def disable(self, actor: User, permission_id: int) -> None:
        self._assert_admin(actor)
        permission = await self.repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("ROUTE_PERMISSION_NOT_FOUND", "Route permission not found.")
        if permission.status != RoutePermissionStatus.DISABLED.value:
            await self.repository.update_permission(
                permission, RoutePermissionUpdateInDB(status=RoutePermissionStatus.DISABLED.value)
            )

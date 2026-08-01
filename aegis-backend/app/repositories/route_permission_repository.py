from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.route_permission import RoutePermission, RoutePermissionStatus
from app.repositories.base import BaseRepository
from app.schemas.route_permission import RoutePermissionCreateInDB, RoutePermissionUpdateInDB


class RoutePermissionRepository(
    BaseRepository[RoutePermission, RoutePermissionCreateInDB, RoutePermissionUpdateInDB]
):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(RoutePermission, db)

    async def create_permission(self, payload: RoutePermissionCreateInDB) -> RoutePermission:
        permission = RoutePermission(**payload.model_dump())
        self.db.add(permission)
        await self.db.commit()
        await self.db.refresh(permission)
        return permission

    async def update_permission(
        self, permission: RoutePermission, payload: RoutePermissionUpdateInDB
    ) -> RoutePermission:
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(permission, key, value)
        await self.db.commit()
        await self.db.refresh(permission)
        return permission

    async def list_permissions(
        self, skip: int, limit: int, status: str | None
    ) -> list[RoutePermission]:
        query = select(RoutePermission)
        if status is not None:
            query = query.where(RoutePermission.status == status)
        result = await self.db.execute(
            query.order_by(RoutePermission.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count_permissions(self, status: str | None) -> int:
        query = select(func.count(RoutePermission.id))
        if status is not None:
            query = query.where(RoutePermission.status == status)
        return int((await self.db.execute(query)).scalar_one())

    async def get_active_by_route(
        self,
        method: str,
        path_pattern: str,
        exclude_id: int | None = None,
    ) -> RoutePermission | None:
        query = select(RoutePermission).where(
            and_(
                RoutePermission.method == method,
                RoutePermission.path_pattern == path_pattern,
                RoutePermission.status == RoutePermissionStatus.ACTIVE.value,
            )
        )
        if exclude_id is not None:
            query = query.where(RoutePermission.id != exclude_id)
        return (await self.db.execute(query)).scalar_one_or_none()

    async def list_active_permissions(self) -> list[RoutePermission]:
        result = await self.db.execute(
            select(RoutePermission)
            .where(RoutePermission.status == RoutePermissionStatus.ACTIVE.value)
            .order_by(RoutePermission.id.asc())
        )
        return list(result.scalars().all())

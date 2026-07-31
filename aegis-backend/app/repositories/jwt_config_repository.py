from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jwt_config import JWTConfig, JWTConfigStatus
from app.repositories.base import BaseRepository
from app.schemas.jwt_config import JWTConfigCreateInDB, JWTConfigUpdateInDB


class JWTConfigRepository(BaseRepository[JWTConfig, JWTConfigCreateInDB, JWTConfigUpdateInDB]):
    """Repository for JWT configuration persistence operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(JWTConfig, db)

    async def create_config(self, payload: JWTConfigCreateInDB) -> JWTConfig:
        """Create a new JWT config record."""
        jwt_config = JWTConfig(**payload.model_dump())
        self.db.add(jwt_config)
        await self.db.commit()
        await self.db.refresh(jwt_config)
        return jwt_config

    async def list_configs(self, skip: int, limit: int) -> list[JWTConfig]:
        """List JWT configs with pagination."""
        result = await self.db.execute(
            select(JWTConfig)
            .order_by(JWTConfig.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_configs(self) -> int:
        """Count total JWT configs."""
        result = await self.db.execute(select(func.count(JWTConfig.id)))
        return int(result.scalar_one())

    async def update_config(self, jwt_config: JWTConfig, payload: JWTConfigUpdateInDB) -> JWTConfig:
        """Update mutable fields on an existing JWT config."""
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(jwt_config, key, value)

        await self.db.commit()
        await self.db.refresh(jwt_config)
        return jwt_config

    async def activate_config(self, jwt_config: JWTConfig) -> JWTConfig:
        """Activate one config and deactivate any currently active config."""
        await self.db.execute(
            update(JWTConfig)
            .where(JWTConfig.status == JWTConfigStatus.ACTIVE.value)
            .values(status=JWTConfigStatus.DISABLED.value)
        )
        jwt_config.status = JWTConfigStatus.ACTIVE.value
        await self.db.commit()
        await self.db.refresh(jwt_config)
        return jwt_config

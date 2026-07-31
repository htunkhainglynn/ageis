from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.repositories.base import BaseRepository
from app.schemas.api_key import APIKeyCreateInDB, APIKeyUpdateInDB


class APIKeyRepository(BaseRepository[APIKey, APIKeyCreateInDB, APIKeyUpdateInDB]):
    """Repository for API key persistence operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(APIKey, db)

    async def get_keys_by_owner(self, owner_id: int, skip: int, limit: int) -> list[APIKey]:
        """Return API keys for a single owner with pagination."""
        result = await self.db.execute(
            select(APIKey)
            .where(APIKey.owner_id == owner_id)
            .order_by(APIKey.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_keys_by_owner(self, owner_id: int) -> int:
        """Count total API keys for an owner."""
        result = await self.db.execute(select(func.count(APIKey.id)).where(APIKey.owner_id == owner_id))
        return int(result.scalar_one())

    async def count_all_keys(self) -> int:
        """Count API keys across all owners for administrator views."""
        result = await self.db.execute(select(func.count(APIKey.id)))
        return int(result.scalar_one())

    async def get_candidates_by_prefix(self, key_prefix: str) -> list[APIKey]:
        """Return the small candidate set for constant-format key verification."""
        result = await self.db.execute(
            select(APIKey).where(APIKey.key_prefix == key_prefix)
        )
        return list(result.scalars().all())

    async def create_api_key(self, payload: APIKeyCreateInDB) -> APIKey:
        """Create a new API key record."""
        api_key = APIKey(**payload.model_dump())
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def update_api_key(self, api_key: APIKey, payload: APIKeyUpdateInDB) -> APIKey:
        """Update API key metadata fields."""
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in update_data.items():
            setattr(api_key, key, value)

        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

from typing import Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel as ORMBaseModel

ModelType = TypeVar("ModelType", bound=ORMBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic async repository providing basic CRUD operations."""

    def __init__(self, model: type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get_by_id(self, item_id: int) -> ModelType | None:
        """Retrieve a single record by primary key."""
        result = await self.db.execute(select(self.model).where(self.model.id == item_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Retrieve a list of records with pagination."""
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        db_obj = self.model(**obj_in.model_dump())
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, item_id: int, obj_in: UpdateSchemaType) -> ModelType | None:
        """Update an existing record by primary key."""
        db_obj = await self.get_by_id(item_id)
        if db_obj is None:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)

        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def delete(self, item_id: int) -> bool:
        """Delete an existing record by primary key."""
        db_obj = await self.get_by_id(item_id)
        if db_obj is None:
            return False

        await self.db.delete(db_obj)
        await self.db.commit()
        return True

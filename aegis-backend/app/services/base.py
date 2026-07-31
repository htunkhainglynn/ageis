from typing import Generic, TypeVar

from pydantic import BaseModel

from app.models.base import BaseModel as ORMBaseModel
from app.repositories.base import BaseRepository

ModelType = TypeVar("ModelType", bound=ORMBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic service wrapper around a repository."""

    def __init__(
        self,
        repository: BaseRepository[ModelType, CreateSchemaType, UpdateSchemaType],
    ) -> None:
        self.repository = repository

    async def get_by_id(self, item_id: int) -> ModelType | None:
        """Retrieve a record by id."""
        return await self.repository.get_by_id(item_id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Retrieve records with pagination."""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record."""
        return await self.repository.create(obj_in)

    async def update(self, item_id: int, obj_in: UpdateSchemaType) -> ModelType | None:
        """Update a record by id."""
        return await self.repository.update(item_id, obj_in)

    async def delete(self, item_id: int) -> bool:
        """Delete a record by id."""
        return await self.repository.delete(item_id)

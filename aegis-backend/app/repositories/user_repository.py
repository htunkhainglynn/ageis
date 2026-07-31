from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserCreateInDB, UserUpdate, UserUpdateInDB


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """Repository for user persistence operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def count_all(self) -> int:
        """Count total users."""
        result = await self.db.execute(select(func.count(User.id)))
        total = result.scalar_one()
        return int(total)

    async def create_user(self, payload: UserCreateInDB) -> User:
        """Create a user with prepared persistence fields."""
        user = User(**payload.model_dump())
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user(self, user: User, payload: UserUpdateInDB) -> User:
        """Update a user model with prepared persistence fields."""
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        await self.db.commit()
        await self.db.refresh(user)
        return user

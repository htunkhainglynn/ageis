from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreateInDB, UserUpdateInDB
from app.utils.logger import logger


def _first_bootstrap_admin_email() -> str | None:
    """Return the first explicitly configured bootstrap administrator email."""
    for candidate in settings.BOOTSTRAP_ADMIN_EMAILS.split(","):
        email = candidate.strip().lower()
        if email:
            return email
    return None


async def ensure_bootstrap_admin(db: AsyncSession) -> User | None:
    """Create or promote the environment-configured bootstrap administrator."""
    email = _first_bootstrap_admin_email()
    password = settings.BOOTSTRAP_ADMIN_PASSWORD
    if email is None or password == "":
        return None

    repository = UserRepository(db=db)
    user = await repository.get_by_email(email)
    if user is None:
        user = await repository.create_user(
            UserCreateInDB(
                email=email,
                full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
                hashed_password=hash_password(password),
                is_active=True,
                role=UserRole.ADMIN.value,
            )
        )
        logger.info("Bootstrap administrator created")
        return user

    if user.role != UserRole.ADMIN.value or not user.is_active:
        user = await repository.update_user(
            user=user,
            payload=UserUpdateInDB(
                role=UserRole.ADMIN.value,
                is_active=True,
            ),
        )
        logger.info("Bootstrap administrator role ensured")
    return user


async def bootstrap_from_environment() -> None:
    """Run optional bootstrap setup using a dedicated database session."""
    async with AsyncSessionLocal() as db:
        await ensure_bootstrap_admin(db)
